import os

from langchain_openai import ChatOpenAI

from config.lm_config import lm_config

_llm_client_cache ={}

# 单次 LLM 请求的超时与重试。
# 背景：曾经因为模型端不可用（请求发出后永不返回），且客户端未设超时，
#      导致查询流程在等 LLM 的地方无限期挂起，整个接口既不返回也不报错。
#      这里强制设置超时，让异常尽早抛出、由调用方降级，而不是拖死整条链路。
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "60"))
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "1"))


def get_llm_client(model:str|None=None,json_mode:bool=False) -> ChatOpenAI:
    m = model or lm_config.llm_model
    key=(m,json_mode)
    if key in _llm_client_cache:
        return _llm_client_cache[key]
    extra_body = {"enable_thinking":False}#是否深度思考
    model_kwargs:dict={}#模型格式
    #json格式
    if json_mode:
        model_kwargs["response_format"] = {"type":"json_object"}
    client = ChatOpenAI(
        model=m,
        temperature=lm_config.llm_temperature,
        api_key=lm_config.api_key,
        base_url=lm_config.base_url,
        extra_body=extra_body,
        model_kwargs=model_kwargs,
        timeout=LLM_TIMEOUT,
        max_retries=LLM_MAX_RETRIES
    )
    _llm_client_cache[key] = client
    return client


