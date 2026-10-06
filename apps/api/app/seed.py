"""Small local corpus used by the first-run demonstration."""

from packages.retrieval.hybrid import Document

SEED_DOCUMENTS = [
    Document(
        id="seed-agent-workflow",
        title="Agent 工作流设计",
        content=(
            "可靠的 Agent 应将规划、工具调用、证据校验和答案生成建模为显式状态。"
            "每个循环必须设置最大步骤、超时和重试预算，从而避免无限循环。"
            "执行轨迹需要记录节点耗时、工具结果和配置版本，便于回放与定位失败。"
        ),
        source="seed://architecture",
    ),
    Document(
        id="seed-hybrid-retrieval",
        title="混合检索与重排",
        content=(
            "BM25 擅长关键词精确匹配，向量检索擅长语义召回。RRF 可以在不同分数量纲下融合排序，"
            "再使用 reranker 对候选证据重排。评测应至少报告 Recall@K、MRR 与 nDCG。"
        ),
        source="seed://retrieval",
    ),
    Document(
        id="seed-agent-evaluation",
        title="Agent 评测原则",
        content=(
            "Agent 评测不能只使用 LLM-as-Judge。可复现方案应结合标准证据、规则指标和人工抽检，"
            "同时统计任务成功率、引用正确率、平均步骤、延迟、成本与工具失败恢复率。"
        ),
        source="seed://evaluation",
    ),
    Document(
        id="seed-agent-security",
        title="工具调用安全边界",
        content=(
            "工具执行需要 allowlist、结构化参数校验、超时、熔断与最小权限。检索内容属于不可信数据，"
            "不得覆盖系统指令。日志需要脱敏，凭证不得进入提示词、持久化轨迹或错误响应。"
        ),
        source="seed://security",
    ),
]
