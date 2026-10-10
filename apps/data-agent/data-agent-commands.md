# Data-Agent 项目运行命令清单

> 整理日期：2026-10-09
> 适用环境：Windows + PowerShell / Git Bash，已安装 Docker Desktop、uv
> 本机用 curl 测试 localhost 时务必加 `--noproxy "*"`，否则会被系统代理拦截（返回 502/000）。

---

## 一、环境概览

项目包含两套并行的 Docker 环境，二者端口完全相同，**不能同时运行**。

| 环境 | 目录 | Compose 项目名 | 容器名前缀 | 数据卷 | 当前状态 |
|---|---|---|---|---|---|
| 新环境（推荐日常用） | `D:\data-agent\docker-dataagent` | `data-agent-infra` | `data-agent-*` | `data-agent-infra_*` | 运行中 |
| 旧环境（备份 / 并存用） | `D:\data-agent\docker` | `docker` | 无前缀（mysql/es 等） | `docker_*` | 已停止，容器与数据卷均保留 |

### 中间件端口表

| 服务 | 镜像 | 端口 | 用途 |
|---|---|---|---|
| MySQL | mysql:8.0 | 3306 | 元数据库 `meta` + 数仓 `dw`（自动初始化） |
| Elasticsearch | 8.19.10 + IK 中文分词（本地构建） | 9200 | 搜索 |
| Kibana | kibana:8.19.10 | 5601 | ES 可视化 |
| Qdrant | qdrant:v1.16 | 6333 / 6334 | 向量库 |
| Embedding | TEI (CPU) + bge-large-zh-v1.5 | 8081 | 文本向量化 |

### 应用入口

- 启动命令：`uv run python main.py`（在 `D:\data-agent` 下执行）
- API 文档：`http://127.0.0.1:8000/docs`
- 查询接口：`POST http://127.0.0.1:8000/api/query`（SSE 流式，body：`{"query":"自然语言问题"}`）

---

## 二、基础设施（Docker 中间件）

### A. 新环境 `data-agent-infra`（推荐日常使用）

```bash
# 进入独立环境目录
cd D:\data-agent\docker-dataagent

# 首次或镜像变动后启动（含 ES 本地构建 IK 插件镜像，首次较慢）
docker compose up -d --build

# 日常启动（已构建过，跳过构建）
docker compose up -d

# 查看运行状态
docker compose ps

# 查看日志（例如 mysql）
docker compose logs -f mysql

# 停止容器（保留数据卷，容器仅变为 Exited）
docker compose stop

# 停止并移除容器（保留数据卷，请勿加 -v）
docker compose down

# 完全停止并删除数据卷（危险！会清空所有业务数据，一般不使用）
# docker compose down -v
```

### B. 旧环境 `docker`（备份 / 并存用）

```bash
# 进入原目录
cd D:\data-agent\docker

# 启动
docker compose up -d

# 仅停止（保留容器与数据）
docker compose stop

# 恢复已停止的容器
docker compose start

# 停止并移除容器（保留数据卷，请勿加 -v）
docker compose down
```

### C. 两套环境切换（关键）

由于端口完全相同，切换时必须先停一套再起另一套：

```bash
# 例：从旧环境切到新环境
cd D:\data-agent\docker          && docker compose stop    # 停旧（不删）
cd D:\data-agent\docker-dataagent && docker compose up -d  # 起新

# 例：从新环境切回旧环境
cd D:\data-agent\docker-dataagent && docker compose stop    # 停新（不删）
cd D:\data-agent\docker          && docker compose start    # 起旧
```

---

## 三、应用本体（FastAPI）

```bash
# 进入项目根目录
cd D:\data-agent

# 首次 / 依赖变更后同步依赖（uv 会自动建 .venv）
uv sync

# 启动应用（前台运行，Ctrl+C 退出）
uv run python main.py

# 后台运行（适合长期驻留）
uv run python main.py &

# 若 8000 被占用，请改用 uvicorn 命令行显式指定端口
# ⚠️ 千万不要改成 8001！8001 是「知库·查询服务」的端口，8002 是知库嵌入、8004 是知库导入，
#    改成这些端口会直接撞车 —— 这就是「一个端口能用了另一个就不行」的典型成因。
uv run python -m uvicorn main:app --host 127.0.0.1 --port 18000
```

> 应用启动后需等待约 10-20 秒初始化完成，再发起 API 请求。
> 切换 Docker 环境后，应用需要重启以重新连接中间件。

---

## 四、冒烟测试（验证中间件连通性）

```bash
# Elasticsearch 集群健康
curl --noproxy "*" http://localhost:9200/_cluster/health?pretty

# IK 中文分词测试
curl --noproxy "*" -X POST "http://localhost:9200/_analyze" \
  -H "Content-Type: application/json" \
  -d '{"analyzer":"ik_smart","text":"查询上个月销售额最高的产品"}'

# Qdrant 集合列表
curl --noproxy "*" http://localhost:6333/collections

# Embedding 向量推理
curl --noproxy "*" -X POST "http://localhost:8081/embed" \
  -H "Content-Type: application/json" \
  -d '{"inputs":"查询上个月销售额最高的产品"}'

# MySQL 表检查
docker exec mysql mysql -uitwwy -pitwwy123 -e "USE meta; SHOW TABLES; USE dw; SHOW TABLES;"
# 新环境用：docker exec data-agent-mysql mysql -uitwwy -pitwwy123 -e "USE meta; SHOW TABLES;"
```

### 应用端到端测试

```bash
curl --noproxy "*" -N -X POST http://127.0.0.1:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query":"查询上个月总销售额"}'
```

> 链路预期：抽取关键字 → 召回列数据 → 召回指标数据 → 召回字段取值。
> 若最终返回 403，是腾讯云 lkeap 套餐包过期，属账号问题，非环境故障。

---

## 五、一键从零拉起（推荐流程）

```bash
# 1. 启动基础设施（新环境）
cd D:\data-agent\docker-dataagent
docker compose up -d --build

# 2. 同步并启动应用
cd D:\data-agent
uv sync
uv run python main.py

# 3. 验证
curl --noproxy "*" -N -X POST http://127.0.0.1:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query":"查询上个月总销售额"}'
```

---

## 六、注意事项

1. **不要给 `docker compose down` 加 `-v`**：否则数据卷（`mysql_data`、`es_data`、`qdrant_data` 等）会被一并删除，业务数据不可恢复。
2. **腾讯云 lkeap 套餐包过期**：`conf/app_config.yaml` 中的 LLM key 当前报 403，需到腾讯云 lkeap 控制台续费或更换 key，否则链路到「调大模型」一步会失败。
3. **本机代理拦截 localhost**：所有 curl 测本地服务必须加 `--noproxy "*"`。
4. **旧环境文件已被修改**：旧 `D:\data-agent\docker\docker-compose.yaml` 中已修两处坑——MySQL 卷改用 `mysql_data_v2`、ES 堆限制 `ES_JAVA_OPTS: -Xms1g -Xmx1g`，否则原 8.4 数据会导致 8.0 镜像拒绝降级、ES 会因 OOM 被杀。
5. **内存占用**：ES 限制 1G 堆，Embedding 模型（bge-large-zh-v1.5）首次加载约 2-3 分钟属正常，期间接口暂不可用。
6. **数据卷清单**（均保留未删）：
   - 新环境：`data-agent-infra_mysql_data` / `data-agent-infra_es_data` / `data-agent-infra_qdrant_data`
   - 旧环境：`docker_mysql_data` / `docker_mysql_data_v2` / `docker_es_data` / `docker_qdrant_data`
   - 其他项目：`sql_db-data`（customer-service 旧数据）
