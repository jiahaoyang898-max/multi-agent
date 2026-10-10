"""知库（knowledge_base）中间件连通性探测 —— 只读，不启动业务服务、不加载大模型。

用 apps/knowledge_base/.venv 运行。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "apps" / "knowledge_base"

env = {}
for raw in (ROOT / ".env").read_text(encoding="utf-8", errors="ignore").splitlines():
    s = raw.strip()
    if not s or s.startswith("#") or "=" not in s:
        continue
    k, v = s.split("=", 1)
    env[k.strip()] = v.strip().strip('"')


def g(key, default=""):
    return env.get(key) or default


ROWS = []


def report(name, ok, detail):
    ROWS.append((name, ok, detail))
    print(f"  [{'OK  ' if ok else 'FAIL'}] {name:24} {detail}", flush=True)


def check_milvus():
    url = g("MILVUS_URL", "http://localhost:19530")
    chunks, items = g("CHUNKS_COLLECTION"), g("ITEM_NAME_COLLECTION")
    try:
        from pymilvus import MilvusClient
        cl = MilvusClient(uri=url)
        cols = cl.list_collections()
        detail = f"{url}  集合: {', '.join(cols) or '无'}"
        for cn in (chunks, items):
            if cn and cn in cols:
                n = len(cl.query(collection_name=cn, filter="", output_fields=["pk"],
                                 limit=500))
                detail += f"  | {cn}={n} 行"
        report("Milvus 向量库", True, detail)
    except Exception as e:
        report("Milvus 向量库", False, f"{type(e).__name__}: {str(e)[:150]}")


def check_mongo():
    url = g("MONGO_URL", "mongodb://localhost:27017")
    db = g("MONGO_DB_NAME", "kb001")
    try:
        from pymongo import MongoClient
        cl = MongoClient(url, serverSelectionTimeoutMS=6000)
        cl.admin.command("ping")
        names = cl[db].list_collection_names()
        detail = f"db={db}  集合 {len(names)} 个: {', '.join(names[:6]) or '无'}"
        report("MongoDB 文档库", True, detail)
        cl.close()
    except Exception as e:
        report("MongoDB 文档库", False, f"{type(e).__name__}: {str(e)[:150]}")


def check_minio():
    ep = g("MINIO_ENDPOINT", "http://localhost:9000")
    bucket = g("MINIO_BUCKET_NAME", "knowledge-base")
    try:
        from minio import Minio
        host = ep.replace("http://", "").replace("https://", "")
        cl = Minio(host, access_key=g("MINIO_ACCESS_KEY"),
                   secret_key=g("MINIO_SECRET_KEY"), secure=False)
        ok = cl.bucket_exists(bucket)
        report("MinIO 对象存储", True,
               f"{ep}  bucket='{bucket}' {'存在' if ok else '不存在'}")
    except Exception as e:
        report("MinIO 对象存储", False, f"{type(e).__name__}: {str(e)[:150]}")


def check_embedding_service():
    """知库的 BGE-M3 嵌入服务。注意：它需要 1.4GB 内存，由 PyCharm 里单独启动。"""
    base = g("EMBEDDING_SERVICE_URL", "http://127.0.0.1:8002")
    try:
        import httpx
        r = httpx.get(f"{base}/health", timeout=6)
        data = r.json() if r.status_code == 200 else {}
        report("BGE-M3 嵌入服务", r.status_code == 200,
               f"{base}  HTTP {r.status_code}  model_loaded={data.get('model_loaded')}")
    except Exception as e:
        report("BGE-M3 嵌入服务", False,
               f"{base}  未启动（需在 PyCharm 中运行 embedding_service）")


def main():
    print("=" * 88)
    print("知库（knowledge_base）中间件连通性检查")
    print("=" * 88)
    check_milvus()
    check_mongo()
    check_minio()
    check_embedding_service()
    ok = sum(1 for _, o, _ in ROWS if o)
    print("-" * 88)
    print(f"通过 {ok}/{len(ROWS)}")
    return 0 if ok == len(ROWS) else 1


if __name__ == "__main__":
    sys.exit(main())
