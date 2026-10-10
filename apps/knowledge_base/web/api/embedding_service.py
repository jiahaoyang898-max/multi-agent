"""智枢知库 · BGE-M3 嵌入服务（单例）。

背景
----
知库的导入服务(8004)与查询服务(8001)都要生成 dense+sparse 双向量，而
BGE-M3 单份常驻内存约 1.1~2.3GB。原实现让每个进程各自加载一份模型，
在内存有限的机器上（例如 16GB 且同时跑着 Docker/IDE）必然 OOM：

    RuntimeError: [enforce fail at alloc_cpu.cpp:117] data. DefaultCPUAllocator:
    not enough memory: you tried to allocate 512004096 bytes.

本服务把模型收敛到唯一进程，其他进程通过 HTTP 共享，导入与查询互不重复加载。

接口
----
GET  /health  -> {"status": "ok", "model_loaded": bool}
POST /embed   -> {"texts": [...]}  ->  {"dense": [[...]], "sparse": [{...}]}
"""

import os

# 必须在导入 torch 之前设置线程数：BGE-M3 是推理型负载，
# 多线程只会带来线程栈与内存 arena 的额外开销，压低单进程峰值内存。
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
# 本服务自身必须走本地模型，避免自我调用形成递归
os.environ["EMBEDDING_SERVICE_URL"] = ""

import threading
from contextlib import asynccontextmanager
from typing import List

import torch
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from tool.logger import logger
from utils.embedding_utils import encode_documents_local, is_model_loaded, load_local_model

torch.set_num_threads(1)

# 推理是 CPU 密集且模型非线程安全，统一串行化，避免并发把内存顶穿
_infer_lock = threading.Lock()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动即在后台线程预热模型：让首个业务请求不必等待冷启动。

    预热失败不阻断服务启动——这样进程仍能响应 /health，
    问题会在日志里清晰暴露，而不是让整个栈起不来。
    """
    def _warmup():
        try:
            load_local_model()
            logger.info("BGE-M3 模型预热完成，嵌入服务就绪")
        except Exception as exc:
            logger.warning(f"BGE-M3 预热失败，将在首次请求时重试：{exc}", exc_info=True)

    threading.Thread(target=_warmup, name="bge-m3-warmup", daemon=True).start()
    yield


app = FastAPI(title="智枢知库-BGE-M3嵌入服务", lifespan=lifespan)


class EmbedRequest(BaseModel):
    texts: List[str]


@app.get("/health", summary="健康检查")
async def health():
    return {"status": "ok", "model_loaded": is_model_loaded()}


@app.post("/embed", summary="批量生成 dense+sparse 向量")
def embed(request: EmbedRequest):
    if not request.texts:
        return {"dense": [], "sparse": []}
    try:
        with _infer_lock:
            return encode_documents_local(request.texts)
    except Exception as exc:
        logger.error(f"向量生成失败：{exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"embedding failed: {exc}")


if __name__ == "__main__":
    uvicorn.run(app=app, host="127.0.0.1", port=8002)
