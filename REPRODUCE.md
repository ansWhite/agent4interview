# 复现指南（Reproduce Guide）

本文档用于**在一台全新设备上从零复现 InsightAgent**。按顺序执行即可，无需模型密钥。

- 适用平台：Windows（PowerShell）、macOS、Linux
- 预计耗时：首次约 5～10 分钟（主要花在依赖下载）
- 复现完成后可获得：可运行的 API、Web 工作台、测试与评测全通过

---

## 0. 环境要求

| 依赖 | 版本要求 | 本项目验证版本 | 必要性 |
|---|---|---|---|
| Python | **>= 3.11** | 3.14.5（`.venv` 内） | 必需 |
| Node.js | **>= 20** | 22.12.0 | 必需（Web 工作台） |
| npm | 随 Node 附带 | 11.4.1 | 必需 |
| Git | 任意较新版本 | 2.44.0 | 必需 |
| uv | 最新版 | 0.11.16 | 可选（推荐） |
| Docker | 最新版 | — | 可选（容器方式） |

> **建议 Python 使用 3.11 / 3.12 / 3.13**。本机验证环境是 3.14.5，功能正常，但 3.14 较新，个别轮子（wheel）可能尚未提供预编译包，导致从源码编译变慢或失败。若在 3.14 上安装依赖报错，换 3.12 即可。

### 检查环境

```powershell
# Windows PowerShell
python --version      # 期望 >= 3.11
node --version        # 期望 >= 20
npm --version
git --version
```

```bash
# macOS / Linux
python3 --version
node --version
npm --version
git --version
```

---

## 1. 克隆仓库

```powershell
git clone https://github.com/ansWhite/agent4interview.git
cd agent4interview
```

**关于网络**：仓库只含源码（约 0.7 MB / 62 个文件），克隆很快。若在国内直连 GitHub 出现 `Connection was reset`，为当前仓库配置代理（只影响 GitHub，不影响其他 git 服务）：

```powershell
git config http.https://github.com.proxy http://127.0.0.1:7890
```

> 端口按你自己代理软件的实际端口填写（Clash 常见 7890，V2Ray 常见 10809）。

---

## 2. 安装依赖

有两条路，**二选一**。

### 方式 A：使用 uv（推荐，可完全复现版本）

仓库内提交了 `uv.lock`，它能锁定**每一个依赖的精确版本**，这是跨设备一致性的关键。

```powershell
uv sync
```

完成后运行 Python 命令请加 `uv run` 前缀，例如：

```powershell
uv run python -m pytest
```

### 方式 B：使用标准 venv + pip

```powershell
# Windows
python -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -e ".[dev]"

# 前端依赖（在仓库根目录执行，会自动处理 apps/web 工作区）
npm install
```

```bash
# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
npm install
```

> **注意**：`pip install -e ".[dev]"` 中的 `-e`（可编辑安装）很重要。它把 `apps` 和 `packages` 注册为可导入包，否则 `import packages.agent_core` 会失败。
>
> 若 pip 下载缓慢，可临时指定镜像：
> ```powershell
> .venv\Scripts\python -m pip install -e ".[dev]" -i https://pypi.tuna.tsinghua.edu.cn/simple
> ```

---

## 3. 配置环境变量

`.env` **不是必需的**（`apps/api/app/config.py` 中所有配置项都有默认值，默认使用 `fake` 模型，无需任何 API Key）。

如果要显式配置，复制模板即可：

```powershell
# Windows
Copy-Item .env.example .env

# macOS / Linux
cp .env.example .env
```

`MODEL_PROVIDER=fake` 表示使用确定性假模型，**测试、演示和评测全部离线可跑，不消耗额度、不需要密钥**。只有接入真实模型时才需要填写 `MODEL_API_KEY`。

---

## 4. 验证复现是否成功

按顺序执行，四条全过即复现成功。

### 4.1 后端单元测试

```powershell
# 方式 A
uv run python -m pytest -q
# 方式 B
.venv\Scripts\python -m pytest -q
```

期望结果：`10 passed`（另有 2 个 e2e/integration 用例）。完整测试套件共 12 个用例。

> 若 e2e / integration 用例报 `PermissionError`，多半是系统临时目录受限或有安全软件拦截。指定一个可写目录即可：
> ```powershell
> .venv\Scripts\python -m pytest -q --basetemp=.tmp_pytest
> ```

### 4.2 前端测试与构建

```powershell
npm run test:web     # vitest
npm run build:web    # next build
```

### 4.3 启动后端 API

```powershell
# 方式 A
uv run python -m uvicorn apps.api.app.main:app --reload --host 127.0.0.1 --port 8000
# 方式 B
.venv\Scripts\python -m uvicorn apps.api.app.main:app --reload --host 127.0.0.1 --port 8000
```

启动时会**自动完成初始化**：创建 SQLite 数据库、写入种子文档、构建检索索引。首次启动无需任何迁移命令。

另开一个终端验证健康检查：

```powershell
curl.exe http://127.0.0.1:8000/health
```

期望返回：

```json
{"status":"ok","model":"deterministic-fake-v1","documents":3}
```

### 4.4 启动前端工作台

```powershell
npm run dev:web
```

浏览器打开 **http://127.0.0.1:3000** 。服务只监听回环地址（`127.0.0.1`），不会暴露到局域网。

---

## 5. 一键命令（Makefile）

仓库提供 `Makefile`，适合 macOS / Linux / Git Bash：

```bash
make install      # 安装全部依赖
make dev-api      # 启动后端
make dev-web      # 启动前端
make test         # 跑全部测试
make lint         # ruff + eslint
make typecheck    # mypy + tsc
```

---

## 6. 容器方式（可选）

```powershell
docker compose -f infra/compose.yaml up --build
```

会启动 4 个服务：PostgreSQL（pgvector）、Redis、API、Web。同样是回环地址绑定。

> 默认的本地开发不用 Docker，SQLite 足够。切换到 PostgreSQL 时需要修改 `DATABASE_URL` 并安装可选依赖：`pip install -e ".[postgres]"`。

---

## 7. 复现后能做什么

### 端到端跑一次 Agent 任务

```powershell
# 1. 创建任务（question 必填，3~4000 字符；budget 可选）
curl.exe -X POST http://127.0.0.1:8000/tasks `
  -H "Content-Type: application/json" `
  -d '{\"question\":\"可靠 Agent 为什么需要显式状态机？\"}'

# 2. 用返回的 task id 查询状态
curl.exe http://127.0.0.1:8000/tasks/<task_id>

# 3. 通过 SSE 实时观察 planner → retrieve → grade → synthesize → verify 轨迹
curl.exe -N http://127.0.0.1:8000/tasks/<task_id>/events

# 4. 新增本地知识（会触发摄取、分块与索引）
curl.exe -X POST http://127.0.0.1:8000/documents `
  -H "Content-Type: application/json" `
  -d '{\"title\":\"测试文档\",\"content\":\"这里是要被检索的内容。\",\"source\":\"local\"}'

# 5. 运行离线评测
curl.exe -X POST http://127.0.0.1:8000/evaluations/runs `
  -H "Content-Type: application/json" `
  -d '{\"name\":\"baseline\",\"cases\":[]}'
```

### 完整接口一览

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/health` | 健康检查（含模型名与文档数） |
| POST | `/tasks` | 创建研究任务（202） |
| GET | `/tasks/{id}` | 查询任务状态 |
| GET | `/tasks/{id}/events` | SSE 实时事件流 |
| POST | `/documents` | 新增本地知识文档 |
| POST | `/evaluations/runs` | 创建评测运行（202） |
| GET | `/evaluations/runs/{id}` | 查询评测结果 |

交互式 API 文档：**http://127.0.0.1:8000/docs**

---

## 8. 常见问题排查

| 现象 | 原因与解决 |
|---|---|
| `ModuleNotFoundError: No module named 'packages'` | 忘了可编辑安装。执行 `pip install -e ".[dev]"`，或在 `uv run` 前缀下运行 |
| `git clone` 报 `Connection was reset` | GitHub 网络问题。配置代理：`git config http.https://github.com.proxy http://127.0.0.1:7890` |
| 端口 8000 / 3000 被占用 | 换端口：uvicorn 加 `--port 8001`；前端改 `apps/web/package.json` 的 dev 脚本 |
| 前端请求 API 失败 | 检查 `NEXT_PUBLIC_API_BASE_URL`（默认 `http://127.0.0.1:8000`），需与后端端口一致 |
| 数据状态错乱，想重新开始 | 删除根目录 `insight_agent.db` 后重启后端，会自动重建并重新播种 |
| e2e 测试报 `PermissionError` | 用 `--basetemp=.tmp_pytest` 指定可写临时目录 |
| 依赖安装极慢或失败 | 使用国内镜像，或改用 `uv sync`（并行下载，明显更快） |
| 路径过长报错（Windows） | 将项目移到较短的路径，例如 `C:\proj\agent4interview` |

---

## 9. 重要说明

1. **不会复现的内容**：`.venv/`、`node_modules/`、`.next/`、`insight_agent.db`、`.env` 均被 `.gitignore` 排除，属于本机生成物，**克隆后按本文档重新生成即可**，这是刻意设计而非缺失。
2. **数据库无需备份**：`insight_agent.db` 是本地 SQLite 文件，删除后重启 API 会自动重建并写入种子数据。
3. **完全离线可用**：默认 `MODEL_PROVIDER=fake`，不依赖任何外部模型服务，便于评测复现与演示。
4. **安全边界**：所有服务只绑定 `127.0.0.1`，仅本机可访问。
5. **评测数据集已入库**：`data/eval_cases.jsonl` 是版本化资产，克隆后即可直接用于评测。

---

## 10. 快速自检清单

```text
[ ] git clone 成功，进入目录
[ ] Python >= 3.11，Node >= 20
[ ] 依赖安装完成（uv sync 或 pip install -e ".[dev]" + npm install）
[ ] pytest 通过（10 passed）
[ ] npm run test:web 通过
[ ] 后端 8000 启动，/health 返回 status: ok
[ ] 前端 3000 打开正常，能创建并观察任务
```
