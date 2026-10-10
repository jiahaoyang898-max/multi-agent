import asyncio
from itertools import chain

from langchain_classic.chains.question_answering.map_rerank_prompt import output_parser
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime
from typing_extensions import runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.core.log import logger
from app.models.es.value_info_es import ValueInfoEs
from app.prompt.prompt_loader import loader_prompt

async def recall_value(state: DataAgentState,runtime:Runtime[DataAgentContext]):
	writer=runtime.stream_writer
	writer({"stage":"召回字段取值"})
	try:
		query=state["query"]
		keyworks=state["keywords"]
		value_es_repository=runtime.context["value_es_repository"]
		prompt = PromptTemplate(template=loader_prompt("extend_keywords_for_value_recall"), input_variables=["query"])
		output_parser=JsonOutputParser()
		chain=prompt|llm|output_parser
		result=await chain.ainvoke({"query":query})
		keyworks=list(set(keyworks+result))
		values_map:dict[str,ValueInfoEs]={}
		for keywork in keyworks:
			values:list[ValueInfoEs]=await value_es_repository.search(keywork,threshold=0)
			for value in values:
				value_id=value["id"]
				if value_id not in values_map:
					values_map[value_id] = value
		retrieved_values=list(values_map.values())
		logger.info(f"召回字段取值：{list(values_map.keys())}")
		return {"retrieved_values":retrieved_values}
	except Exception as e:
		logger.error(f"召回字段取值异常：{str(e)}")
		raise

if __name__ == "__main__":
	from unittest.mock import MagicMock
	from app.repositories.es.value_es_repository import ValueEsRepository
	from app.clients.es_client_manager import es_client_manager
	async def main():
		es_client_manager.init()
		state={
			"query":"统计广东省的销售总额",
			"keyworks":["统计","统计广东省的销售总额","销售总额","广东省"],
		}
		value_repo= ValueEsRepository(es_client_manager.client)
		runtime=MagicMock()
		runtime.stream_writer=lambda x:print(f"进度:{x}")
		runtime.context={"value_es_repository":value_repo}
		result=await recall_value(state,runtime)
		print(f"\n召回到的值：{result['retrieved_values']}")
		print(f"共{len(result['retrieved_values'])}条")
		await es_client_manager.close()
	asyncio.run(main())







