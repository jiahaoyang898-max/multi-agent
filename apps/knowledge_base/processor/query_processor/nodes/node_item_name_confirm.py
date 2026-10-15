# processor/query_processor/nodes/node_item_name_confirm.py

import json
from typing import Dict, Any, List, Tuple

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI

from config.lm_config import lm_config
from config.milvus_config import milvus_config
from processor.query_processor.base import NodeBase
from processor.query_processor.prompt.item_name_confirm import ITEM_NAME_EXTRACT_TEMPLATE, \
    ITEM_NAME_EXTRACT_SYSTEM_PROMPT
from processor.query_processor.state import QueryGraphState
from tool.logger import logger
from utils.embedding_utils import generate_embeddings
from utils.milvus_utils import get_milvus_client, create_hybrid_search_requests, hybrid_search
from utils.mongo_history_utils import get_recent_messages, save_chat_message, update_message_item_names
from utils.json_format_utils import format_json
from utils.task_utils import add_done_task


# ---------------------------------------------------------------------------
# 型号对齐阈值
# ---------------------------------------------------------------------------
# 这里的分数来自 Milvus 混合检索（WeightedRanker(0.8, 0.2, norm_score=True)），
# 是「归一化后的加权分」，量纲固定在 0~1，但正常命中不会接近 1.0。
# 实测（bge-m3 + 当前 kb_item_names 集合）：
#     正确型号命中   ≈ 0.68 ~ 0.75
#     无关型号       ≈ 0.45 ~ 0.55
# 早期代码把「高分」写死成 > 0.85，该阈值在实际分数量纲下永远不可达，
# 结果每次带型号的提问都会掉进「请确认型号」的追问分支（功能死锁）。
# 现改为「绝对下限 + 相对分差」双条件：既能把唯一命中的型号正确确认下来，
# 也能在多个候选确实接近时继续追问澄清，避免误选。
NOISE_FLOOR = 0.5        # 低于此分视为噪声，直接丢弃
CONFIDENT_FLOOR = 0.6    # 第一名需达到此分，才允许自动确认
CONFIDENT_MARGIN = 0.08  # 第一名与其余候选的最小分差；小于它视为并列 → 追问澄清


def _normalize_item_name(name) -> str:
    """型号归一化：去掉空白、常见分隔符并忽略大小写，用于「同名」判断。

    项目里同一型号存在多种写法（如 BrotherHAK180烫金机 / BrotherHAK-180烫金机），
    归一化后即可视为同一个型号直接确认。
    """
    if not name:
        return ""
    text = str(name)
    for ch in (" ", "\n", "\r", "\t", "\u3000", "-", "_", "/"):
        text = text.replace(ch, "")
    return text.lower()


def _dedup_keep_order(items: List[str]) -> List[str]:
    """去重并保留原始顺序。

    原来用 list(set(...)) 去重，set 的迭代顺序不确定，会让追问选项顺序忽前忽后；
    这里保持检索分数排名的先后，行为更稳定。
    """
    seen = set()
    result = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


class NodeItemNameConfirm(NodeBase):
    name: str = "node_item_name_confirm"
    def process(self,state: QueryGraphState) -> QueryGraphState:
        #步骤1
        session_id,original_query= self._step_1_validate_param(state)
        logger.info(f"步骤1：参数校验通过")
        #步骤2
        history = get_recent_messages(session_id)
        logger.info(f"步骤2：获取到{len(history)}条历史消息")
        state["history"] = history
        #步骤3存入数据
        message_id = save_chat_message(session_id,"user", original_query)
        logger.info(f"步骤3：用户消息已初始保存，ID:{message_id}")
        #步骤4提取信息
        extract_res = self._step_4_extract_info(original_query,history)
        item_names = extract_res.get("item_names")
        rewritten_query = extract_res.get("rewritten_query",original_query)
        state["rewritten_query"] = rewritten_query
        state["item_names"] = item_names
        # 步骤5.6如果有提取到商品名，进行搜索和对齐
        align_result = {}
        if len(item_names)>0:
            query_results = self._step_5_vectorize_and_query(item_names)
            logger.info(query_results)
            align_result = self._step_6_align_item_names(query_results)
        else:
            logger.info("Node:未提取到商品名，跳过向量检索")
        state = self._step_7_check_confirmation(state,align_result,history)
        self._step_8_write_history(state,session_id,rewritten_query,message_id)
        add_done_task(state.get("session_id"), self.name, state.get("is_stream"))
        return state


    def _step_1_validate_param(self,state: QueryGraphState) -> Tuple[str,str]:
        session_id = state.get("session_id")
        if not session_id:
            raise ValueError("核心参数session_id缺失")
        original_query = state.get("original_query")
        if not original_query:
            raise ValueError("核心参数original_query缺失")
        return session_id,original_query

    def _step_4_extract_info(self,query,history)->Dict:
        try:
            chat_model = ChatOpenAI(
                model = lm_config.item_model,
                api_key=lm_config.api_key,
                base_url=lm_config.base_url,
                temperature=lm_config.llm_temperature,
                # 开启JSON标准输出模式，强制模型返回可解析的json_object
                model_kwargs={
                    "response_format":{"type":"json_object"}
                }
            )
            history_text = ""
            for msg in history:
                role = msg.get("role")
                content = msg.get("text")
                history_text += f"{role}:{content}\n"
            user_prompt = ITEM_NAME_EXTRACT_TEMPLATE.format(
                history_text = history_text,
                query=query
            )
            messages = [
                SystemMessage(content = ITEM_NAME_EXTRACT_SYSTEM_PROMPT),
                HumanMessage(content = user_prompt)
            ]
            response = chat_model.invoke(messages)
            content = response.content
            if content.startswith("```json"):
                content = content.replace("```json","").replace("```","")
            result = json.loads(content)
            if "item_names" not in result:
                result["item_names"] = []
            if "rewritten_query" not in result:
                result["rewritten_query"] = query
            result["item_names"] = [
                name.replace(" ","").replace("\n","") .replace("\t","").replace("\r","")
                for name in result["item_names"]
            ]
            return result
        except Exception as e:
            logger.error(f"大模型调用异常:{e}")
            return {"item_names": [], "rewritten_query": query}

    def _step_5_vectorize_and_query(self,item_names)->List[Dict]:
        results = []
        client = get_milvus_client()
        if not client:
            logger.error("连接Milvus失败")
            return results
        collection_name = milvus_config.item_name_collection
        embeddings = generate_embeddings(item_names)
        for i in range(len(item_names)):
            try:
                dense_vector = embeddings.get("dense")[i]
                sparse_vector = embeddings.get("sparse")[i]
                reqs = create_hybrid_search_requests(
                    dense_vector=dense_vector,
                    sparse_vector=sparse_vector,
                    limit=5
                )
                search_res = hybrid_search(
                    client=client,
                    collection_name=collection_name,
                    reqs=reqs,
                    ranker_weights=(0.8,0.2),
                    limit=5,
                    norm_score=True,
                    output_fields=["item_name"]
                )
                matches = []
                if search_res and len(search_res)>0:
                    for hit in search_res[0]:
                        matches.append({
                            "item_name": hit.get("entity",{}).get("item_name"),
                            "score":hit.get("distance"),
                        })
                results.append({
                    "extracted_names": item_names[i],
                    "matches": matches,
                })
            except Exception as e:
                logger.error(f"查询商品名 '{item_names[i]}' 时出错: {e}")
        return results

    def _step_6_align_item_names(self,query_results)->dict:
        #测试代码
        # query_results = [
        #     {
        #         'extracted_names': 'T300覆膜机',
        #         'matches': [
        #             {'item_name': 'T300覆膜机', 'score': 0.91},
        #             {'item_name': 'T300全自动覆膜机', 'score': 0.87}
        #         ]
        #     }
        # ]
        # query_results = [
        #     {
        #         'extracted_names': 'L80过油机',
        #         'matches': [
        #             {'item_name': 'L82过油烘干机', 'score': 0.42}
        #         ]
        #     }
        # ]

        # # 样例4：无匹配
        # query_results = [
        #     {
        #         'extracted_names': 'K500切割机',
        #         'matches': []
        #     }
        # ]

        confirmed_item_names:List[str] = []
        options:List[str] = []
        logger.info(f"步骤6：获得待处理的数据源：{query_results}")
        for res in query_results:
            # 兼容两种键名：_step_5 写入的是复数形式 extracted_names。
            # 早期这里只读单数 extracted_name，永远取到空串，导致「同名直判」分支形同虚设。
            extracted_name = str(
                res.get("extracted_names") or res.get("extracted_name") or ""
            ).strip()
            matches = res.get("matches") or []
            if not matches:
                continue

            # 1) 按分数降序排列，并丢弃噪声分
            ranked = sorted(
                (m for m in matches if (m.get("score") or 0) >= NOISE_FLOOR),
                key=lambda m: m.get("score") or 0,
                reverse=True,
            )
            if not ranked:
                logger.info(f"步骤6：型号「{extracted_name}」全部候选低于噪声下限，视为无匹配")
                continue
            # 1.1) 同一型号可能因重复导入在 kb_item_names 里存在多条记录（例如
            #      hak180产品安全手册 / hak180产品安全手册_new 都写了同一个型号），
            #      它们分数完全相同。若不去重，第二条会被当成「并列候选」，
            #      导致唯一命中也被迫追问澄清。这里按归一化型号名去重，只保留最高分的一条。
            deduped_ranked: List[Dict[str, Any]] = []
            seen_ranked_names = set()
            for cand in ranked:
                key = _normalize_item_name(cand.get("item_name"))
                if key in seen_ranked_names:
                    continue
                seen_ranked_names.add(key)
                deduped_ranked.append(cand)
            if len(deduped_ranked) != len(ranked):
                logger.info(
                    f"步骤6：型号「{extracted_name}」候选去重 {len(ranked)} → {len(deduped_ranked)}（同名重复记录）"
                )
            ranked = deduped_ranked
            top = ranked[0]
            top_score = top.get("score") or 0

            # 2) 用户给的型号与库里某型号归一化后完全相同 → 直接确认，不必追问
            if extracted_name:
                exact = next(
                    (m for m in ranked
                     if _normalize_item_name(m.get("item_name")) == _normalize_item_name(extracted_name)),
                    None,
                )
                if exact:
                    logger.info(f"步骤6：型号「{extracted_name}」与库内同名，直接确认")
                    confirmed_item_names.append(exact.get("item_name"))
                    continue

            # 3) 与第一名分差小于 CONFIDENT_MARGIN 的候选视为「并列」，需要用户澄清
            rivals = [
                m for m in ranked[1:]
                if top_score - (m.get("score") or 0) < CONFIDENT_MARGIN
            ]
            if top_score >= CONFIDENT_FLOOR and not rivals:
                confirmed_item_names.append(top.get("item_name"))
            else:
                for m in [top] + rivals:
                    name = m.get("item_name")
                    if name:
                        options.append(name)

        return {
            "confirmed_item_names": _dedup_keep_order(confirmed_item_names),
            "options": _dedup_keep_order(options),
        }

    def _step_7_check_confirmation(self,state,align_result,history):
        confirmed = align_result.get("confirmed_item_names",[])
        options = align_result.get("options",[])
        if confirmed:
            ids_to_update = []
            for msg in history:
                if not msg.get("item_names"):
                    mid = msg.get("_id")
                    if mid :
                        ids_to_update.append(str(mid))
            if ids_to_update:
                update_message_item_names(ids_to_update,confirmed)
            logger.info(f"步骤7：型号已确认 {confirmed}，继续检索")
            state["item_names"]=confirmed
            state["answer"] = ""
            return state
        if options:
            options_str = "、".join(options[:3])
            answer = f"您是想问以下哪个产品：{options_str}？请确定一下型号。"
            logger.info(f"步骤7：存在多个相近型号，追问用户确认 {options[:3]}")
            state["answer"] = answer
            state["item_names"] = []
            return state
        # 没有任何可用候选，按「用户是否提过型号」分两种情况处理：
        if not (state.get("item_names") or []):
            # 情况一：用户根本没提型号（如「知识库里有什么内容」这类泛问）。
            # 这里不能写死 answer，否则图会被短路到 node_answer_output，
            # 泛问类问题将永远答不出来。清空 answer 让流程继续走全库检索链路
            # —— node_search_embedding 明确支持 item_names 为空（全库搜索）。
            logger.info("步骤7：未提取到型号，转交全库检索（不短路）")
            state["answer"] = ""
            state["item_names"] = []
            return state
        # 情况二：用户明确给了型号，但库里没有任何相近项 → 明确告知，避免模型凭空编造
        logger.info(f"步骤7：型号 {state.get('item_names')} 在知识库中无相近匹配")
        state["answer"] = "抱歉，未找到相关产品，请提供准确型号以便我为您查询"
        state["item_names"] = []
        return state

    def _step_8_write_history(self,state,session_id,rewritten_query,message_id):
        if state.get("answer"):
            save_chat_message(
                session_id=session_id,
                role="assistant",
                text=state["answer"],
                rewritten_query="",
                item_names=state.get("item_names",[])
            )
        save_chat_message(
            session_id=session_id,
            role="user",
            text=state["original_query"],
            rewritten_query=rewritten_query,
            item_names=state.get("item_names",[]),
            message_id=message_id
        )
        return state



if __name__ == '__main__':
    from bson import json_util
    init_state = {
        "session_id": "test_session_003",
        "original_query":"HAK 180 烫金机怎么用？"
    }
    node_item_name_confirm = NodeItemNameConfirm()
    result = node_item_name_confirm(init_state)
    # 将返回的图状态进行json序列化
    json_state = json_util.dumps(result,ensure_ascii=False,indent=4)
    logger.info(format_json(result))





