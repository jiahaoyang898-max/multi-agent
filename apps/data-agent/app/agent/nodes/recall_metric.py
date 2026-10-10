import asyncio

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.core.log import logger
from app.models.qdrant.metric_info_qdrant import MetricInfoQdrant
from app.prompt.prompt_loader import loader_prompt


async def recall_metric(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"stage": "召回指标数据"})
    try:
        query = state['query']
        keywords = state["keywords"]
        embedding_client = runtime.context["embedding_client"]
        metric_qdrant_repository = runtime.context["metric_qdrant_repository"]
        prompt = PromptTemplate(template=loader_prompt("extend_keywords_for_metric_recall"), input_variables=["query"])
        output_parser = JsonOutputParser()
        chain = prompt | llm | output_parser
        result = await chain.ainvoke({"query": query})
        keywords = set(keywords + result)
        retrieved_metric_map: dict[str, MetricInfoQdrant] = {}
        for keyword in keywords:
            embedding = await embedding_client.aembed_query(keyword)
            payloads: list[MetricInfoQdrant] = await metric_qdrant_repository.search(embedding)
            for payload in payloads:
                metric_id = payload["id"]
                if metric_id not in retrieved_metric_map:
                    retrieved_metric_map[metric_id] = payload
        retrieved_metrics = list(retrieved_metric_map.values())
        logger.info(f"召回指标信息:{list(retrieved_metric_map.keys())}")
        return {"retrieved_metrics": retrieved_metrics}
    except Exception as e:
        logger.error(f"召回指标信息异常：{str(e)}")
        raise


if __name__ == "__main__":
    from unittest.mock import MagicMock
    from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository
    from app.clients.embedding_client_manager import embedding_client_manager
    from app.clients.qdrant_client_manager import qdrant_client_manager


    async def main():
        embedding_client_manager.init()
        qdrant_client_manager.init()
        state = {
            "query": "统计华北地区销售总额",
            "keywords": ["统计", "统计华北地区销售总额", "销售总额", "华北地区"],
        }
        metric_repo = MetricQdrantRepository(qdrant_client_manager.client)
        runtime = MagicMock()
        runtime.stream_writer = lambda x: print(f"进度: {x}")
        runtime.context = {
            "embedding_client": embedding_client_manager.client,
            "metric_qdrant_repository": metric_repo,
        }
        result = await recall_metric(state, runtime)
        print(f"\n召回指标: {result['retrieved_metrics']}")
        print(f"共 {len(result['retrieved_metrics'])} 个指标")
        await qdrant_client_manager.close()
    asyncio.run(main())
