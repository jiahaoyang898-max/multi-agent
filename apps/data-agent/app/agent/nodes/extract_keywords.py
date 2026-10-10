import jieba.analyse
from langgraph.runtime import Runtime
from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger

async def extract_keywords(state:DataAgentState,runtime:Runtime[DataAgentContext]):
    writer=runtime.stream_writer
    writer({"stage":"抽取关键字"})
    try:
        query=state["query"]
        allow_pos =(
            "n",  # 名词: 数据、服务器、表格
            "nr",  # 人名: 张三、李四
            "ns",  # 地名: 北京、上海
            "nt",  # 机构团体名: 政府、学校、某公司
            "nz",  # 其他专有名词: Unicode、哈希算法、诺贝尔奖
            "v",  # 动词: 运行、开发
            "vn",  # 名动词: 工作、研究
            "a",  # 形容词: 美丽、快速
            "an",  # 名形词: 难度、合法性、复杂度
            "eng",  # 英文
            "i",  # 成语
            "l",  # 常用固定短语
        )
        keyworks:list[str]=jieba.analyse.extract_tags(query,allowPOS=allow_pos)
        keyworks=list(set(keyworks+[query]))
        logger.info(f"抽取关键字:{keyworks}")
        return {"keywords":keyworks}
    except Exception as e:
        logger.error(f"抽取关键字异常:{str(e)}")
        raise