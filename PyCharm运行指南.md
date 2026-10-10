# PyCharm 运行指南（智枢套件）

> 项目路径：`D:\ruanjian\multi-agent`
> 前提：Docker 中间件已启动（MySQL / Milvus / MongoDB / MinIO / ES / Qdrant / Embedding 共 10 个容器，当前均已运行 4 小时+）

---

## 一、打开项目后先做这一步

PyCharm 当前正在运行，本轮修改的 `.idea` 配置需要重新加载才会生效：

**`File` → `Reload All from Disk`**（或直接重启 PyCharm）

重载后，右上角运行下拉框里会出现 4 个以 ① ② ③ ④ 开头的运行配置。

---

## 二、Python 解释器：已可运行，但建议改到项目内

### 现状（已核实的隐患）

PyCharm 全局 SDK 表里这两个解释器**指向的是旧的项目副本**，不是本项目的 venv：

| SDK 名称 | 当前指向 | 应该指向 |
|---|---|---|
| `uv (data-agent)` | `D:\data-agent\.venv`（3.11.9，旧副本） | `D:\ruanjian\multi-agent\apps\data-agent\.venv`（**3.12.13**） |
| `uv (knowledge_base)` | `D:\knowledge_base\.venv`（3.11.9，旧副本） | `D:\ruanjian\multi-agent\apps\knowledge_base\.venv`（3.11.9） |

> `D:\knowledge_base` 和 `D:\data-agent` 是真实存在的旧目录（里面还留着 `hs_err_pid*.log`），
> 所以 PyCharm 不会报"解释器无效"，但**它跑的不是本项目的环境**。

### 怎么改（3 步）

`File → Settings → Project: multi-agent → Python Interpreter → Add Interpreter`
→ `Add Local Interpreter → Existing`
→ 选择 `D:\ruanjian\multi-agent\apps\data-agent\.venv\Scripts\python.exe`

知库同理，选 `apps\knowledge_base\.venv\Scripts\python.exe`。

> **注意**：4 个运行配置都已用**绝对路径**锁定各自正确的解释器（`IS_MODULE_SDK=false`），
> 所以**即使不改这一步也能正常运行**。改它只是为了代码索引 / 补全 / 跳转准确。

---

## 三、运行顺序

| 顺序 | 运行配置 | 端口 | 依赖 | 说明 |
|---|---|---|---|---|
| 1 | ① 问数后端 | **8000** | Docker 中间件 | 独立，可随时启动 |
| 2 | ② 知库·嵌入服务 BGE-M3 | **8002** | — | **必须先启动**，下面两个都依赖它 |
| 3 | ③ 知库·查询服务 | **8001** | 8002 | 等 8002 显示模型加载完成再启 |
| 4 | ④ 知库·导入服务 | **8004** | 8002 | 同上 |

**②启动较慢**（首次要加载 BGE-M3 模型，约 10~20 秒，占约 1.4 GB 内存），
控制台出现 `model_loaded` 相关日志后再启动 ③ ④。

### 不在 PyCharm 里跑的两个（Node.js 项目）

| 服务 | 目录 | 命令 |
|---|---|---|
| 问数前端 (5173) | `apps/data-agent/web` | `npm run dev` |
| 智枢工作台 (8080) | `apps/workbench` | `node server.js` |

在 PyCharm 的 Terminal 里执行即可，或单独开命令行窗口。

---

## 四、怎么确认跑起来了

| 检查项 | 地址 | 期望 |
|---|---|---|
| 问数后端 | http://127.0.0.1:8000/docs | Swagger 页面 |
| 知库·嵌入 | http://127.0.0.1:8002/health | `{"status":"ok","model_loaded":true}` |
| 知库·查询 | http://127.0.0.1:8001/health | `{"ok":true}` |
| 知库·导入 | http://127.0.0.1:8004/docs | Swagger 页面 |

浏览器能打开对应页面 = 服务正常。

---

## 五、中间件连接自检（已实测通过）

项目根目录下两个脚本，**只读探测、不写数据、不启动业务服务**：

```bash
cd D:\ruanjian\multi-agent

# 问数侧：MySQL(meta/dw) + Qdrant + Elasticsearch + Embedding
apps\data-agent\.venv\Scripts\python.exe check-conn-data-agent.py

# 知库侧：Milvus + MongoDB + MinIO + BGE-M3 嵌入服务
apps\knowledge_base\.venv\Scripts\python.exe check-conn-knowledge-base.py
```

**本轮实测结果：**

| 脚本 | 结果 | 明细 |
|---|---|---|
| `check-conn-data-agent.py` | **5 / 5** | MySQL 8.0.46（meta 4 表 / dw 5 表）· Qdrant 3 集合 · ES 8.19.10 · TEI HTTP 200 |
| `check-conn-knowledge-base.py` | **3 / 3** | Milvus 19530（kb_chunks 14 行 / kb_item_names 3 行）· MongoDB kb001 · MinIO bucket 存在 |

> 知库脚本里「BGE-M3 嵌入服务」一项会显示 FAIL —— 这是**预期**的，
> 因为它是 Python 服务，需要在 PyCharm 里点 ② 启动后才可用。

---

## 六、注意事项

1. **启动服务前先确认 Docker 中间件在跑**：
   ```bash
   docker ps
   ```
   缺任何一个容器，对应服务都会连不上数据库。

2. **内存偏紧**。当前物理内存 13.86 GB，BGE-M3 常驻约 1.4 GB，
   剩余余量不大。若启动知库服务时报 `OpenBLAS error: Memory allocation still failed`，
   说明内存被打满 —— 可先停掉不用的容器腾地方：
   ```bash
   docker stop data-agent-kibana     # 约占 680 MB，纯日志面板，平时可不跑
   ```

3. **`import_service.py` 的端口已修正为 8004**。原先文件里写死 `port=8000`，
   与问数后端撞端口；命令行启动时被 `--port 8004` 覆盖才没暴露，
   但在 PyCharm 里直接点运行就会冲突。

4. 若运行配置没出现，说明 `.idea` 被 PyCharm 的内存状态覆盖了 ——
   重启一次 PyCharm 即可。
