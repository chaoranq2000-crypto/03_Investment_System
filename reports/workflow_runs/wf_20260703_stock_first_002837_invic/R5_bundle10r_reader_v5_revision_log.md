# Reader v5 叙事重构记录

## 触发原因

Reader v4 的事实边界与追溯关系通过了自动检查，但人工反馈指出正文“机械化和干涩”。复核确认，v4 在 10 个章节中重复使用“本节判断、关键事实、因果机制、经济含义、反向证据、不确定性边界、后续验证”等七组标签；原可读性得分只检查字数和 H2 数量，无法识别这一问题。

本次只修订表达与编排，不增加事实、预测、估值数值或结论置信度。v4 报告、附录、scorecard、handoff 与 generation lock 均保持原始字节和哈希。

## 结构变化

| v5 读者章节 | 承接的结构化分析单元 | 读者问题 |
|---|---|---|
| 问题不在有没有液冷，而在能否兑现 | executive_summary、conclusion_and_watchlist | 产品能力如何走到利润和现金 |
| 公司靠什么赚钱 | company_context_and_scope、segment_economics | 宽温控基本盘与液冷平台是什么关系 |
| 需求成立，但不会自动变成公司利润 | industry_and_competition | 行业需求如何穿过竞争和交付环节 |
| 增长的成色 | financial_quality、forecast_and_scenarios | 收入、利润、现金和预测能否相互解释 |
| 市场已经计入多少增长 | valuation、market/technical/sentiment/events | 当前市值要求什么样的盈利兑现 |
| 什么会证明这套判断错了 | risks_and_falsification、watchlist | 哪些证据会推翻或上调判断 |

结构化 payload 仍保留 10 个不可补偿的分析单元，质量门继续逐单元检查事实、机制、经济含义、反证、不确定性、观察指标和引用；六章只负责读者表达，不替代底层门禁。

## 表达变化

- 开头直接呈现 2025 年收入/利润与 2026Q1 毛利/现金的矛盾，不再先介绍流程状态。
- 把事实、管理层近似口径、研究估计和分析师观点放进各自适合的段落，并在首次出现时说明边界。
- 只保留对理解主线有帮助的四组表格；将 20 个分散观察项收敛为 8 个核心变量。
- 正文移除 generation、工件哈希、自动门、候选状态、历史 Reader 等审计语言；这些信息只留在质量与追溯产物中。
- 不做同业排名，不启用 DCF 或 SOTP，不把液冷独立经济性从 unknown 改写为事实。

## 新增非补偿叙事门

v5 质量合同新增以下 fail-closed 检查；任一 high issue 都会阻断送审候选状态：

1. 审计标签覆盖多数章节时，触发 `reader_template_scaffolding_excessive`。
2. 正文出现工作流、工件锁或质量状态术语时，触发 `reader_process_audit_language_leaked`。
3. 多段使用相同开头或近重复段落时，分别触发 opening / similarity issue。
4. 标题密度过高或存在大量过薄章节时，触发 heading fragmentation issue。
5. v5 缺少叙事政策配置时直接拒绝，不能退回 v4 的字数加标题计分。

## 自动检查结果

| 检查 | v5 结果 |
|---|---|
| Reader score | 100 / 82 |
| truthfulness / core / candidate blockers | 0 / 0 / 0 |
| 正文汉字数 | 4151 |
| H2 读者章节 | 6 |
| 叙事段落 | 31 |
| 重复审计标签 | 0 |
| 流程/审计术语命中 | 0 |
| 近重复段落对 | 0 |
| 过薄章节 | 0 |
| 显示引用 | 22 / 22 唯一解析 |
| 确定性重建 | 6 个锁定产物两次重建，哈希变化 0 |
| v4 历史兼容 | payload、report、appendix、scorecard、handoff、generation lock 均可精确重建原哈希 |

Reader v5 SHA256 为 `cb261412f1c72dfd56e6dc9030c3d0f8bb06d4963a5525396059a6b1a21e6090`。本记录不代替人工复核；v5 的人工状态仍为 `pending`，`sample_quality_allowed=false`，`p2_allowed=false`。
