# 评测与消融实验协议

## 数据集切分

数据集至少覆盖事实问答、多跳检索、冲突证据和不可回答四类。开发集用于调参，测试集在实验配置冻结后运行；每条样本保存标准文档 ID 和必要证据 ID。

## 核心指标

- 检索：Recall@K、MRR、nDCG。
- 引用：Citation Precision、Citation Completeness。
- Agent：任务成功率、平均步骤、P50/P95 延迟、工具错误恢复率。
- 成本：输入/输出 token 与每个成功任务成本；fake model 下只报告步骤与延迟。

## 三组消融

| 实验 | 基线 | 实验组 | 控制变量 |
|---|---|---|---|
| 检索 | Dense only | BM25 + Dense + RRF + rerank | 相同语料、chunk、K |
| 工作流 | 固定一次检索 | Planner + evidence grade + bounded revision | 相同模型与预算 |
| 记忆 | 无长期记忆 | 相关度、置信度、时效性过滤 | 相同问题序列 |

每次结果必须记录代码版本、模型名、Prompt 版本、检索版本、随机种子和预算。不得只展示最佳样本。

## 失败分类

按 `retrieval_failure`、`planning_failure`、`tool_failure`、`unsupported_claim`、`citation_mismatch`、`early_stop`、`late_stop` 标注。先修复占比最高且可稳定复现的一类，再重新运行冻结测试集。

## 结论模板

实验结论需同时回答：变化是否显著、代价是什么、在哪类样本上失败、何时不应采用该方案。简历中的提升比例只能取自保存的真实结果。
