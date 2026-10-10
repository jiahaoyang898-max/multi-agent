
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def normalize_value(value):
    """把数据库驱动返回的特殊类型转成可被 JSON 直接序列化的原生类型。

    MySQL 的 SUM/AVG 等聚合会返回 decimal.Decimal，而查询服务用
    json.dumps(..., default=str) 兜底时会把它变成「字符串」，导致前端拿到的数字
    变成 "132" 这种形式：表格不右对齐、不加千分位、KPI 大数卡不触发、图表条宽全为 0。
    这里在出库时统一归一化，保证数字就是数字。
    """
    if isinstance(value, Decimal):
        # 整数值的 Decimal 转 int（如 SUM(int) 的结果），否则转 float
        try:
            if value == value.to_integral_value():
                return int(value)
        except Exception:
            pass
        return float(value)
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace")
    return value


class DwMysqlRepository:
    def __init__(self,session: AsyncSession):
        self.session = session
    async def get_column_values(self,table_name:str,column_name:str,limit:int=10):
        # distinct去重
        sql =f"select distinct {column_name} from {table_name} limit {limit}"
        result = await self.session.execute(text(sql))
        return result.scalars().fetchall()
    async def get_column_types(self,table_name:str):
        #MySQL 内置指令，专门查看表字段详情
        sql=f"show columns from {table_name}"
        result = await self.session.execute(text(sql))
        return {row.Field:row.Type for row in result.fetchall()}
    async def get_db_info(self):
        #查询数据库环境信息，版本、方言
        result=await self.session.execute(text("select version()"))
        version=result.scalar()
        dialect=self.session.get_bind().dialect.name
        return {"version":version,"dialect":dialect}

    async def validate_sql(self, sql:str):
        #用explain验证sql
        # 注意：EXPLAIN 与 SQL 之间必须留空格，否则会拼成 "explainSELECT ..." 触发 1064 语法错误，
        # 导致每次查询都误判「校验失败」而多走一轮大模型纠错。
        await self.session.execute(text(f"EXPLAIN {sql}"))

    async def execute_sql(self,sql):
        #最终执行sql
        result = await self.session.execute(text(sql))
        return [
            {key: normalize_value(value) for key, value in row.items()}
            for row in result.mappings().fetchall()
        ]

