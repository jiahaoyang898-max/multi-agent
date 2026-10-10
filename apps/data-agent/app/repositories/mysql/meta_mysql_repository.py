from cgitb import text

from dns.e164 import query
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mysql.column_info_mysql import ColumnInfoMySQL
from app.models.mysql.column_metric_mysql import ColumnMetricMySQL
from app.models.mysql.metric_info_mysql import MetricInfoMySQL
from app.models.mysql.table_info_mysql import TableInfoMySQL

class MetaMysqlRepository:
    def __init__(self,session: AsyncSession):
        self.session = session

    async def _upsert_all(self, objects: list):
        """按主键做 UPSERT（存在则更新，不存在则插入）。

        原来用的是 session.add_all（纯 INSERT），「重建知识」重跑时会撞主键报
        IntegrityError，导致 meta 库里的字段取值样例无法刷新。
        """
        for obj in objects:
            await self.session.merge(obj)

    async def save_table_infos(self,table_infos: list[TableInfoMySQL]):
        await self._upsert_all(table_infos)
    async def save_column_infos(self,column_infos: list[ColumnInfoMySQL]):
        await self._upsert_all(column_infos)
    async def save_metric_infos(self,metric_infos: list[MetricInfoMySQL]):
        await self._upsert_all(metric_infos)
    async def save_column_metric_infos(self,column_metric_infos: list[ColumnMetricMySQL]):
        await self._upsert_all(column_metric_infos)
    async def get_column_info_by_id(self,column_id:str) -> ColumnInfoMySQL | None:
        return await self.session.get(ColumnInfoMySQL,column_id)
    async def get_key_columns_by_table_id(self,table_id:str)->list[ColumnInfoMySQL]:
        sql="""
            select * from column_info where table_id =:table_id and role in  ("primary_key","foreign_key")
        """
        query = select(ColumnInfoMySQL).from_statement(text(sql))
        result = await self.session.execute(query,{"table_id":table_id})
        return result.scalars().fetchall()
    async def get_table_info_by_id(self,table_id:str) -> TableInfoMySQL:
        return await self.session.get(TableInfoMySQL,table_id)