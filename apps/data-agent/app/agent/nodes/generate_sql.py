import asyncio

import yaml
from langchain_classic.chains.question_answering.map_rerank_prompt import output_parser
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.core.log import logger
from app.prompt.prompt_loader import loader_prompt


async def generate_sql(state:DataAgentState,runtime:Runtime[DataAgentContext]):
		writer = runtime.stream_writer
		writer({"stage":"生成SQL"})
		try:
			query = state["query"]
			table_infos = state["table_infos"]
			metric_infos = state["metric_infos"]
			date_info = state["date_info"]
			db_info = state["db_info"]
			prompt=PromptTemplate(template=loader_prompt("generate_sql"),input_variables=["query","table_infos","metric_infos","date_info","db_info"])
			output_parser=StrOutputParser()
			chain=prompt|llm|output_parser
			result=await chain.ainvoke({
				"query":query,
				"table_infos":yaml.dump(table_infos,allow_unicode=True,sort_keys=False),
				"metric_infos":yaml.dump(metric_infos,allow_unicode=True,sort_keys=False),
				"date_info":yaml.dump(date_info,allow_unicode=True,sort_keys=False),
				"db_info":yaml.dump(db_info,allow_unicode=True,sort_keys=False),
			})
			logger.info(f"生成的sql语句\n:{result}")
			return {"sql":result}
		except Exception as e:
			logger.error(f"生成的sql语句失败:{str(e)}")
			raise








