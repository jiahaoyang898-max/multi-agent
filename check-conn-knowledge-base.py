"""知库（knowledge_base）中间件连通性探测 —— 只读，不启动业务服务、不加载大模型。

用 apps/knowledge_base/.venv 运行。

【为什么必须显式写 127.0.0.1，且必须绕开系统代理】
1. Windows 上 "localhost" 先解析到 IPv6 的 ::1，而 Docker Desktop 发布的宿主端口通常是
   IPv4。用 localhost 探测会把「没人监听」报成 WinError 1225 / 10061，归因困难。
   本脚本把配置里的 localhost 家族统一改写成 127.0.0.1（端口一律沿用 .env，不硬编码）。
2. 本机注册表开着系统代理（ProxyEnable=1）时，httpx 默认 trust_env=True 会把请求发给代理。
   服务根本没起也可能拿到 HTTP 502 或读超时，甚至把代理转发回来的「别人的响应」当成
   自己的服务在线 —— 这就是「假绿」。所以脚本强制 NO_PROXY=* 且 trust_env=False，
   只承认直连结果。
3. 每条自检都打印「实连地址 + 服务端标识（版本/集合/库名）」，连错实例时肉眼可辨。
"""
import os
import re
import socket
import sys
from pathlib import Path

# 必须在导入任何 HTTP 客户端库之前置空代理
os.environ["NO_PROXY"] = "*"
os.environ["no_proxy"] = "*"

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


PROBE_HOST = "127.0.0.1"
LOCAL_ALIASES = {"localhost", "::1", "[::1]", "0.0.0.0"}
_URL_RE = re.compile(
    r"^(?P<scheme>[a-zA-Z][a-zA-Z0-9+.-]*://)?"
    r"(?P<userinfo>[^@/?#\s]*@)?"
    r"(?P<host>\[[^\]]*\]|[^:/?#\s]+)"
    r"(?P<rest>.*)$"
)


def to_local(endpoint):
    """把 localhost/::1 一类主机名换成显式 127.0.0.1；真正的远端地址原样保留，端口与路径不改。"""
    endpoint = endpoint.strip()
    m = _URL_RE.match(endpoint)
    if not m:
        return endpoint
    host = m.group("host")
    if host.lower() not in LOCAL_ALIASES:
        return endpoint
    # [::1] 这类带方括号的写法改写后不再需要方括号
    return f"{m.group('scheme') or ''}{m.group('userinfo') or ''}{PROBE_HOST}{m.group('rest') or ''}"


def target(endpoint):
    """提取 host:port 供打印（绝不带 user:password），便于肉眼确认实际连到了哪。"""
    m = _URL_RE.match(endpoint.strip())
    if not m:
        return endpoint
    rest = m.group("rest") or ""
    port = re.match(r"^:(\d+)", rest)
    return f"{m.group('host').strip('[]')}{(':' + port.group(1)) if port else ''}"


ROWS = []


def tcp_probe(host, port, timeout=5):
    """纯 TCP 层探测：客户端库的报错常常含义模糊（如 Milvus 的 illegal connection params），
    先用 socket 判一次，把「没人监听 / 超时 / 被拦」讲清楚。

    超时下下限不能调小：本机（Docker Desktop/WSL2 转发）对未发布端口的 RST 固定要约
    2.04 秒才回来，timeout=2 会把「没人监听」误报成「超时」；实测 4~6 秒才稳定拿到 10061。
    """
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return None
    except OSError as e:
        return e


def os_err_text(e):
    we = getattr(e, "winerror", None)
    if isinstance(e, TimeoutError) or we in (10060, 10065):
        return (f"连接超时（{type(e).__name__}: {e}）—— 端口没人应答：容器未起，"
                f"或被防火墙/安全软件静默丢包")
    table = {
        10061: "该端口上没有监听者（容器未起，或宿主端口没发布）",
        10013: "权限被拒绝（防火墙或杀软拦截）",
        11001: "主机名解析失败",
    }
    hint = table.get(we, "")
    body = f"[WinError {we}] {str(e).split(']')[-1].strip()}" if we else str(e)
    return f"{body}{('：' + hint) if hint else ''}"


def down_hint(url_or_endpoint, err_text=""):
    """FAIL 时补一句端口级归因；客户端自己已讲清楚（10061/超时）就不重复探测。"""
    if any(k in str(err_text) for k in ("10061", "10060", "拒绝", "timed out", "timeout")):
        return ""
    t = target(url_or_endpoint)
    host, _, port = t.partition(":")
    if not port:
        return ""
    e = tcp_probe(host, port, timeout=4)
    return "" if e is None else f"  | 端口归因: {type(e).__name__} {os_err_text(e)}"


def report(name, ok, detail):
    ROWS.append((name, ok, detail))
    print(f"  [{'OK  ' if ok else 'FAIL'}] {name:24} {detail}", flush=True)


def check_milvus():
    raw = g("MILVUS_URL", "http://127.0.0.1:19530")
    url = to_local(raw)
    chunks, items = g("CHUNKS_COLLECTION"), g("ITEM_NAME_COLLECTION")
    try:
        from pymilvus import MilvusClient
        cl = MilvusClient(uri=url)
        cols = cl.list_collections()
        try:
            ident = f"Milvus v{cl.get_server_version()}"
        except Exception as e:
            ident = f"Milvus 版本未知({type(e).__name__})"
        detail = f"实连 {target(url)}（配置值 {raw}）  {ident}  集合: {', '.join(cols) or '无'}"
        bad = []
        for cn in (chunks, items):
            if not cn:
                continue
            if cn in cols:
                n = len(cl.query(collection_name=cn, filter="", output_fields=["pk"],
                                 limit=500))
                detail += f"  | {cn}={n} 行"
            else:
                bad.append(cn)
        if bad:
            report("Milvus 向量库", False,
                   f"{detail}  | 缺少本库约定的集合 {bad}，疑似连到别的 Milvus 实例")
        else:
            report("Milvus 向量库", True, detail)
    except Exception as e:
        report("Milvus 向量库", False,
               f"实连 {target(url)}（配置值 {raw}）  {type(e).__name__}: {str(e)[:240]}"
               f"{down_hint(url, str(e))}")


def check_mongo():
    raw = g("MONGO_URL", "mongodb://127.0.0.1:27017")
    url = to_local(raw)
    db = g("MONGO_DB_NAME", "kb001")
    try:
        from pymongo import MongoClient
        cl = MongoClient(url, serverSelectionTimeoutMS=6000)
        cl.admin.command("ping")
        addr = cl.address or ("?", "?")
        try:
            ver = cl.server_info().get("version", "?")
        except Exception:
            ver = "?"
        names = cl[db].list_collection_names()
        detail = (f"实连 {addr[0]}:{addr[1]}（配置值 {raw}）  MongoDB v{ver}"
                  f"  db={db}  集合 {len(names)} 个: {', '.join(names[:6]) or '无'}")
        if names:
            report("MongoDB 文档库", True, detail)
        else:
            report("MongoDB 文档库", True, detail + "  | 注：该库暂无集合（知库未导入过文档）")
        cl.close()
    except Exception as e:
        report("MongoDB 文档库", False,
               f"实连 {target(url)}（配置值 {raw}）  {type(e).__name__}: {str(e)[:240]}"
               f"{down_hint(url, str(e))}")


def check_minio():
    raw = g("MINIO_ENDPOINT", "http://127.0.0.1:29000")
    ep = to_local(raw)
    bucket = g("MINIO_BUCKET_NAME", "knowledge-base")
    try:
        from minio import Minio
        host = ep.replace("http://", "").replace("https://", "")
        cl = Minio(host, access_key=g("MINIO_ACCESS_KEY"),
                   secret_key=g("MINIO_SECRET_KEY"), secure=False)
        exists = cl.bucket_exists(bucket)
        try:
            all_buckets = [b.name for b in cl.list_buckets()]
            scope = f"该实例共 {len(all_buckets)} 个桶: {', '.join(all_buckets[:6])}"
        except Exception:
            scope = "桶清单不可读"
        detail = (f"实连 {host}（配置值 {raw}）  bucket='{bucket}' "
                  f"{'存在' if exists else '不存在'}  | {scope}")
        if exists:
            report("MinIO 对象存储", True, detail)
        else:
            report("MinIO 对象存储", False, detail + "（未建桶，导入会失败）")
    except Exception as e:
        report("MinIO 对象存储", False,
               f"实连 {target(ep)}（配置值 {raw}）  {type(e).__name__}: {str(e)[:240]}"
               f"{down_hint(ep, str(e))}")


def check_embedding_service():
    """知库的 BGE-M3 嵌入服务（8102）。

    它是唯一常驻 1.4~2.3GB 内存的进程，`npm start` 会按 services.json 的 kb-embedding 拉起，
    也可按「智枢套件-一键运行与端口速查.md」§3 终端 1 手动起。
    判绿条件是 HTTP 200 且 model_loaded=true —— 进程活着但模型没加载，等于没就绪。
    """
    raw = g("EMBEDDING_SERVICE_URL", "http://127.0.0.1:8102")
    base = to_local(raw).rstrip("/")
    try:
        import httpx
        r = httpx.get(f"{base}/health", timeout=6, trust_env=False)
        data = r.json() if r.status_code == 200 else {}
        loaded = data.get("model_loaded")
        ident = (f"status={data.get('status')} model_loaded={loaded}"
                 if data else f"响应体非预期: {str(data)[:60]}")
        if r.status_code != 200:
            report("BGE-M3 嵌入服务", False,
                   f"实连 {target(base)}（配置值 {raw}）  HTTP {r.status_code}  {ident}")
        elif "model_loaded" not in data:
            # 200 但不是本服务的响应结构 —— 极可能是端口上跑着别的服务
            report("BGE-M3 嵌入服务", False,
                   f"实连 {target(base)}（配置值 {raw}）  HTTP 200 但响应无 model_loaded 字段，"
                   f"疑似端口上不是嵌入服务（{ident}）")
        elif not loaded:
            # 进程活着但 2.2GB 的模型没加载进来，此时向量化仍会回退本地加载，不能算通过
            report("BGE-M3 嵌入服务", False,
                   f"实连 {target(base)}（配置值 {raw}）  HTTP 200  但 model_loaded=false："
                   f"预热未完成或内存不足（约需 1.4~2.3GB），不能算就绪")
        else:
            report("BGE-M3 嵌入服务", True,
                   f"实连 {target(base)}（配置值 {raw}）  HTTP 200  {ident}")
    except Exception as e:
        report("BGE-M3 嵌入服务", False,
               f"实连 {target(base)}（配置值 {raw}）  {type(e).__name__}: {str(e)[:120]}"
               f"{down_hint(base, str(e))}")


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
