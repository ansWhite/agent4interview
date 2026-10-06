# InsightAgent

InsightAgent 是一个面向技术调研场景的可控、可观测、可评测 Deep Research Agent。它会拆解问题、检索本地知识库、调用受限工具、校验证据并生成带引用的答案，同时保存完整执行轨迹供回放和实验对比。

## 核心能力

- 有预算边界的 planner → retrieve → grade → synthesize → verify 工作流
- BM25 + hashed dense retrieval + RRF 融合与轻量重排
- Tool allowlist、参数校验、超时与调用预算
- SSE 实时事件、trace replay 与错误恢复
- 检索和 Agent 指标、配置对比与消融实验入口
- deterministic fake model，测试和演示无需模型密钥
- Next.js 任务、证据、轨迹与评测工作台

## 本机启动

要求 Python 3.11+、Node.js 20+。复制 `.env.example` 为 `.env` 后执行：

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
npm install
.venv\Scripts\python -m uvicorn apps.api.app.main:app --host 127.0.0.1 --port 8000
```

另开终端：

```powershell
npm run dev:web
```

浏览器访问本机 `http://127.0.0.1:3000`。服务只监听回环地址。

## 运行测试

```powershell
.venv\Scripts\python -m pytest
.venv\Scripts\python -m ruff check .
.venv\Scripts\python -m mypy apps packages
npm run test:web
npm run build:web
```

## 项目结构

- `apps/api`：FastAPI、SSE、任务服务和持久化
- `apps/web`：Next.js 演示与观测界面
- `packages/agent_core`：状态机、模型抽象、预算与验证
- `packages/retrieval`：摄取、混合召回、融合和重排
- `packages/tools`：安全 Tool SDK 与 MCP 适配
- `packages/evaluation`：数据集、指标和评测 runner
- `infra`：本地容器编排
- `docs`：架构决策、实验方法和演示脚本

## 当前边界

首版使用模块化单体和进程内任务执行器，优先保证算法可解释和评测可复现。PostgreSQL/pgvector、Redis worker 与标准 MCP 服务保留明确适配边界，可按规模需求切换。所有示例数据均为本地合成数据。
