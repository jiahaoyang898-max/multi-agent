import asyncio
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncSession, async_sessionmaker

from app.conf.app_config import app_config, DBConfig

class MysqlClientManager:
    def __init__(self,config:DBConfig):
        self.engine: Optional[AsyncEngine] = None
        self.config=config
        self.session_factory = None
    def _get_url(self):
        return f"mysql+asyncmy://{self.config.user}:{self.config.password}@{self.config.host}:{self.config.port}/{self.config.database}?charset=utf8mb4"
    def init(self):
        self.engine = create_async_engine(
            url=self._get_url(),
            pool_size=5,
            pool_pre_ping=True
        )
        self.session_factory = async_sessionmaker(
            bind=self.engine,
            autoflush=True,
            autobegin = True,
            expire_on_commit = True
        )
    async def close(self):
        await self.engine.dispose()

dw_mysql_client_manager = MysqlClientManager(app_config.db_dw)
meta_mysql_client_manager = MysqlClientManager(app_config.db_meta)

if __name__ == '__main__':
    dw_mysql_client_manager.init()
    meta_mysql_client_manager.init()
    async def test():
        async with dw_mysql_client_manager.session_factory() as session:
            sql = "select * from fact_order limit 10"
            result = await session.execute(text(sql))
            rows = result.mappings().fetchall()
            print(type(rows))
            print(rows[0])
        await dw_mysql_client_manager.close()
    asyncio.run(test())
    async def tests():
        async with meta_mysql_client_manager.session_factory() as session:
            sql = "select *from table_info limit 10"
            result = await session.execute(text(sql))
            rows = result.scalars().fetchall()
            print(rows)
        await meta_mysql_client_manager.close()
    asyncio.run(tests())


