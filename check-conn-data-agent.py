"""问数（data-agent）中间件连通性探测 —— 只读，不启动业务服务、不写数据。

用 apps/data-agent/.venv 运行，保证驱动与实际运行时一致。

【为什么必须显式写 127.0.0.1，且必须绕开系统代理】
1. Windows 上 "localhost" 先解析到 IPv6 的 ::1，而 Docker Desktop 发布的宿主端口通常是
   IPv4。用 localhost 探测会把「没人监听」报成 asyncmy OperationalError
   (2003, WinError 1225 远程计算机拒绝网络连接)，归因困难。本脚本把 conf 里的
   localhost 家族统一改写成 127.0.0.1 —— 端口/账号/库名仍从 app_config.yaml 读，不硬编码。
2. 本机若开着 Windows 注册表系统代理（ProxyEnable=1），httpx 默认 trust_env=True 会把
   请求发给代理；服务根本没起也可能拿到 HTTP 502 / 读超时，甚至把代理转发回来的
   「别人的响应」当成自己的服务在线 —— 这就是「假绿」。脚本强制 NO_PROXY=* 并
   trust_env=False，只承认直连结果。
3. 每条自检打印「实连地址 + 服务端标识」（MySQL 版本与 @@hostname/@@port、Qdrant 版本号、
   ES 集群名与版本、TEI 模型名），连错实例时肉眼可辨。
4. MySQL 额外做硬断言：必须是 mysql:8.0 且智枢的 meta、dw 两个库都可见；否则判 FAIL
   并打印实际拿到的版本/库，避免把别人机器上的 MySQL（例如 8.4.x）当成自己的。
"""
import asyncio
import os
import socket
import sys
from pathlib import Path

# 必须在导入任何 HTTP 客户端库之前置空代理
os.environ["NO_PROXY"] = "*"
os.environ["no_proxy"] = "*"

import yaml

ROOT = Path(__file__).resolve().parent / "apps" / "data-agent"
cfg = yaml.safe_load((ROOT / "conf" / "app_config.yaml").read_text(encoding="utf-8"))

PROBE_HOST = "127.0.0.1"
LOCAL_ALIASES = {"localhost", "::1", "[::1]", "0.0.0.0"}
# 智枢 compose 用的是 mysql:8.0；其它大版本（如 8.4 / 5.7）说明连到了别人的实例
EXPECTED_MYSQL_FAMILY = "8.0"
# 智枢必须同时具备的两个库
ZHISHU_DATABASES = ("meta", "dw")
# TCP 通了但对方不是 MySQL 时，asyncmy 会一直等握手包；必须设硬超时，不能让自检挂死
MYSQL_QUERY_TIMEOUT = 15

ROWS = []


def to_local(host):
    """localhost 家族 → 显式 127.0.0.1；真正的远端主机名/IP 原样保留。"""
    h = str(host).strip().strip("[]")
    return PROBE_HOST if h.lower() in LOCAL_ALIASES else str(host).strip()


def tcp_probe(host, port, timeout=5):
    """先做纯 TCP 探测。

    实测必要性：
    1. 23306 无人监听时 socket 给出的是可读的 WinError 10061（拒绝连接），而 asyncmy
       只会吐出含义模糊的 WinError 1225；端口上若跑着非 MySQL 的监听者，asyncmy 更是会
       永久卡在等握手（本机实测会一直挂着）。所以先自己判一次，把归因拿回自己手里。
    2. 超时下限不能随便调小：本机（Docker Desktop/WSL2 转发）对未发布端口的 RST 固定要
       约 2.04 秒才回来，timeout=2 会把「没人监听」误报成「超时」。实测 4~6 秒才稳定拿到
       10061，因此默认给 5 秒。
    """
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return None
    except OSError as e:
        return e


def os_err_text(e):
    """把 Windows socket 错误翻译成人能看懂的结论（超时类异常没有 winerror）。"""
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


def mysql_problems(ver, db, dbname, visible):
    """智枢 MySQL 硬断言，返回问题列表（空列表 = 通过）。纯函数，便于单测。"""
    p = []
    if not str(ver).startswith(EXPECTED_MYSQL_FAMILY):
        p.append(f"版本不是智枢要求的 mysql:{EXPECTED_MYSQL_FAMILY}（实得 {ver}）")
    if str(db) != dbname:
        p.append(f"实际连到的库是 {db}，不是配置的 {dbname}")
    missing = [d for d in ZHISHU_DATABASES if d not in visible]
    if missing:
        p.append(f"该实例上缺少智枢需要的库 {missing}")
    return p


def redact(text):
    """绝不把配置里的口令吐进终端。"""
    out = str(text)
    for key in ("db_meta", "db_dw"):
        pw = cfg.get(key, {}).get("password")
        if pw:
            out = out.replace(str(pw), "***")
    return out


def report(name, ok, detail):
    ROWS.append((name, ok, detail))
    print(f"  [{'OK  ' if ok else 'FAIL'}] {name:24} {redact(detail)}", flush=True)


def down_hint(host, port, err_text=""):
    """HTTP 客户端的异常串又长又绕，FAIL 时补一句端口级归因；
    客户端自己已经讲清楚（10061/超时）就不重复探测，省时间也不刷屏。"""
    if any(k in str(err_text) for k in ("10061", "10060", "拒绝", "timed out", "timeout")):
        return ""
    e = tcp_probe(host, port, timeout=4)
    return "" if e is None else f"  | 端口归因: {type(e).__name__} {os_err_text(e)}"


async def check_mysql(key, label):
    c = cfg[key]
    host, port, dbname = to_local(c["host"]), int(c["port"]), c["database"]
    url = (f"mysql+asyncmy://{c['user']}:{c['password']}@{host}:{port}"
           f"/{dbname}?charset=utf8mb4")
    where = f"实连 {host}:{port}（配置 host={c['host']}）"

    probe_err = tcp_probe(host, port)
    if probe_err is not None:
        report(label, False, f"{where}  TCP 层即失败: {type(probe_err).__name__} "
                            f"{os_err_text(probe_err)}")
        return

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine
    eng = create_async_engine(url, pool_size=2, pool_pre_ping=True)
    try:
        async def _query():
            async with eng.connect() as conn:
                r = await conn.execute(text(
                    "SELECT VERSION(), DATABASE(), @@hostname, @@port, "
                    "(SELECT COUNT(*) FROM information_schema.tables "
                    " WHERE table_schema = DATABASE())"))
                ver, db, srv_host, srv_port, n = r.fetchone()

                visible = [row[0] for row in await conn.execute(text(
                    "SELECT SCHEMA_NAME FROM information_schema.schemata "
                    "WHERE SCHEMA_NAME IN ('meta','dw') ORDER BY SCHEMA_NAME"))]

                # 附带查一张核心表，确认读权限（表名来自 docker-dataagent/mysql/{meta,dw}.sql）
                core = "fact_order" if dbname == "dw" else "table_info"
                try:
                    t = await conn.execute(text(f"SELECT COUNT(*) FROM {dbname}.{core}"))
                    extra = f"核心表 {dbname}.{core} {t.scalar_one()} 行"
                except Exception as te:
                    extra = f"核心表 {dbname}.{core} 不可读({type(te).__name__})"

                ident = f"MySQL v{ver} @ {srv_host}:{srv_port}(服务端自报)"
                shown = (f"{where}  {ident}  db={db}  {n} 张表"
                         f"  智枢库可见: {visible or '无'}  {extra}")
                problems = mysql_problems(ver, db, dbname, visible)
                report(label, not problems,
                       shown + ("" if not problems else "  → FAIL: " + "；".join(problems)))

        await asyncio.wait_for(_query(), timeout=MYSQL_QUERY_TIMEOUT)
    except asyncio.TimeoutError:
        report(label, False,
               f"{where}  TCP 通但 {MYSQL_QUERY_TIMEOUT}s 内拿不到 MySQL 握手/响应"
               f" —— 该端口上跑的很可能不是 MySQL（或是别人占用的同名端口）")
    except Exception as e:
        report(label, False, f"{where}  {type(e).__name__}: {str(e)[:240]}")
    finally:
        await eng.dispose()



def check_qdrant():
    c = cfg["qdrant"]
    host, port = to_local(c["host"]), int(c["port"])
    where = f"实连 {host}:{port}（配置 host={c['host']}）"
    ident, title = "?", ""
    try:
        import httpx
        # Qdrant 根路径会自报 title/version，是判断「连到谁的 Qdrant」最直接的标识
        info = httpx.get(f"http://{host}:{port}/", timeout=8, trust_env=False).json()
        title, ident = str(info.get("title", "")), f"{info.get('title') or '?'} v{info.get('version', '?')}"
    except Exception as e:
        ident = f"版本未知({type(e).__name__})"
    try:
        from qdrant_client import QdrantClient
        cl = QdrantClient(host=host, port=port, timeout=8)
        cols = [x.name for x in cl.get_collections().collections]
        shown = f"{where}  {ident}  集合 {len(cols)} 个: {', '.join(cols) or '无（元知识未初始化）'}"
        # compose 用的是 qdrant/qdrant:v1.16；标题不对就说明端口上是别的服务
        if title and "qdrant" not in title.lower():
            report("Qdrant 向量库", False, f"{shown}  → FAIL: 根路径自报 '{title}'，不是 Qdrant")
        else:
            report("Qdrant 向量库", True, shown)
    except Exception as e:
        report("Qdrant 向量库", False,
               f"{where}  {ident}  {type(e).__name__}: {str(e)[:240]}{down_hint(host, port, str(e))}")


def check_es():
    c = cfg["es"]
    host, port = to_local(c["host"]), int(c["port"])
    where = f"实连 {host}:{port}（配置 host={c['host']}）"
    want_index = c.get("index_name")
    try:
        from elasticsearch import Elasticsearch
        es = Elasticsearch(hosts=[f"http://{host}:{port}"], request_timeout=8)
        info = es.info()
        ver = str(info["version"]["number"])
        tagline = str(info.get("tagline", ""))
        idx = list(es.indices.get_alias(index="*").keys())
        ident = (f"ES v{ver}  cluster='{info.get('cluster_name')}'"
                 f" node='{info.get('name')}'  tagline='{tagline}'")
        note = ""
        if want_index:
            note = (f"  约定索引 '{want_index}' "
                    f"{'已建' if want_index in idx else '未建（需跑 build_meta_knowledge）'}")
        shown = f"{where}  {ident}  索引: {', '.join(idx) or '无'}{note}"
        problems = []
        # compose 基底是 elasticsearch:8.19.10；版本号或 tagline 对不上就是连错了实例
        if not ver.startswith("8."):
            problems.append(f"版本不是智枢使用的 8.x（实得 {ver}）")
        if tagline and "search" not in tagline.lower():
            problems.append(f"tagline='{tagline}' 不像 Elasticsearch")
        report("Elasticsearch 取值库", not problems,
               shown + ("" if not problems else "  → FAIL: " + "；".join(problems)))
    except Exception as e:
        report("Elasticsearch 取值库", False,
               f"{where}  {type(e).__name__}: {str(e)[:240]}{down_hint(host, port, str(e))}")


def check_embedding():
    c = cfg["embedding"]
    host, port = to_local(c["host"]), int(c["port"])
    base = f"http://{host}:{port}"
    where = f"实连 {host}:{port}（配置 host={c['host']}）"
    want_model = str(c.get("model", "")).lower()
    try:
        import httpx
        r = httpx.get(f"{base}/health", timeout=8, trust_env=False)
        model = "?"
        try:
            mi = httpx.get(f"{base}/info", timeout=8, trust_env=False).json()
            m = mi.get("model")
            model = (m or {}).get("repository") if isinstance(m, dict) else m or "?"
        except Exception:
            model = "未提供 /info"
        detail = f"{where}  HTTP {r.status_code}  TEI model={model}"
        if r.status_code != 200:
            # 端口是通的（能拿到状态码），但服务不健康；再探一次端口没意义
            report("Embedding 服务(TEI)", False,
                   f"{detail}  → FAIL: /health 非 200，可能是端口上跑着别的服务")
        elif want_model and model not in ("?", "未提供 /info") \
                and want_model not in str(model).lower():
            # 端口通了但模型不是配置的那个 = 连到别人的嵌入服务
            report("Embedding 服务(TEI)", False,
                   f"{detail}  → FAIL: 模型与 app_config.yaml 的 '{c.get('model')}' 不一致")
        else:
            report("Embedding 服务(TEI)", True, detail)
    except Exception as e:
        report("Embedding 服务(TEI)", False,
               f"{where}  {type(e).__name__}: {str(e)[:240]}{down_hint(host, port, str(e))}")


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
