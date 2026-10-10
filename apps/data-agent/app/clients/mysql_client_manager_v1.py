import asyncio
from typing import Union
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine, AsyncSession
from sqlalchemy import text
from app.conf.app_config import app_config,DBConfig

class MysqlClientManager:
    def __init__(self,db_config: DBConfig):
        self.db_config = db_config
        self.engine:Union[AsyncEngine,None] = None
    def _get_url(self):
        return f"mysql+asyncmy://{self.db_config.user}:{self.db_config.password}@{self.db_config.host}:{self.db_config.port}/{self.db_config.database}?charset=utf8mb4"
    def init(self):
        self.engine = create_async_engine(
            self._get_url(),
            pool_size=10,
            pool_pre_ping=True
        )
    async def close(self):
        await self.engine.dispose()
dw_mysql_client_manager = MysqlClientManager(app_config.db_dw)
meta_mysql_client_manager = MysqlClientManager(app_config.db_meta)

if __name__ == '__main__':
    dw_mysql_client_manager.init()
    async def test():
        async with AsyncSession(dw_mysql_client_manager.engine) as session:
            result = await session.execute(text("select * from fact_order limit 10"))
            rows = result.fetchall()
            print(type(rows[0]))
            print(rows[0])
    asyncio.run(test())


