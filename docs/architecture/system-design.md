# 系统设计

## 设计目标

InsightAgent 将 Agent 视为一个受预算约束、可持久化和可评测的状态机。核心目标不是最大化调用次数，而是在有限步骤内生成有证据支持、可以复现的答案。

## 模块边界

```text
Next.js Workbench
        │ HTTP + SSE
        ▼
FastAPI Application ── SQLAlchemy ── SQLite / PostgreSQL
        │
        ├── ResearchAgent state machine
        │     Planner → Retriever → Evidence Grader → Synthesizer → Verifier
        │
        ├── HybridRetriever
        │     BM25 ─┐
        │     Dense ├─ RRF → relevance rerank
        │            ┘
        ├── Allowlisted Tool Registry ── optional MCP adapter
        └── Evaluation Runner ── deterministic metrics and config stamps
```

## 关键决策

1. 首版采用模块化单体。Agent 节点仍保持稳定接口，未来可把慢节点迁入 worker，不提前承担微服务治理成本。
2. 工作流由项目代码显式控制，模型只负责规划和合成；预算、终止、验证和错误恢复不交给模型自由决定。
3. 默认 hashed dense retrieval 无模型依赖，确保离线测试稳定。生产适配器可替换为 embedding 服务而不改变 RRF 和评测接口。
4. 所有任务、事件与版本信息持久化。SSE 是实时投影，数据库记录才是回放事实源。
5. 工具默认拒绝，只有注册到 allowlist 的结构化工具可以执行；首版不提供任意命令执行能力。

## 一致性与恢复

任务先以 `pending` 状态落库，再异步执行。每个事件独立持久化，最终状态写回任务记录。客户端断线后可重新读取任务，并从持久化事件重建轨迹。外部模型和工具调用需要通过超时与有界重试包装。

## 扩展点

- `ModelProvider`：接入真实模型、路由或 fallback。
- `HybridRetriever`：替换 dense encoder、接入 pgvector、增加 cross-encoder。
- `ToolRegistry`：接入企业内部 API 或独立 MCP Server。
- `EvaluationRunner`：加入 groundedness、人工标注与实验追踪后端。
- `Repository`：增加幂等键、租户、行级权限与 worker lease。
