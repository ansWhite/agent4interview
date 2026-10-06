# InsightAgent 当前已完成工作总结

## 1. 当前项目状态

`agent4interview` 当前已经被搭建成一个名为 `InsightAgent` 的面试作品 MVP。

项目定位是：

> 一个面向技术调研场景的可控、可观测、可评测 Deep Research Agent。

它现在已经包含：

- Python 后端 API
- Next.js 前端工作台
- Agent 核心状态机
- 混合检索系统
- 工具调用框架
- 本地文档索引
- SSE 实时执行轨迹
- 离线评测体系
- 单元测试、集成测试、端到端测试
- 架构文档、实验文档、演示脚本

需要注意：这次实现推进得比较快，已经超过了“逐步构建”的理想节奏。后续建议暂停新增功能，先按模块理解已有代码。

## 2. 为什么做这个项目

这个项目的面试目标是证明你具备以下能力：

1. Agent 工程能力
   - 状态机设计
   - 工具调用
   - 预算控制
   - 失败恢复
   - 实时轨迹

2. RAG / 检索算法能力
   - 文档切分
   - BM25
   - 向量检索思想
   - RRF 融合排序
   - 检索评测指标

3. 后端工程能力
   - FastAPI
   - 异步任务
   - SSE 事件流
   - SQLAlchemy 持久化
   - API schema 设计

4. 评测与实验能力
   - Recall@K
   - MRR
   - nDCG
   - Citation Precision
   - Citation Completeness
   - 端到端任务成功率

5. 前端产品表达能力
   - Agent 执行轨迹可视化
   - 证据卡片展示
   - 评测指标展示
   - 本地知识索引入口

## 3. 当前目录结构

```text
agent4interview/
├── apps/
│   ├── api/                    # FastAPI 后端服务
│   │   ├── app/
│   │   │   ├── main.py          # API 入口、路由、SSE
│   │   │   ├── service.py       # 任务执行、文档索引、评测运行
│   │   │   ├── database.py      # SQLAlchemy 持久化
│   │   │   ├── schemas.py       # 请求/响应模型
│   │   │   ├── config.py        # 配置读取
│   │   │   └── seed.py          # 内置示例语料
│   │   └── Dockerfile
│   │
│   └── web/                    # Next.js 前端工作台
│       ├── app/
│       │   ├── page.tsx         # 主页面
│       │   ├── layout.tsx       # 页面布局
│       │   └── globals.css      # 样式
│       ├── lib/
│       │   ├── api.ts           # API 请求与 SSE 订阅
│       │   ├── types.ts         # 前端类型定义
│       │   ├── format.ts        # 格式化工具
│       │   └── format.test.ts   # 前端测试
│       ├── package.json
│       └── tsconfig.json
│
├── packages/
│   ├── agent_core/              # Agent 核心逻辑
│   │   ├── workflow.py          # ResearchAgent 工作流
│   │   ├── models.py            # AgentState、Budget、Evidence 等
│   │   ├── llm.py               # Fake model 与模型协议
│   │   └── memory.py            # 长期记忆原型
│   │
│   ├── retrieval/               # 检索系统
│   │   ├── hybrid.py            # BM25 + hashed dense + RRF
│   │   └── chunking.py          # 文本切分
│   │
│   ├── tools/                   # 工具调用系统
│   │   ├── base.py              # Tool 协议
│   │   ├── registry.py          # ToolRegistry
│   │   ├── calculator.py        # 安全计算器工具
│   │   └── mcp_server.py        # MCP 适配入口
│   │
│   └── evaluation/              # 评测体系
│       ├── metrics.py           # 检索与引用指标
│       └── runner.py            # 批量评测执行器
│
├── tests/
│   ├── unit/                    # 单元测试
│   ├── integration/             # 集成测试
│   └── e2e/                     # 端到端测试
│
├── docs/
│   ├── architecture/
│   │   └── system-design.md     # 架构设计文档
│   ├── experiments/
│   │   └── evaluation-protocol.md
│   ├── demo-script.md           # 面试演示脚本
│   └── current-progress-summary.md
│
├── data/
│   └── eval_cases.jsonl         # 评测用例
│
├── infra/
│   └── compose.yaml             # Docker Compose 配置
│
├── pyproject.toml               # Python 依赖与工具配置
├── pyrightconfig.json           # Pyright 类型检查配置
├── package.json                 # Node 工作区配置
├── package-lock.json            # Node 依赖锁定
├── Makefile                     # 常用命令
├── README.md                    # 项目说明
├── .env.example                 # 环境变量模板
├── .gitignore
└── .dockerignore
```

## 4. Agent 核心流程

核心入口：

- `packages/agent_core/workflow.py`
- `packages/agent_core/models.py`
- `packages/agent_core/llm.py`

当前 Agent 工作流是：

```text
用户问题
  ↓
Question Intake
  ↓
Planner：拆解子任务
  ↓
Retriever：检索本地知识
  ↓
Evidence Grader：筛选证据
  ↓
Tool Router：必要时调用工具
  ↓
Synthesizer：基于证据生成答案
  ↓
Verifier：检查证据和引用
  ↓
持久化状态与事件
```

目前这个流程不是依赖真实大模型完成的，而是使用了一个确定性的 `DeterministicFakeModel`。

这样做的目的：

- 不依赖模型 API key
- 测试结果稳定
- 先把 Agent 工程骨架跑通
- 后续再接入真实模型时，只需要实现统一模型接口

## 5. 核心数据模型

主要文件：`packages/agent_core/models.py`

当前核心模型包括：

- `AgentState`
  - 表示一次 Agent 任务的完整状态
  - 包含问题、状态、步骤、证据、引用、答案、预算等

- `Budget`
  - 控制最大步骤数
  - 控制最大工具调用次数
  - 控制最大重试次数
  - 防止 Agent 无限循环

- `ResearchStep`
  - 表示 Planner 生成的一个子任务

- `Evidence`
  - 表示检索或工具返回的证据

- `Citation`
  - 表示答案中的引用和证据之间的对应关系

- `AgentEvent`
  - 表示 Agent 执行过程中的事件
  - 用于前端实时展示轨迹

这个模块是理解整个项目的第一重点。

## 6. 检索系统已经实现了什么

主要文件：

- `packages/retrieval/hybrid.py`
- `packages/retrieval/chunking.py`

当前检索系统包含：

1. 文本切分
   - 将长文本切成多个 chunk
   - 支持 overlap，避免上下文断裂

2. BM25 风格词项检索
   - 偏关键词匹配
   - 适合精确术语，如 `Agent`、`RRF`、`BM25`

3. hashed dense retrieval
   - 不依赖真实 embedding 模型
   - 用哈希向量模拟 dense retrieval
   - 主要用于展示向量检索接口和思想

4. RRF 排序融合
   - 将 BM25 排名和 dense 排名融合
   - 避免不同分数体系无法直接相加的问题

当前检索不是生产级语义检索，但非常适合作为面试作品中的算法讲解基础。

## 7. 工具调用系统已经实现了什么

主要文件：

- `packages/tools/base.py`
- `packages/tools/registry.py`
- `packages/tools/calculator.py`
- `packages/tools/mcp_server.py`

当前工具系统包含：

1. Tool 协议
   - 统一工具的名称、描述和调用方式

2. ToolRegistry
   - 只允许注册过的工具执行
   - 未注册工具会被拒绝
   - 支持超时控制
   - 隔离工具异常

3. CalculatorTool
   - 支持简单数学表达式
   - 使用 Python AST 解析
   - 不允许任意代码执行

4. MCP Server 适配入口
   - 预留了 MCP 协议扩展
   - 当前只是最小适配，不是重点主线

面试中这个模块可以讲：

- Agent 工具调用为什么需要 allowlist
- 为什么不能让 Agent 执行任意命令
- 工具调用失败如何降级
- MCP 在 Agent 工具生态中的作用

## 8. 后端 API 已经实现了什么

主要文件：

- `apps/api/app/main.py`
- `apps/api/app/service.py`
- `apps/api/app/database.py`
- `apps/api/app/schemas.py`

当前 API 包含：

```text
GET  /health
POST /tasks
GET  /tasks/{task_id}
GET  /tasks/{task_id}/events
POST /documents
POST /evaluations/runs
GET  /evaluations/runs/{run_id}
```

主要能力：

1. 创建 Agent 任务
2. 查询 Agent 任务状态
3. 通过 SSE 实时推送任务事件
4. 添加本地文档并加入检索器
5. 运行离线评测
6. 查询评测结果
7. 使用 SQLite 持久化任务、事件和文档

其中最重要的设计是：

```text
任务状态持久化 + AgentEvent 事件持久化 + SSE 实时推送
```

这让前端既能实时看到执行轨迹，也能在断线后重新查询任务结果。

## 9. 前端工作台已经实现了什么

主要文件：

- `apps/web/app/page.tsx`
- `apps/web/lib/api.ts`
- `apps/web/lib/types.ts`
- `apps/web/app/globals.css`

当前前端页面包含：

1. 问题输入区
2. Agent 状态显示
3. 实时执行轨迹
4. 答案展示区
5. 引用数量显示
6. 证据卡片
7. Budget 使用情况
8. 本地知识添加表单
9. 离线评测运行按钮
10. 评测指标展示

前端通过 `EventSource` 订阅后端 SSE：

```text
GET /tasks/{task_id}/events
```

这样可以实时展示：

- task_started
- node_started
- node_completed
- tool_started
- tool_completed
- task_failed
- task_finished

## 10. 评测体系已经实现了什么

主要文件：

- `packages/evaluation/metrics.py`
- `packages/evaluation/runner.py`
- `data/eval_cases.jsonl`

当前评测指标包括：

1. 检索指标
   - `Recall@K`
   - `MRR`
   - `nDCG`

2. 引用指标
   - `Citation Precision`
   - `Citation Completeness`

3. Agent 指标
   - `task_success`
   - `steps`
   - `latency_ms`
   - `warnings`

面试中可以重点讲：

> Agent 项目不能只看“能不能回答”，还要看证据是否找对、引用是否正确、任务是否可复现、失败是否可解释。

## 11. 测试与验证情况

当前已经完成以下验证。

### Python 静态检查

```powershell
uvx ruff check .
uv run --extra dev mypy apps packages
npx pyright
```

结果：全部通过。

### Python 测试

```powershell
uv run --extra dev python -m pytest
```

结果：

```text
12 passed
```

覆盖内容包括：

- Agent workflow
- retrieval
- tools
- memory
- evaluation
- repository
- e2e research journey

### 前端测试与检查

```powershell
npm --workspace apps/web run typecheck
npm run lint:web
npm run test:web
npm run build:web
```

结果：全部通过。

前端测试结果：

```text
3 passed
```

### 浏览器实测

本地启动后验证过：

- 页面可以正常加载
- 默认问题可以提交
- Agent 任务可以完成
- 执行轨迹可以显示
- 答案可以生成
- 引用和证据卡可以显示
- Budget 可以显示
- 本地文档可以索引
- 离线评测可以运行

浏览器实测中的一次评测指标示例：

```text
citation_completeness: 1.000
citation_precision: 0.250
mrr: 0.750
ndcg: 0.815
recall_at_k: 1.000
steps: 5.000
task_success: 1.000
```

## 12. 当前运行方式

### 后端启动

```powershell
uv run python -m uvicorn apps.api.app.main:app --host 127.0.0.1 --port 8000
```

### 前端启动

```powershell
npm run dev:web
```

### 访问方式

通过本机预览或浏览器访问：

```text
http://127.0.0.1:3000
```

注意：当前服务均设计为本机开发使用，不需要公网部署。

## 13. 当前环境注意事项

当前 Windows 环境中：

- `python` 命令可能是 Microsoft Store 占位符
- 项目实际通过 `uv` 创建和管理 Python 环境
- 运行测试时需要显式带上 dev extras

推荐命令是：

```powershell
uv run --extra dev python -m pytest
uv run --extra dev mypy apps packages
```

而不是直接使用：

```powershell
python -m pytest
```

另外：

- Node.js 可用
- npm 依赖已安装
- Docker 当前未安装，所以 `infra/compose.yaml` 尚未在本机验证

## 14. 当前局限

当前版本只是 MVP，不是最终形态。

主要局限：

1. 没有接入真实大模型
   - 当前使用 `DeterministicFakeModel`
   - 适合测试和演示工程流程
   - 不代表真实 LLM 推理能力

2. 检索系统是轻量实现
   - hashed dense 只是模拟向量检索
   - 未来可以替换成真实 embedding + pgvector

3. Memory 尚未进入主工作流
   - `MemoryStore` 已实现原型
   - 但当前 Agent workflow 还没有真正调用它

4. MCP 只是预留适配
   - `mcp_server.py` 已有入口
   - 但不是当前主线功能

5. 评测结果没有持久化
   - 当前评测 run 存在内存中
   - 服务重启后会丢失

6. Redis 暂未使用
   - `compose.yaml` 中有 Redis
   - 代码中还没有引入 Redis worker 或缓存

7. Docker 未验证
   - 因本机没有 Docker
   - compose 配置需要后续有 Docker 环境时再验证

8. 项目搭建节奏过快
   - 当前代码已经超过你希望的逐步学习节奏
   - 后续应该以“理解一个模块 → 再继续下一个模块”为主

## 15. 建议的后续学习顺序

接下来不要继续加功能，建议按下面顺序研究。

### 第 0 步：理解项目结构和启动方式

目标：知道每个目录干什么，能把前后端跑起来。

重点文件：

- `README.md`
- `pyproject.toml`
- `package.json`
- `apps/api/app/main.py`
- `apps/web/app/page.tsx`

### 第 1 步：理解 AgentState 和 Budget

目标：理解为什么 Agent 必须有状态、预算和事件。

重点文件：

- `packages/agent_core/models.py`

重点问题：

- 一次 Agent 任务需要保存哪些状态？
- 为什么要限制 step、tool call 和 retry？
- `AgentEvent` 为什么重要？

### 第 2 步：理解最小 Agent workflow

目标：理解一次任务从问题到答案如何执行。

重点文件：

- `packages/agent_core/workflow.py`
- `packages/agent_core/llm.py`

重点问题：

- Planner 做了什么？
- Retriever 如何返回证据？
- Synthesizer 为什么只基于 evidence 回答？
- Verifier 如何避免无证据编造？

### 第 3 步：理解检索模块

目标：理解 BM25、hashed dense 和 RRF。

重点文件：

- `packages/retrieval/hybrid.py`
- `packages/retrieval/chunking.py`
- `tests/unit/test_retrieval.py`

重点问题：

- BM25 适合什么场景？
- dense retrieval 解决什么问题？
- RRF 为什么能融合不同排序？

### 第 4 步：理解工具调用和安全边界

目标：理解 Agent 为什么不能随便执行工具。

重点文件：

- `packages/tools/base.py`
- `packages/tools/registry.py`
- `packages/tools/calculator.py`
- `tests/unit/test_tools.py`

重点问题：

- allowlist 有什么作用？
- 为什么计算器用 AST？
- 工具执行失败如何处理？

### 第 5 步：理解 FastAPI 后端

目标：理解 Agent 如何被封装成服务。

重点文件：

- `apps/api/app/main.py`
- `apps/api/app/service.py`
- `apps/api/app/schemas.py`

重点问题：

- `POST /tasks` 做了什么？
- 为什么任务要异步执行？
- 为什么要区分 API 层和 service 层？

### 第 6 步：理解 SSE 实时轨迹

目标：理解前端如何实时看到 Agent 执行过程。

重点文件：

- `apps/api/app/main.py`
- `apps/web/lib/api.ts`
- `apps/web/app/page.tsx`

重点问题：

- SSE 和普通 HTTP 有什么区别？
- EventSource 如何订阅后端事件？
- AgentEvent 如何从后端传到前端？

### 第 7 步：理解持久化

目标：理解任务、事件、文档如何保存。

重点文件：

- `apps/api/app/database.py`
- `tests/integration/test_repository.py`

重点问题：

- 为什么任务状态要落库？
- 为什么事件也要落库？
- 如何支持断线后重新查看结果？

### 第 8 步：理解评测体系

目标：理解如何证明 Agent 不是“看起来能跑”。

重点文件：

- `packages/evaluation/metrics.py`
- `packages/evaluation/runner.py`
- `data/eval_cases.jsonl`
- `docs/experiments/evaluation-protocol.md`

重点问题：

- Recall@K、MRR、nDCG 分别衡量什么？
- 引用正确率为什么重要？
- 如何做消融实验？

### 第 9 步：再考虑扩展功能

等前面都理解之后，再考虑：

- 接入真实 LLM
- 替换真实 embedding
- 接入 pgvector
- 完善 Memory
- 完善 MCP Server
- 增加更多工具
- 做更完整的实验报告

## 16. 面试时可以怎么讲

可以用下面这条主线介绍项目：

> 我做了一个面向技术调研场景的 Deep Research Agent，不只是让它能回答问题，而是重点解决 Agent 工程中的可控性、可观测性和可评测性。系统把 Agent 建模成有预算约束的状态机，通过本地知识库检索和工具调用获取证据，再生成带引用的答案，并保存完整执行轨迹。最后通过离线评测体系度量检索质量、引用质量和任务成功率。

可以展开成三个技术故事：

1. 为什么 Agent 要有状态机和预算？
2. 为什么 RAG 不能只做向量检索，还要做混合检索和评测？
3. 为什么 Agent 项目必须有 trace、引用和评测，而不是只看最终答案？

## 17. 接下来应该怎么做

建议下一步不要写新代码，而是从“第 0 步：项目结构和启动方式”开始。

建议你先重点看：

1. `README.md`
2. `apps/api/app/main.py`
3. `apps/web/app/page.tsx`
4. `packages/agent_core/models.py`

看完之后，我们再进入第 1 步：详细讲解 `AgentState` 和 `Budget`。