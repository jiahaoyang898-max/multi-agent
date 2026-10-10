import asyncio
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime
from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.core.log import logger
from app.models.es.value_info_es import ValueInfoEs
from app.prompt.prompt_loader import loader_prompt


async def validate_sql(state:DataAgentState,runtime:Runtime[DataAgentContext]):
		writer = runtime.stream_writer
		writer({"stage":"校验SQL"})
		sql = state["sql"]
		dw_mysql_repository = runtime.context["dw_mysql_repository"]
		try:
			await dw_mysql_repository.validate_sql(sql)
			logger.info(f"sql验证正确:{sql}")
			return {"error":None}
		except Exception as e:
			logger.info(f"sql验证失败:{sql}")
			return {"error":str(e)}