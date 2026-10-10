# -*- coding: utf-8 -*-
"""智枢套件 · 端到端冒烟测试

覆盖：
  1. 六个服务的健康检查
  2. 嵌入服务（BGE-M3，8002）双向量自检
  3. 问数（data-agent）自然语言问数，重点验证「相对时间查询不再匹配不到行」
  4. 知库（knowledge_base）型号确认 + 检索 + 生成
  5. 知库导入链路（可选，见 --with-import）

仅使用标准库，可直接运行。

用法：
  python smoke-test.py                              # 默认：健康 + 嵌入 + 问数 + 知库查询
  python smoke-test.py --with-import "样例.pdf"      # 额外跑一遍完整导入链路
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid

TIMEOUT = 300

SERVICES = [
    ("智枢工作台", 8080, "/"),
    ("问数前端", 5173, "/"),
    ("问数后端", 8000, "/docs"),
    ("知库·嵌入服务", 8002, "/health"),
    ("知库后端·查询", 8001, "/health"),
    ("知库后端·导入", 8004, "/docs"),
]

# (用例名, 提问, 断言说明)
DATA_AGENT_CASES = [
    ("各区域销量对比", "各区域销量对比"),
    ("本月总销售额", "本月总销售额"),
    ("最近30天订单数", "最近30天订单数"),
    ("哪个产品销量最高", "哪个产品销量最高"),
    ("上个月总销售额", "查询上个月总销售额"),
    ("今年总销售额", "今年总销售额"),
    ("上季度各区域销售额", "上季度各区域销售额"),
]

KB_CASES = [
    ("明确型号-无线网关", "H3CLA2608 无线网关怎么恢复出厂设置"),
    ("明确型号-烫金机", "HAK180烫金机怎么用"),
    ("泛问-无型号", "知识库里有哪些产品文档"),
]


def http(url, data=None, headers=None, timeout=TIMEOUT):
    body = None
    if data is not None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read().decode("utf-8", errors="replace")


def health_checks():
    print("=" * 92)
    print("一、服务健康检查")
    print("=" * 92)
    ok_count = 0
    for name, port, path in SERVICES:
        url = f"http://127.0.0.1:{port}{path}"
        start = time.time()
        try:
            status, _ = http(url, timeout=15)
            cost = time.time() - start
            flag = "OK  " if status < 400 else "WARN"
            if status < 400:
                ok_count += 1
            print(f"  [{flag}] {name:16} :{port:<5} HTTP {status}  ({cost:.1f}s)")
        except Exception as e:
            print(f"  [FAIL] {name:16} :{port:<5} {type(e).__name__}: {str(e)[:60]}")
    print(f"  -> {ok_count}/{len(SERVICES)} 个服务可达\n")
    return ok_count


def run_embedding_service():
    """嵌入服务自检：验证 dense 维度与 sparse 词权重都正常返回。"""
    print("=" * 92)
    print("二、知库·嵌入服务（BGE-M3 :8002）")
    print("=" * 92)
    payload = {"texts": ["大功率电磁炉", "H3CLA2608室内无线网关"]}
    start = time.time()
    try:
        _, raw = http(
            "http://127.0.0.1:8002/embed",
            data=payload,
            headers={"Content-Type": "application/json"},
            timeout=120,
        )
    except Exception as e:
        print(f"  [FAIL] /embed 请求异常 {type(e).__name__}: {str(e)[:70]}\n")
        return 0
    cost = time.time() - start

    try:
        data = json.loads(raw)
        dense, sparse = data["dense"], data["sparse"]
    except Exception:
        print(f"  [FAIL] 响应无法解析：{raw[:80]}\n")
        return 0

    ok = len(dense) == 2 and len(dense[0]) == 1024 and all(len(s) > 0 for s in sparse)
    if ok:
        print(f"  [OK  ] 向量生成 {cost:5.1f}s  dense={len(dense)}x{len(dense[0])}  "
              f"sparse[0] 非零项={len(sparse[0])}")
    else:
        print(f"  [FAIL] 向量结构异常：dense={len(dense)} 维={len(dense[0]) if dense else 0} "
              f"sparse 非零项={[len(s) for s in sparse]}")
    print(f"  -> {1 if ok else 0}/1 项嵌入自检通过\n")
    return 1 if ok else 0


def http_multipart(url, file_path, field="files", timeout=TIMEOUT):
    """最小 multipart/form-data 上传（仅依赖标准库）。

    注意：文件名刻意保持 ASCII —— 非 ASCII 文件名在 multipart 头里的编码
    依赖服务端解析实现，容易变成乱码，不适合做稳定的冒烟用例。
    """
    boundary = "----smoke" + uuid.uuid4().hex
    filename = os.path.basename(file_path)
    with open(file_path, "rb") as fp:
        content = fp.read()
    body = b"".join([
        f"--{boundary}\r\n".encode(),
        f'Content-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'.encode(),
        b"Content-Type: application/octet-stream\r\n\r\n",
        content,
        b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ])
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read().decode("utf-8", errors="replace")


def run_import(file_path):
    """完整导入链路：上传 → 轮询状态直到 completed。

    重点回归「主体名称识别」节点——历史故障点（BGE-M3 本地加载 OOM）。

    注意：本用例会向知识库真实写入文档。若传入的是已导入过的同名文件，
    服务端按 file_title 先删后插，不会产生重复文档。
    """
    print("=" * 92)
    print("五、知库导入链路（knowledge_base :8004）")
    print("=" * 92)
    if not os.path.exists(file_path):
        print(f"  [FAIL] 文件不存在：{file_path}\n")
        return 0

    print(f"  待导入文件：{os.path.basename(file_path)}")
    start = time.time()

    try:
        _, raw = http_multipart("http://127.0.0.1:8004/upload", file_path)
        task_ids = json.loads(raw).get("task_ids") or []
        if not task_ids:
            print(f"  [FAIL] 未返回 task_id：{raw[:100]}\n")
            return 0
        task_id = task_ids[0]
    except Exception as e:
        print(f"  [FAIL] 上传异常 {type(e).__name__}: {str(e)[:80]}\n")
        return 0

    print(f"  上传成功 task_id={task_id}，等待流水线完成…")
    status, done, running = "processing", [], []
    deadline = time.time() + 900
    while time.time() < deadline:
        time.sleep(15)
        try:
            _, raw = http(f"http://127.0.0.1:8004/status/{task_id}", timeout=20)
            info = json.loads(raw)
        except Exception as e:
            print(f"  [WARN] 状态查询失败，重试：{type(e).__name__}")
            continue
        status = info.get("status")
        done = info.get("done_list") or []
        running = info.get("running_list") or []
        print(f"    [{time.time()-start:6.1f}s] {status:10} 已完成 {len(done)} 节点"
              f"{'，进行中：' + '、'.join(running) if running else ''}")
        if status in ("completed", "failed"):
            break

    cost = time.time() - start
    if status == "completed":
        print(f"  [OK  ] 导入完成 {cost:5.1f}s  节点：{'→'.join(done)}")
        print(f"  -> 1/1 条导入用例通过\n")
        return 1
    print(f"  [FAIL] 导入未完成 {cost:5.1f}s  status={status}  节点：{'→'.join(done)}\n")
    return 0


def run_data_agent():
    print("=" * 92)
    print("三、问数（data-agent）")
    print("=" * 92)
    passed = 0
    for name, question in DATA_AGENT_CASES:
        payload = {"query": question}
        start = time.time()
        try:
            _, raw = http(
                "http://127.0.0.1:8000/api/query",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
        except Exception as e:
            print(f"  [FAIL] {name:18} 请求异常 {type(e).__name__}: {str(e)[:70]}")
            continue
        cost = time.time() - start

        stages, result, error = [], None, None
        for line in raw.splitlines():
            if not line.startswith("data:"):
                continue
            try:
                obj = json.loads(line[5:].strip())
            except Exception:
                continue
            if "stage" in obj:
                stages.append(obj["stage"])
            if "result" in obj:
                result = obj["result"]
            if "error" in obj:
                error = obj["error"]

        if error:
            print(f"  [FAIL] {name:18} {cost:5.1f}s  error={error}")
            continue
        if not result:
            print(f"  [FAIL] {name:18} {cost:5.1f}s  未返回 result（阶段：{'→'.join(stages)}）")
            continue
        # 判定：result 里必须有非空行且不是全 null
        rows = result if isinstance(result, list) else [result]
        non_empty = [r for r in rows if r]
        has_value = any(
            v not in (None, "", []) for r in non_empty for v in (r.values() if isinstance(r, dict) else [r])
        )
        if has_value:
            passed += 1
            preview = json.dumps(rows[:2], ensure_ascii=False)
            print(f"  [OK  ] {name:18} {cost:5.1f}s  {preview[:100]}")
        else:
            print(f"  [FAIL] {name:18} {cost:5.1f}s  结果为空（匹配不到数据行）：{rows}")
    print(f"  -> {passed}/{len(DATA_AGENT_CASES)} 条问数用例返回了有效数据\n")
    return passed


def run_knowledge_base():
    print("=" * 92)
    print("四、知库查询（knowledge_base :8001）")
    print("=" * 92)
    passed = 0
    for name, question in KB_CASES:
        payload = {"query": question, "session_id": f"smoke_{abs(hash(name)) % 10**8}", "is_stream": False}
        start = time.time()
        try:
            _, raw = http(
                "http://127.0.0.1:8001/query",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
        except Exception as e:
            print(f"  [FAIL] {name:18} 请求异常 {type(e).__name__}: {str(e)[:70]}")
            continue
        cost = time.time() - start
        try:
            answer = (json.loads(raw).get("answer") or "").strip()
        except Exception:
            print(f"  [FAIL] {name:18} {cost:5.1f}s  响应无法解析：{raw[:80]}")
            continue

        # 判定：必须有实质回答，且不能是「请确定一下型号」这类退化追问
        is_ask_back = "请确定一下型号" in answer
        if answer and not is_ask_back:
            passed += 1
            print(f"  [OK  ] {name:18} {cost:5.1f}s  长度{len(answer):<5} {answer[:60]!r}")
        elif is_ask_back:
            print(f"  [FAIL] {name:18} {cost:5.1f}s  退化为追问：{answer[:60]!r}")
        else:
            print(f"  [FAIL] {name:18} {cost:5.1f}s  答案为空")
    print(f"  -> {passed}/{len(KB_CASES)} 条知库用例返回了实质回答\n")
    return passed


if __name__ == "__main__":
    import_file = None
    if "--with-import" in sys.argv:
        idx = sys.argv.index("--with-import")
        if idx + 1 < len(sys.argv):
            import_file = sys.argv[idx + 1]
        else:
            print("用法：python smoke-test.py --with-import <文件路径>\n")
            sys.exit(2)

    t0 = time.time()
    ok = health_checks()
    emb = run_embedding_service()
    da = run_data_agent()
    kb = run_knowledge_base()
    imp = run_import(import_file) if import_file else None

    print("=" * 92)
    summary = (
        f"汇总：服务可达 {ok}/{len(SERVICES)} | 嵌入自检 {emb}/1 | "
        f"问数 {da}/{len(DATA_AGENT_CASES)} | 知库查询 {kb}/{len(KB_CASES)}"
    )
    if imp is not None:
        summary += f" | 知库导入 {imp}/1"
    print(summary)
    print(f"总耗时 {time.time()-t0:.1f}s")
    print("=" * 92)

    total_ok = (
        ok == len(SERVICES)
        and emb == 1
        and da == len(DATA_AGENT_CASES)
        and kb == len(KB_CASES)
        and (imp is None or imp == 1)
    )
    sys.exit(0 if total_ok else 1)
