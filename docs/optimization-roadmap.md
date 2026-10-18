# InsightAgent 后续优化方案

> 基于 MVP 现状的五阶段演进路线。每个阶段独立可交付，按优先级排序，可逐项落地。

## 总览

| 阶段 | 主题 | 核心改动 | 优先级 |
|------|------|---------|--------|
| P0 | 检索落地化 | 文档入库 pgvector + DeepSeek 联网检索 | 高 |
| P1 | RAG 真实化 | 真实 embedding + 向量库 + 重排 | 高 |
| P2 | Verifier 强化 | Reflection 范式 LLM 复核 | 中 |
| P3 | 工具生态扩展 | 确定性 tool 集合 + Skill + MCP | 中 |
| P4 | Agent 范式升级 | LangGraph 显式图 + ReAct 循环 | 中 |

---

## P0：检索落地化

### 现状问题

1. 语料硬编码在 `apps/api/app/seed.py`，只有 4 篇演示文档，无法承载真实知识库
2. `HybridRetriever` 是纯内存字典，服务重启全丢，文档规模上千后 BM25 全量扫描性能崩溃
3. 只能检索本地，无法回答知识库外的问题（时效性问题完全失效）

### 目标架构

```
                     ┌─────────────────────────────┐
                     │        Retriever 接口         │
                     └──────┬──────────┬───────────┘
                            │          │
                  ┌─────────▼───┐  ┌───▼──────────┐
                  │  本地混合检索 │  │ DeepSeek 联网  │
                  │ (pgvector)  │  │ search + fetch │
                  └─────────────┘  └───────────────┘
                            │          │
                            └────┬─────┘
                                 ▼
                        RRF 融合 + 证据去重
                        (local + web 两种 source)
```

### 改动 1：文档持久化与真实检索库

| 现状 | 目标 |
|------|------|
| `seed.py` 硬编码 | 独立的数据导入管道（API 上传 / 文件夹扫描 / URL 批量抓取） |
| 内存 dict | PostgreSQL + `pgvector` 扩展 |
| 全量扫描 BM25 | PostgreSQL `tsvector` 全文索引（或 Elasticsearch） |

关键设计：

- 表结构：`documents(id, title, content, source, metadata)` + `chunks(doc_id, chunk_index, content, embedding vector(N), tsv tsvector)`
- BM25 用 `ts_rank` 近似替代，向量用 pgvector 的 `<=>` 余弦距离 + HNSW 索引
- `HybridRetriever` 保持接口不变（`search(query, limit) -> list[SearchHit]`），内部实现换成 SQL 查询——上层 workflow 零改动
- 已有的 `postgres` optional 依赖（`asyncpg` + `pgvector`）就是为此预留的

### 改动 2：接入 DeepSeek 联网搜索与抓取

DeepSeek 提供两个工具 API（与 Chat API 同一个 Key，Bearer 认证）：

**Search API**（`POST /v1/tools/search`）：

```python
payload = {
    "query": "LangGraph 条件边 路由",          # 必填，1~128 字符，支持 site: 等语法
    "count": 8,                               # 返回条数 1~50
    "need_content": False,                    # True 时返回网页正文
    "ori_question": "LangGraph 的条件边如何路由？",  # 原始问题，帮助理解意图
}
# 响应字段：
# rerank_score: 0~3，>=1.5 为优质结果（可直接当 Evidence.score 用）
# snippet: 100~200 字符短摘要（前端展示）
# summary: 600~800 字符长摘要（喂给 LLM）
# content: 网页正文（need_content=True 时）
# url / title / site_name / date / authority(0~4)
```

**Fetch API**（`POST /v1/tools/fetch`）：

```python
payload = {"url": "https://example.com/article"}   # <=8192 字符，HTTP/HTTPS
# 响应：{"title": "...", "content": "...Markdown 正文..."}
```

实现方案——封装为两个 `Tool`（复用现有 ToolRegistry 安全壳）：

```
packages/tools/web_search.py    → WebSearchTool
packages/tools/web_fetch.py     → WebFetchTool
```

`WebSearchTool.invoke({"query": ...})` 内部调用 Search API，把每条结果转成 `Evidence`：

- `document_id` = `web:{url 的 hash}`
- `source` = `web://search`
- `score` = `rerank_score / 3`（归一化到 0~1，与本地检索可比）
- `content` = `summary`（600~800 字符正适合作为证据，不需要 need_content）

**进阶：search → fetch 二段式抓取**

对 `rerank_score >= 1.5` 且信息不足的头部结果，先返回 URL 列表，再由 workflow 决定是否对 top 1~2 条调 `WebFetchTool` 拉取 Markdown 正文，切分后转成多条 `Evidence`（`source = web://fetch`）。这形成 Deep Research 的"多轮检索"能力。

**路由决策**：什么时候联网？

- 本地检索 top1 score 低于阈值（如 0.3）→ 知识库覆盖不足 → 触发 web 检索
- 问题带时效性关键词（"最新"、"2026"、"现在"）→ 直接 web 优先
- 消融实验：local only / web only / hybrid 三组对比 Recall@K（正好充实 `evaluation-protocol.md` 的实验矩阵）

**安全边界**（面试重点）：

- 网页内容 = 不可信数据，prompt injection 防御：fetch 回来的正文只进 Evidence，永不拼接进 system prompt
- 域名 allowlist/denylist（企业内落地常见诉求：禁竞品站点、只信白名单源）
- URL 校验：拒绝内网地址（SSRF 防护，`10.x` / `127.x` / `169.254.x` / `::1`）

---

## P1：向量检索真实化（RAG 落地）

### 现状问题

`_embed()` 用 blake2b 哈希模拟向量，"安全边界"和"安全限制"的向量毫无关系，语义召回实际上是假的。

### 方案

三步走：

**1. 引入真实 embedding 模型**

| 选项 | 说明 | 适用 |
|------|------|------|
| `bge-m3`（BAAI） | 中英双语、开源、可本地跑 | 推荐，中文语料首选 |
| `text-embedding-v3` 等 API | 无需 GPU，按量计费 | 快速验证 |
| DeepSeek 生态 embedding | 若开放则优先 | 关注官方动态 |

本地部署：`sentence-transformers` 加载 bge-m3，CPU 可跑（1024 维，单条 ~10ms）。

**2. 向量入库 pgvector**

```sql
CREATE EXTENSION vector;
ALTER TABLE chunks ADD COLUMN embedding vector(1024);
CREATE INDEX ON chunks USING hnsw (embedding vector_cosine_ops);
```

**3. 统一 Retriever 抽象**

```
packages/retrieval/
├── base.py          # Retriever 协议: search(query, limit) -> list[SearchHit]
├── local.py         # pgvector 混合检索 (tsvector + HNSW + RRF 在 SQL 内融合)
├── web.py           # DeepSeek search/fetch 适配
└── fusion.py        # 跨源 RRF (local + web 结果统一融合)
```

`workflow.py` 只依赖 `Retriever` 协议，组合方式由配置决定——这也是评测协议里"检索消融实验"（Dense only vs 混合）的基础设施。

### 这就是 RAG 吗？

是。现在的系统是 RAG 的骨架（检索 → 增强 → 生成），但"R"是半假的。P0+P1 完成后：真文档库 + 真 embedding + 真 BM25 + 联网检索，才是一个完整的 production-grade RAG 检索层。

---

## P2：Verifier 强化（Reflection 范式）

### 现状问题

```python
elif state.answer and "[1]" not in state.answer:   # 字面匹配，形同虚设
```

两条硬规则只能拦截最粗的错误，引用错挂、证据曲解、答案幻觉全部漏过。

### 方案：规则层 + LLM Reflection 双层验证

```
Synthesizer
    │
    ▼
┌─────────────────────────────────┐
│ Layer 1: 规则校验（快，确定性）    │
│  - 证据非空                       │
│  - 引用标记存在且格式合法           │
│  - 每个 [n] 能映射到 Citation     │
│  - 答案长度 / 引用密度合理         │
└──────────────┬──────────────────┘
               │ 通过
               ▼
┌─────────────────────────────────┐
│ Layer 2: LLM Reflection（慢，语义）│
│  输入: 原问题 + 证据 + 答案        │
│  输出: 结构化审查报告 (JSON)       │
└──────────────┬──────────────────┘
               │
       ┌───────┴────────┐
       ▼                ▼
   issues 为空       issues 非空
       │                │
       ▼                ▼
    通过        consume_retry → Revise (DeepSeek)
                        │
                        ▼
               再过一轮 Layer 1（防修订引入新问题）
               重试耗尽 → 降级：答案 + 警告标记返回
```

LLM 审查 prompt 输出结构化结果：

```json
{
  "verdict": "pass | revise | reject",
  "issues": [
    {
      "type": "unsupported_claim",       // 与失败分类对齐
      "quote": "答案中缺乏证据支撑的原句",
      "reason": "证据 [2] 未提及 X"
    }
  ]
}
```

要点：

- Reflection 是**独立的一次 LLM 调用**，与 synthesize 分离，可换不同模型（如用更强模型审查）
- `issues[].type` 对齐 `evaluation-protocol.md` 的失败分类（`unsupported_claim` / `citation_mismatch` / ...），审查结果直接变成可统计的评测数据
- 预算控制：Reflection 调用消耗 `steps_used`，重试受 `max_retries` 约束，防止"反思无限套娃"
- 成本权衡：Layer 1 全量跑，Layer 2 可配置（默认开启，预算紧张时关闭）——这本身又是一个消融实验点

---

## P3：工具生态扩展

### 现状问题

只有一个 calculator，`_maybe_calculate` 用正则硬判断何时调用——这是 fake model 时代的妥协。真实 Agent 应该由 **LLM 决定**调什么工具（function calling），而不是正则猜。

### 方案 A：确定性工具集（对标主流 Agent 硬编码工具）

主流 Agent（Claude Code / Codex / OpenDevin）普遍内置这些高确定性工具：

| 工具 | 作用 | 本项目落地 |
|------|------|-----------|
| `read_file` / `list_dir` | 读本地文件 | 知识库补充：扫描本地 md/pdf 目录入库 |
| `web_search` / `web_fetch` | 联网检索 | P0 已规划（DeepSeek API） |
| `calculator` | 精确计算 | 已有 |
| `datetime` | 当前时间/时区换算 | 时效性问题的基础工具 |
| `http_request` | 受限 HTTP GET | 调用公开 API（汇率、天气） |
| `code_interpreter` | 沙箱执行 Python | 复杂计算 + 数据处理（可选，成本高） |

每个工具统一走 `Tool` 协议，全部过 `ToolRegistry` 的 allowlist / 超时 / 异常隔离。

### 方案 B：LLM function calling 驱动工具选择

把 `ToolRegistry.schemas()`（已有此方法！）发给 DeepSeek 的 `tools` 参数：

```python
response = await client.chat.completions.create(
    model="deepseek-chat",
    messages=messages,
    tools=[
        {"type": "function", "function": tool_schema}
        for tool_schema in self.tools.schemas()   # 现成的
    ],
)
if response.choices[0].message.tool_calls:
    for call in response.choices[0].message.tool_calls:
        result = await self.tools.execute(
            call.function.name, json.loads(call.function.arguments)
        )
```

这样 `_maybe_calculate` 的正则硬编码可以删掉，**工具路由决策交给 LLM**，这是从"流程模拟"到"真 Agent"的关键一步。

### 方案 C：Skill 与 MCP 扩展

**Skill 机制**（参考 Claude Code 的 Skill 设计）：

```
skills/
└── tech-report/
    ├── skill.toml       # 元数据：触发条件、描述
    └── prompt.md        # 领域专用 prompt 模板
```

Agent 启动时加载 skill 注册表，用户问题匹配到 skill 时注入对应 prompt（如"生成技术调研报告"skill 注入报告结构模板）。适合**场景化能力扩展**而不写死在代码里。

**MCP（Model Context Protocol）**：

项目已有 `packages/tools/mcp_server.py` 预留入口。两个方向：

1. **作为 MCP Server**：把本项目的工具（检索、评测）暴露为标准 MCP 服务，供其他 Agent（Claude Code 等）复用
2. **作为 MCP Client**：接入社区 MCP 服务器的工具（GitHub、数据库、浏览器自动化），工具生态瞬间扩大

```
packages/tools/
├── base.py            # Tool 协议（不变）
├── registry.py        # 本地工具注册（不变）
├── builtin/           # 内置确定性工具集
│   ├── calculator.py
│   ├── datetime_tool.py
│   ├── web_search.py
│   └── web_fetch.py
├── mcp_client.py      # MCP 工具动态挂载 → 适配进 ToolRegistry
└── skill_loader.py    # Skill 注册与匹配
```

---

## P4：Agent 范式升级（LangGraph + ReAct）

### 现状评估

现有手写状态机的**真实价值**先说清楚（不是要全盘否定）：

- 显式状态 + Budget + EventSink = 可观测性满分，这套东西 LangGraph 也要自己再做一遍
- 流程是静态线性（plan → retrieve → synthesize → verify），LLM 无法在中途决策"证据不够，换个查询再检索"

核心缺陷：**没有循环**。真正的 Deep Research 需要边检索边思考，证据不足时自主发起下一轮检索——这就是 ReAct 范式。

### ReAct 范式回顾

手写 ReAct 是一个 `while True` 循环，逻辑隐式、无法介入。LangGraph 把循环**显式化为图**：

| ReAct 环节 | LangGraph 对应物 | 职责 |
|-----------|-----------------|------|
| Reasoning（推理） | `agent` 节点 | 调 LLM，分析当前状态，决定调工具还是结束 |
| Acting（行动） | `tools` 节点 | 执行 tool_calls，结果写回状态 |
| 观察 → 再思考 | **条件边**（agent 后） | 检查最后一条消息：有 `tool_calls` → 路由到 tools；没有 → END |
| 循环回指 | **回指边**（tools → agent） | 工具执行完回到模型，下一轮推理 |

### 落地方案：保留现有资产，迁移编排层

**不推翻重来，分层复用**：

| 现有资产 | 在 LangGraph 中的角色 |
|---------|---------------------|
| `AgentState` (pydantic) | LangGraph 的 `TypedDict` State（改造为含 `messages` 字段） |
| `Budget` | 全局 recursion_limit + 自定义 budget 检查节点 |
| `AgentEvent` / EventSink | LangGraph 的 `stream_mode="custom"` / checkpoint 回调适配 |
| `HybridRetriever` | 包成 `retrieval_tool`（给 LLM 的一个工具） |
| `ToolRegistry` | 直接作为 `tools` 节点的执行器（含 allowlist/超时，比 LangGraph 原生的更安全） |
| `DeterministicFakeModel` | 单测用，LangGraph 图不依赖具体模型 |

新结构：

```
packages/agent_core/
├── models.py          # 状态定义（保留 + 扩展 messages）
├── llm.py             # FakeModel（测试）
├── deepseek.py        # DeepSeek provider（加 function calling）
├── workflow.py        # 旧线性 workflow（保留：回归测试 + 消融基线）
└── graph.py           # ★ 新：LangGraph 图
```

`graph.py` 核心骨架：

```python
from langgraph.graph import StateGraph, MessagesAnnotation, START, END
from langgraph.prebuilt import ToolNode

def should_continue(state):
    last = state["messages"][-1]
    return "tools" if last.tool_calls else END     # 条件边

builder = StateGraph(MessagesAnnotation)
builder.add_node("agent", call_deepseek)            # 推理节点
builder.add_node("tools", ToolNode(tools=registry_builtins))  # 行动节点
builder.add_node("budget_guard", check_budget)     # 自定义：预算守卫

builder.add_edge(START, "agent")
builder.add_conditional_edges("agent", should_continue)   # agent → tools | END
builder.add_edge("tools", "agent")                        # 回指边：观察→再思考
builder.add_edge("tools", "budget_guard")                 # 每次行动后查预算

graph = builder.compile(
    checkpointer=PostgresSaver(...),   # 断点恢复（对应现在的 trace 持久化）
)
```

**比裸 LangGraph 多做的（我们的差异化）**：

1. **budget_guard 节点**：LangGraph 的 `recursion_limit` 只数轮次，我们保留语义化预算（工具调用次数、token 成本、重试），超限走降级路径而不是抛异常
2. **plan-first 入口**：纯 ReAct 对中文调研问题容易发散，保留"先 plan 拆解再进 ReAct 循环"的混合模式（Plan-and-Execute 变体），每轮 ReAct 围绕当前子任务
3. **verifier 出口**：循环结束后接 P2 的双层验证再产出最终答案（ReAct 原版没有这个环节）
4. **EventSink 桥接**：把 LangGraph 的节点事件翻译成现有 `AgentEvent` 流 → 前端 SSE、trace 持久化、评测 runner **全部零改动**——这是分层设计最大的收益

### 迁移策略：双轨并行 + 评测裁决

```
评测集（data/eval_cases.jsonl 扩充到 30+ 条）
    ├── 线性 workflow（现状，作为 baseline）
    └── LangGraph ReAct（新）
            │
            ▼
   相同指标对比: task_success / steps / latency / cost / recall@K
```

- `POST /tasks` 加 `engine: "linear" | "react"` 参数，两个引擎并存
- 评测 runner 跑两组，结果落库对比（这正好把"配置对比与消融实验"从文档承诺变成真实能力）
- 用数据决定默认引擎，而不是拍脑袋——这也符合 `evaluation-protocol.md` 的"结论必须取自保存的真实结果"

依赖：`langgraph` / `langchain-core`（`pyproject.toml` 加 optional group `graph`）。

### 保持原状 vs 迁移 LangGraph？

| 维度 | 手写状态机 | LangGraph |
|------|-----------|-----------|
| 上手/调试 | ✅ 单步断点，全是自己的代码 | 要理解框架抽象 |
| 可观测性 | ✅ 已实现 | checkpointer + stream，生态更全 |
| 循环/动态决策 | ❌ 需手写 while + 路由 | ✅ 条件边原生表达 |
| 断点恢复/时间旅行 | ❌ 需自建 | ✅ checkpointer 内置 |
| 人力成本/多 agent 扩展 | 高 | ✅ subgraph 原生 |

结论：**调研型任务需要循环推理，ReAct + LangGraph 是正确方向；但保留线性引擎作为可对照的 baseline 和消融实验基线**。这正是本项目"可评测"定位的延伸——框架选型本身也用评测说话。

---

## 实施顺序建议

```
P0.1 文档导入管道 + pgvector 存储          ┐
P0.2 WebSearchTool (DeepSeek search API)   ├─ 检索能力质变，最先做
P0.3 WebFetchTool + 二段式抓取              ┘
P1   bge-m3 embedding 替换哈希向量           ── RAG 真实化
P2   Reflection 双层验证                    ── 答案质量
P3.1 function calling 驱动工具路由          ┐
P3.2 builtin 工具集扩充                     ├─ Agent 能力面
P3.3 MCP client + skill loader             ┘
P4   LangGraph 双轨迁移 + 评测裁决          ── 架构演进
```

每步完成标准：

1. 新增能力有对应单测（沿用 `tests/` 现有分层）
2. 跑通 `eval_cases.jsonl`，指标不回退
3. 事件流兼容现有前端（`AgentEvent` 协议不变）
4. 更新 `docs/experiments/` 记录对比数据
