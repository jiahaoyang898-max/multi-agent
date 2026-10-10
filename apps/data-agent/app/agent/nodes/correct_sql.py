import asyncio
from zipfile import error

import yaml
from dns.e164 import query
from langchain_classic.chains.question_answering.map_rerank_prompt import output_parser
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime
from urllib3.filepost import writer

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.core.log import logger
from app.prompt.prompt_loader import loader_prompt


async def correct_sql(state:DataAgentState,runtime:Runtime[DataAgentContext]):
		writer = runtime.stream_writer
		writer({"stage":"校正SQL"})
		try:
			query = state["query"]
			table_infos = state["table_infos"]
			metric_infos = state["metric_infos"]
			date_info = state["date_info"]
			db_info = state["db_info"]
			sql = state["sql"]
			error = state["error"]
			prompt=PromptTemplate(template=loader_prompt("correct_sql"),input_variables=["query","table_infos","metric_infos","date_info","db_info","sql","error"])
			output_parser = StrOutputParser()
			chain = prompt | llm |output_parser
			result = await chain.ainvoke({
				"query":query,
				"table_infos": yaml.dump(table_infos, allow_unicode=True, sort_keys=False),
				"metric_infos": yaml.dump(metric_infos, allow_unicode=True, sort_keys=False),
				"date_info": yaml.dump(date_info, allow_unicode=True, sort_keys=False),
				"db_info": yaml.dump(db_info, allow_unicode=True, sort_keys=False),
				"sql": sql,
				"error": error
			})
			logger.info(f"校验生成的正确sql语句\n{result}")
			return {"sql":result}
		except Exception as e:
			logger.error(f"校验生成的正确sql语句异常:{str(e)}")
			raise












