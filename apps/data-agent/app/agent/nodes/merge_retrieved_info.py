import asyncio
from os import name
from langgraph.runtime import Runtime
from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState, TableInfoStata, MetricInfoStata, ColumnInfoState, ValueInfoEs
from app.core.log import logger
from app.models.mysql.column_info_mysql import ColumnInfoMySQL
from app.models.mysql.metric_info_mysql import MetricInfoMySQL
from app.models.mysql.table_info_mysql import TableInfoMySQL
from app.models.qdrant.column_info_qdrant import ColumnInfoQdrant
from app.models.qdrant.metric_info_qdrant import MetricInfoQdrant

async def merge_retrieved_info(state:DataAgentState,runtime:Runtime[DataAgentContext]):
	writer=runtime.stream_writer
	writer({"stage":"合并召回信息"})
	try:
		table_infos:list[TableInfoStata] = []
		metric_infos:list[MetricInfoStata] = []
		retrieved_columns:list[ColumnInfoQdrant] = state["retrieved_columns"]
		retrieved_values:list[ValueInfoEs] = state["retrieved_values"]
		retrieved_metrics:list[MetricInfoQdrant]= state["retrieved_metrics"]
		meta_mysql_repository=runtime.context["meta_mysql_repository"]
		retrieved_columns_map: dict[str, ColumnInfoQdrant] = {retrieved_column["id"]: retrieved_column for retrieved_column in retrieved_columns}
		for retrieved_metric in retrieved_metrics:
			relevant_columns = retrieved_metric["relevant_columns"]
			for relevant_column in relevant_columns:
				if relevant_column not in retrieved_columns_map:
					column_info_mysql:ColumnInfoMySQL=await meta_mysql_repository.get_column_info_by_id(relevant_column)
					retrieved_columns_map[relevant_column] = convert_column_info_from_mysql_to_qdrant(column_info_mysql)

		for retrieved_value in retrieved_values:
			column_value = retrieved_value["value"]
			column_id = retrieved_value["column_id"]
			if column_id not in retrieved_columns_map:
				column_info_mysql=await meta_mysql_repository.get_column_info_by_id(column_id)
				retrieved_columns_map[column_id] = convert_column_info_from_mysql_to_qdrant(column_info_mysql)
			if column_value not in retrieved_columns_map[column_id]['examples']:
				retrieved_columns_map[column_id]['examples'].append(column_value)

		table_to_column_map:dict[str,list[ColumnInfoQdrant]] = {}
		for column in retrieved_columns_map.values():
			table_id = column["table_id"]
			if table_id not in table_to_column_map:
				table_to_column_map[table_id] = []
			table_to_column_map[table_id].append(column)
		for table_id in table_to_column_map.keys():
			key_columns:list[ColumnInfoMySQL] = await meta_mysql_repository.get_key_columns_by_table_id(table_id)
			column_ids = [column["id"] for column in table_to_column_map[table_id]]
			for key_column in key_columns:
				if key_column.id not in column_ids:
					table_to_column_map[table_id].append(convert_column_info_from_mysql_to_qdrant(key_column))

		for table_id,columns in table_to_column_map.items():
			table:TableInfoMySQL=await meta_mysql_repository.get_table_info_by_id(table_id)
			columns = [convert_column_info_from_qdrant_to_stata(column) for column in columns]
			table_info = TableInfoStata(
				name=table.name,
				role=table.role,
				description=table.description,
				columns=columns
			)
			table_infos.append(table_info)
		metric_infos = [convert_metric_info_from_qdrant_to_stata(retrieved_metric) for retrieved_metric in retrieved_metrics]
		return {
			"table_infos": table_infos,
			"metric_infos": metric_infos
		}
	except Exception as e:
		logger.error(f"合并召回信息异常:{str(e)}")
		raise

def convert_metric_info_from_qdrant_to_stata(metric_info_qdrant: MetricInfoQdrant) -> MetricInfoStata:
    return MetricInfoStata(
        name=metric_info_qdrant['name'],
        description=metric_info_qdrant['description'],
        relevant_columns=metric_info_qdrant['relevant_columns'],
        alias=metric_info_qdrant['alias']

    )


def convert_column_info_from_qdrant_to_stata(column_info_qdrant: ColumnInfoQdrant) -> ColumnInfoState:
    return ColumnInfoState(
        name=column_info_qdrant['name'],
        type=column_info_qdrant['type'],
        role=column_info_qdrant['role'],
        examples=column_info_qdrant['examples'],
        description=column_info_qdrant["description"],
        alias=column_info_qdrant['alias']

    )


# 定义转换类型的函数
def convert_column_info_from_mysql_to_qdrant(column_info_mysql: ColumnInfoMySQL) -> ColumnInfoQdrant:
    return ColumnInfoQdrant(
        id=column_info_mysql.id,
        name=column_info_mysql.name,
        type=column_info_mysql.type,
        role=column_info_mysql.role,
        examples=column_info_mysql.examples,
        description=column_info_mysql.description,
        alias=column_info_mysql.alias,
        table_id=column_info_mysql.table_id
    )


if __name__ == "__main__":
    from unittest.mock import MagicMock


    async def main():
        # 构造三路召回 state
        state = {
            "query": "统计华北地区销售总额",
            "retrieved_columns": [
                {"id": "col_001", "name": "order_amount", "type": "float", "role": "measure",
                 "examples": [10.2, 40.5], "description": "订单金额", "alias": ["amount"], "table_id": "table_001"},
                {"id": "col_002", "name": "region_id", "type": "varchar(20)", "role": "foreign_key",
                 "examples": ["1", "2"], "description": "地区外键", "alias": ["region_code"], "table_id": "table_001"},
            ],
            "retrieved_values": [
                {"id": "val_001", "value": "华北", "type": "str", "column_id": "col_003",
                 "column_name": "region_name", "table_id": "table_002", "table_name": "dim_region"},
            ],
            "retrieved_metrics": [
                {"id": "metric_001", "name": "销售总额", "description": "订单总金额",
                 "relevant_columns": ["col_001", "col_003", "col_004"],
                 "alias": ["total_sales", "销售额"]},
            ],
        }

        # 构造 meta_mysql_repository mock
        meta = MagicMock()

        async def get_col_by_id(cid):
            cols = {
                "col_003": MagicMock(id="col_003", name="region_name", type="varchar(50)", role="dimension",
                                     examples=["华东"], description="地区名称", alias=["region"], table_id="table_002"),
                "col_004": MagicMock(id="col_004", name="order_date", type="date", role="dimension",
                                     examples=["2025-01-01"], description="下单日期", alias=["日期"],
                                     table_id="table_001"),
            }
            return cols.get(cid)

        async def get_keys_by_tid(tid):
            keys = {
                "table_001": [
                    MagicMock(id="pk_001", name="order_id", type="varchar(64)", role="primary_key",
                              examples=[], description="订单主键", alias=[], table_id="table_001"),
                    MagicMock(id="fk_001", name="customer_id", type="varchar(64)", role="foreign_key",
                              examples=[], description="客户外键", alias=[], table_id="table_001"),
                ],
                "table_002": [
                    MagicMock(id="pk_002", name="region_id", type="varchar(20)", role="primary_key",
                              examples=["1"], description="地区主键", alias=[], table_id="table_002"),
                ],
            }
            return keys.get(tid, [])

        async def get_table_by_id(tid):
            tables = {
                "table_001": MagicMock(id="table_001", name="fact_order", role="fact", description="订单事实表"),
                "table_002": MagicMock(id="table_002", name="dim_region", role="dim", description="地区维度表"),
            }
            return tables.get(tid)

        meta.get_column_info_by_id = get_col_by_id
        meta.get_key_columns_by_table_id = get_keys_by_tid
        meta.get_table_info_by_id = get_table_by_id

        # 构造 runtime
        runtime = MagicMock()
        runtime.stream_writer = lambda x: print(f"[进度] {x}")
        runtime.context = {"meta_mysql_repository": meta}

        # 执行
        result = await merge_retrieved_info(state, runtime)

        # 打印结果
        for t in result["table_infos"]:
            print(f"\n表 [{t['role']}] {t['name']} — {t['description']}")
            for c in t["columns"]:
                print(f"  · {c['name']} ({c['role']}): {c['description']}, examples={c['examples']}")

        print(f"\n指标: {[m['name'] for m in result['metric_infos']]}")

    asyncio.run(main())
