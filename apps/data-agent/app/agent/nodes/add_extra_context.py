import asyncio
from datetime import datetime
from langgraph.runtime import Runtime
from urllib3.filepost import writer

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState, DateInfoStata
from app.core.log import logger
from app.repositories.mysql.dw_mysql_repository import DwMysqlRepository

async def add_extra_context(state:DataAgentState,runtime:Runtime[DataAgentContext]):
		writer=runtime.stream_writer
		writer({"stage":"添加额外上下文"})
		try:
			today=datetime.today()
			date=today.strftime("%Y-%m-%d")
			weekday=today.strftime("%A")
			quarter=f"Q{(today.month - 1 )//3+1}"
			date_info=DateInfoStata(date=date,weekday=weekday,quarter=quarter)
			dw_mysql_repository:DwMysqlRepository=runtime.context["dw_mysql_repository"]
			#返回版本和方言
			db_info=await dw_mysql_repository.get_db_info()
			logger.info(f"额外上下文信息添加，日期信息{date_info},数据库信息{db_info}")
			return {"date_info":date_info,"db_info":db_info}
		except Exception as e:
			logger.error(f"额外上下文信息添加异常：{str(e)}")
			raise