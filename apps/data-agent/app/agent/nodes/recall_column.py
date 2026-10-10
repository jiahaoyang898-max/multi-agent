import asyncio
from unittest.mock import MagicMock

from anyio.itertools import chain
from dns.e164 import query
from langchain_classic.chains.question_answering.map_rerank_prompt import output_parser
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.core.log import logger
from app.models.qdrant.column_info_qdrant import ColumnInfoQdrant
from app.prompt.prompt_loader import loader_prompt

async def recall_column(state:DataAgentState,runtime:Runtime[DataAgentContext]):
    writer=runtime.stream_writer
    writer({"stage":"召回列数据"})
    try:
        query=state["query"]
        keywords=state["keywords"]
        embedding_client=runtime.context["embedding_client"]
        column_qdrant_repository=runtime.context["column_qdrant_repository"]
        prompt=PromptTemplate(template=loader_prompt("extend_keywords_for_column_recall"), input_variables=["query"])
        output_parser=JsonOutputParser()
        chain=prompt|llm|output_parser
        result=await chain.ainvoke({"query":query})
        keywords=set(keywords+result)
        retrieved_columns_map:dict[str,ColumnInfoQdrant]={}
        for keyword in keywords:
            embedding = await embedding_client.aembed_query(keyword)
            payloads:list[ColumnInfoQdrant]=await column_qdrant_repository.search(embedding)
            for payload in payloads:
                column_id = payload["id"]
                if column_id not in retrieved_columns_map:
                    retrieved_columns_map[column_id]=payload
        retrieved_columns=list(retrieved_columns_map.values())
        logger.info(f"召回字段信息：{list(retrieved_columns_map.keys())}")
        return {"retrieved_columns":retrieved_columns}
    except Exception as e:
        logger.error(f"召回字段信息异常{str(e)}")
        raise

if __name__ == "__main__":
    async def main():
        # 初始化客户端
        from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
        from app.clients.embedding_client_manager import embedding_client_manager
        from app.clients.qdrant_client_manager import qdrant_client_manager
        embedding_client_manager.init()
        qdrant_client_manager.init()
        state = {
            "query": "统计华北地区销售总额",
            "keywords": ["统计", "统计华北地区销售总额", "销售总额", "华北地区"],
        }
        column_repo=ColumnQdrantRepository(qdrant_client_manager.client)
        runtime=MagicMock()
        runtime.stream_writer=lambda x :print(f"进度：{x}")
        runtime.context={
            "embedding_client":embedding_client_manager.client,
            "column_qdrant_repository":column_repo,
        }
        result=await recall_column(state,runtime)
        print(f"\n召回字段: {result['retrieved_columns']}")
        print(f"共 {len(result['retrieved_columns'])} 个字段")
        await qdrant_client_manager.close()
    asyncio.run(main())

