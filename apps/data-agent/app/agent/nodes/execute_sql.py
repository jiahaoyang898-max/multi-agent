from langgraph.runtime import Runtime
from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger


async def execute_sql(state:DataAgentState,runtime:Runtime[DataAgentContext]):
		writer = runtime.stream_writer
		writer({"stage":"执行SQL"})
		try:
			sql = state["sql"]
			dw_mysql_repository = runtime.context["dw_mysql_repository"]
			result = await dw_mysql_repository.execute_sql(sql)
			logger.info(f"执行sql的结果{result}")
			writer({"result":result})
		except Exception as e:
			logger.error(f"执行sql的结果异常：:{str(e)}")
			raise