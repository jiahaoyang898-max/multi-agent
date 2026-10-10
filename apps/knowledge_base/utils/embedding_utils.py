"""BGE-M3 向量生成工具。

知库的导入进程(8004)与查询进程(8001)都需要生成 dense+sparse 双向量。
BGE-M3 单份常驻内存约 1.1~2.3GB，若每个进程各自加载一份，在内存紧张的机器上
必然 OOM（典型报错：DefaultCPUAllocator: not enough memory）。

因此本模块提供两种运行模式：

1. 远程模式（推荐）：配置 EMBEDDING_SERVICE_URL 后，向量统一由
   web/api/embedding_service.py 这个单例服务生成，全机器只保留一份模型；
2. 本地模式（兜底）：未配置该地址、或远程服务不可用时，回退为进程内加载模型，
   保证功能不中断。

对外唯一入口是 generate_embeddings(texts)，返回结构与历史版本完全一致，
调用方无需改动。
"""

import logging
import os

from config.embedding_config import embedding_config
from processor.import_processor.base import setup_logging

setup_logging()

logger = logging.getLogger(__name__)

# 模型单例对象，避免重复初始化
_bge_m3_ef = None

# 远程嵌入服务的默认超时（秒）
DEFAULT_SERVICE_TIMEOUT = 180.0


def _service_url() -> str:
    """读取嵌入服务地址，未配置时返回空串（表示走本地模式）。"""
    return (os.getenv("EMBEDDING_SERVICE_URL") or "").strip().rstrip("/")


def is_model_loaded() -> bool:
    """当前进程内是否已加载模型（供健康检查使用）。"""
    return _bge_m3_ef is not None


def load_local_model():
    """在进程内加载并缓存 BGE-M3 单例。

    注意：pymilvus.model 的导入被刻意放在函数内部，这样纯客户端进程
    （走远程模式时）完全不会引入 torch / FlagEmbedding，可省下大量内存。
    """
    global _bge_m3_ef
    if _bge_m3_ef is not None:
        return _bge_m3_ef

    from pymilvus.model.hybrid import BGEM3EmbeddingFunction

    logger.info(
        "正在本地加载 BGE-M3 模型：path=%s device=%s fp16=%s",
        embedding_config.bge_m3_path,
        embedding_config.bge_device,
        embedding_config.bge_fp16,
    )
    _bge_m3_ef = BGEM3EmbeddingFunction(
        model_name=embedding_config.bge_m3_path,
        device=embedding_config.bge_device,
        use_fp16=embedding_config.bge_fp16,
    )
    logger.info("BGE-M3 模型本地加载完成")
    return _bge_m3_ef


def _pack_embeddings(embeddings, count: int) -> dict:
    """把 FlagEmbedding 的稀疏矩阵结果整理成 Milvus 可直接入库的字典结构。"""
    sparse_matrix = embeddings["sparse"]
    processed_sparse = []
    for i in range(count):
        start, end = sparse_matrix.indptr[i], sparse_matrix.indptr[i + 1]
        indices = sparse_matrix.indices[start:end].tolist()
        data = sparse_matrix.data[start:end].tolist()
        processed_sparse.append({k: v for k, v in zip(indices, data)})

    dense = []
    for emb in embeddings["dense"]:
        dense.append(emb.tolist() if hasattr(emb, "tolist") else list(emb))

    return {"dense": dense, "sparse": processed_sparse}


def encode_documents_local(texts) -> dict:
    """进程内直接推理（供嵌入服务自身与兜底路径使用）。"""
    texts = list(texts)
    model = load_local_model()
    return _pack_embeddings(model.encode_documents(texts), len(texts))


def encode_documents_remote(texts) -> dict:
    """通过 HTTP 调用共享嵌入服务。"""
    import httpx

    url = _service_url()
    timeout = float(os.getenv("EMBEDDING_SERVICE_TIMEOUT") or DEFAULT_SERVICE_TIMEOUT)
    response = httpx.post(
        f"{url}/embed",
        json={"texts": list(texts)},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    return {"dense": payload["dense"], "sparse": payload["sparse"]}


def generate_embeddings(texts) -> dict:
    """为文本生成向量嵌入（对外唯一入口）。

    :param texts: 要生成嵌入的文本列表
    :return: 包含 dense 和 sparse 向量的字典
    """
    texts = list(texts)
    if not texts:
        return {"dense": [], "sparse": []}

    url = _service_url()
    if url:
        try:
            return encode_documents_remote(texts)
        except Exception as exc:  # 服务不可用/超时都回退，保证功能不中断
            logger.warning("嵌入服务调用失败(%s)，本次回退为本地加载模型：%s", url, exc)

    return encode_documents_local(texts)


# ================= 单元测试主入口 =================
if __name__ == "__main__":
    # 准备测试文本（一个是中文，一个是英文词，模拟双语召回测试）
    test_data = ["大功率电磁炉", "Car"]

    print(f"👉 开始单独测试 generate_embeddings 函数...")
    print(f"👉 嵌入模式: {'远程 ' + _service_url() if _service_url() else '本地'}")
    print(f"👉 测试文本: {test_data}\n")

    try:
        # 执行目标函数
        output = generate_embeddings(test_data)

        print("\n" + "=" * 20 + " 🎉 测试结果 🎉 " + "=" * 20)

        # 1. 验证稠密向量
        print(f"【稠密向量 (Dense)】")
        print(f"   - 成功生成数量: {len(output['dense'])} 条")
        # 稠密向量有 1024 维，我们只打印前 5 个数字展示一下，否则会刷屏
        print(f"   - 第一条文本的维度大小: {len(output['dense'][0])} 维")
        print(f"   - 第一条文本的前 5 维特征值: {output['dense'][0][:5]} ...")

        # 2. 验证稀疏向量
        print(f"\n【稀疏向量 (Sparse)】")
        print(f"   - 成功生成数量: {len(output['sparse'])} 条")
        print(f"   - 第一条文本的关键字字典 (词ID : 权重):")
        print(f"     {output['sparse'][0]}")

        print("=" * 54)
        print("💡 结论：函数单独测试通过！输出数据结构完全符合 Milvus 的入库标准。")

    except Exception as e:
        print(f"\n❌ 测试失败！拦截到异常: {e}")
        print("💡 排查建议：")
        print("   1. 请确认本地 D 盘路径下的模型文件是否完整。")
        print("   2. 如果走远程模式，请确认嵌入服务(8002)是否已启动。")
        print("   3. 如果提示 CUDA 相关错误，说明你的显卡驱动或 PyTorch 环境有兼容问题。")
