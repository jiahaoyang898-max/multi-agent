"""问数（data-agent）中间件连通性探测 —— 只读，不启动业务服务、不写数据。

用 apps/data-agent/.venv 运行，保证驱动与实际运行时一致。
"""
import asyncio
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent / "apps" / "data-agent"
cfg = yaml.safe_load((ROOT / "conf" / "app_config.yaml").read_text(encoding="utf-8"))

ROWS = []


def report(name, ok, detail):
    ROWS.append((name, ok, detail))
    print(f"  [{'OK  ' if ok else 'FAIL'}] {name:24} {detail}", flush=True)


async def check_mysql(key, label):
    c = cfg[key]
    url = (f"mysql+asyncmy://{c['user']}:{c['password']}@{c['host']}:{c['port']}"
           f"/{c['database']}?charset=utf8mb4")
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine
    eng = create_async_engine(url, pool_size=2, pool_pre_ping=True)
    try:
        async with eng.connect() as conn:
            r = await conn.execute(text(
                "SELECT VERSION(), DATABASE(), "
                "(SELECT COUNT(*) FROM information_schema.tables "
                " WHERE table_schema = DATABASE())"))
            ver, db, n = r.fetchone()
            # 附带查一张核心表，确认读权限
            try:
                t = await conn.execute(text(
                    f"SELECT COUNT(*) FROM {c['database']}.fact_order"
                    if c["database"] == "dw" else
                    f"SELECT COUNT(*) FROM {c['database']}.table_info"))
                extra = f"，核心表 {t.scalar_one()} 行"
            except Exception:
                extra = ""
            report(label, True, f"MySQL {ver}  db={db}  {n} 张表{extra}")
    except Exception as e:
        report(label, False, f"{type(e).__name__}: {str(e)[:150]}")
    finally:
        await eng.dispose()


def check_qdrant():
    c = cfg["qdrant"]
    try:
        from qdrant_client import QdrantClient
        cl = QdrantClient(host=c["host"], port=c["port"], timeout=8)
        cols = [x.name for x in cl.get_collections().collections]
        report("Qdrant 向量库", True,
               f"{c['host']}:{c['port']}  集合 {len(cols)} 个: {', '.join(cols) or '无'}")
    except Exception as e:
        report("Qdrant 向量库", False, f"{type(e).__name__}: {str(e)[:150]}")


def check_es():
    c = cfg["es"]
    try:
        from elasticsearch import Elasticsearch
        es = Elasticsearch(hosts=[f"http://{c['host']}:{c['port']}"], request_timeout=8)
        info = es.info()
        idx = list(es.indices.get_alias(index="*").keys())
        report("Elasticsearch 取值库", True,
               f"v{info['version']['number']}  索引: {', '.join(idx) or '无'}")
    except Exception as e:
        report("Elasticsearch 取值库", False, f"{type(e).__name__}: {str(e)[:150]}")


def check_embedding():
    c = cfg["embedding"]
    base = f"http://{c['host']}:{c['port']}"
    try:
        import httpx
        r = httpx.get(f"{base}/health", timeout=8)
        report("Embedding 服务(TEI)", r.status_code == 200,
               f"{base}  HTTP {r.status_code}")
    except Exception as e:
        report("Embedding 服务(TEI)", False, f"{type(e).__name__}: {str(e)[:150]}")


async def main():
    print("=" * 88)
    print("问数（data-agent）中间件连通性检查")
    print("=" * 88)
    await check_mysql("db_meta", "MySQL · meta 库")
    await check_mysql("db_dw", "MySQL · dw 库")
    check_qdrant()
    check_es()
    check_embedding()
    ok = sum(1 for _, o, _ in ROWS if o)
    print("-" * 88)
    print(f"通过 {ok}/{len(ROWS)}")
    return 0 if ok == len(ROWS) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
