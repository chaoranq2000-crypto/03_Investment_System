# R5 Sample-Quality Stock Research Note Specification

> R5 是在 R4 内部草稿之上的“样例质量个股深度报告”目标层。本文件定义 R5 的输入、输出、章节、质量门和降级规则。

R5 是显式请求时才启用的 report-capability profile，不是 canonical workflow 的
默认 routing，也不直接决定 `workflow_state.status`。canonical outcome 以
`RESEARCH_WORKFLOW.md` 的当前目标范围 truth table 为准。

本文件中的 evidence / claim / metric / research pack “已审查”只表示通过机器
provenance、schema、claim-type、metric、citation、hash 和 no-advice 验证。
中间产物不需要 reviewer 身份或人工批准；唯一活动人工边界是最终报告质量审核。

## 1. 核心定义

```text
R5_sample_quality_stock_note =
  evidence complete enough
+ financial history complete enough
+ business breakdown complete enough
+ industry context complete enough
+ forecast model complete enough
+ valuation context complete enough
+ market / sentiment / event data current enough
+ narrative layer coherent enough
+ automated quality gate passed
+ one valid final-report human review
```

R5 不等于“更长的报告”。R5 是一套结构化研究资产经过机器质量门后，
被转译成样例风格报告。
报告可以在 `not_requested|pending` 时作为自动研究产物存在，但不能标记
`sample_quality_ready`。

## 2. R4 与 R5 的区别

| 维度 | R4 internal draft | R5 sample-quality note |
| --- | --- | --- |
| 目标 | 证据可审计、缺口可见 | 样例质量、判断链完整 |
| 核心产物 | report draft + quality gate | research pack + report note + gate |
| 证据不足时 | 显示 TODO / source gap | 降级，不得标记 sample-quality |
| 业务拆分 | 可存在 MISSING_DISCLOSURE | 必须支撑收入、毛利、利润池或明确缺口 |
| 盈利预测 | 可缺失 | 必须至少有 base case |
| 估值 | 可缺市场数据 | 必须有市场快照与同业语境 |
| writer 角色 | 汇总证据 | 转译机器验证通过的研究资产 |

## 3. R5 事实源

R5 的事实源是：

```text
R5_stock_research_pack.yaml
```

报告正文只是转译产物：

```text
R5_stock_research_note.md
```

任何正文中的数字、判断、风险、事件或估值锚，都必须能回到 research pack 中的
evidence、metric、assumption、scenario 或 source_gap。research pack 的机器验证
不能替代最终报告人审。

## 4. R5 研究包结构

R5 research pack 至少包含：

```text
company_identity_pack
evidence_snapshot_pack
financial_history_pack
business_breakdown_pack
segment_exposure_pack
industry_context_pack
peer_comparison_pack
forecast_model_pack
valuation_pack
technical_market_pack
sentiment_event_pack
risk_counterevidence_pack
```

## 5. R5 报告章节

R5 report note 固定章节：

```text
价值发现：<公司名>

前言：一句话主线 + 核心矛盾 + 市场分歧

第一章 财务概览
  1.1 财务报表
  1.2 财务指标
  1.3 财务质量与异常项

第二章 业务拆分
  2.1 核心业务一
  2.2 核心业务二
  2.3 新业务 / 期权业务
  2.4 利润结构总结

第三章 行业分析
  3.1 核心细分行业
  3.2 相邻细分行业
  3.3 竞争格局与利润池
  3.4 公司位置

第四章 盈利预测
  4.1 未来三年财务预测
  4.2 业绩节奏和拐点
  4.3 与一致预期差异
  4.4 敏感性分析

第五章 估值分析
  5.1 静态估值
  5.2 动态估值
  5.3 同业估值
  5.4 情景市值 / SOTP / DCF

第六章 技术分析
  6.1 均线趋势
  6.2 关键价位
  6.3 交易状态观察

第七章 情绪分析
  7.1 宏观情绪
  7.2 行业 / 主题情绪
  7.3 个股情绪

第八章 事件驱动
  8.1 未来 1 个月事件
  8.2 未来 3 个月事件
  8.3 未来 6 个月事件
  8.4 验证指标与反证条件

第九章 研究结论
  9.1 核心判断
  9.2 关键假设
  9.3 证伪条件
  9.4 后续跟踪清单
```

## 6. 自动报告质量要求

样例质量至少要求每章满足：

```text
事实：有哪些证据或数据？
解释：为什么这些事实重要？
判断：这些事实如何影响公司基本面、预期或估值？
风险：什么情况会证伪？
来源：能回到 evidence / metric / assumption / source_gap。
```

这些要求先由机器 gate 检查。特别要求：

```text
财务概览：必须讨论利润质量、现金流、异常项、ROE/ROIC 或周转效率。
业务拆分：必须讨论收入、毛利率、利润贡献或缺口原因。
行业分析：必须服务个股判断，不能写成泛泛行业介绍。
盈利预测：必须覆盖 2026E-2028E，且每个关键预测有假设来源。
估值分析：必须有当前市场快照、同业或情景估值语境。
技术分析：必须有 as_of_date，不得使用过期价格判断。
情绪分析：必须区分 macro / industry / company。
事件驱动：必须有日期、事件、影响路径、验证指标、反证条件。
研究结论：必须是研究结论，不是直接交易指令。
```

## 7. 降级规则

任何 capability 的输入不足都按同一阶梯降级：

```text
发行人直接披露
→ 经审计的聚合口径
→ 明示假设、边界和不确定性的有界估计 / 情景
→ unknown 或省略依赖该字段的结论
```

| gap | capability-local effect | canonical effect |
|---|---|---|
| company identity、source identity、path 或 parse 失败，导致任何诚实报告都无法生成 | report capability unavailable | `blocked` |
| financial history 不完整但缺口可见且未被无依据使用 | 只能 source-gapped draft | `accepted_with_todos` 可用 |
| business breakdown 不完整但缺口可见 | 关闭依赖业务拆分的结论和 sample-quality | `accepted_with_todos` 可用 |
| forecast model 不可用 | 省略盈利预测强结论和依赖该模型的方法 | 若当前目标不要求该方法，`accepted_with_todos` 可用 |
| valuation / market snapshot 不可用 | 省略估值或市场状态强结论 | 若当前目标不要求该方法，`accepted_with_todos` 可用 |
| technical `as_of_date` 缺失 | 不能写交易状态判断 | 非必需 capability limitation |
| sentiment / event pack 缺失 | 不写情绪或催化强判断 | 非必需 capability limitation |
| risk / counterevidence 被隐藏，或 unsupported number 实际进入报告 | 当前报告 defect | `needs_fix` |

unknown 必须显式展示。低一级证据不得伪装成高一级；仅关闭实际依赖该字段的
claim、section、calculation 或 method。severity 只描述风险，不能单独提升为全局 blocker。

## 8. No-advice 边界

R5 可以输出：

```text
研究结论
核心假设
验证指标
证伪条件
风险场景
跟踪清单
```

R5 不输出：

```text
直接交易指令
个人化仓位安排
保证收益表达
以评分代替交易行动
```

如样例文本中存在交易化表达，R5 只学习其“研究结构和信息密度”，不复制其交易指令表达。

## 9. Legacy R5 capability evaluators

```text
R5-G1 Evidence Completeness Gate
R5-G2 Financial Model Gate
R5-G3 Business Breakdown Gate
R5-G4 Industry Context Gate
R5-G5 Forecast Model Gate
R5-G6 Valuation Gate
R5-G7 Market / Technical Gate
R5-G8 Sentiment / Event Gate
R5-G9 Narrative Coherence Gate
R5-G10 No-Advice Gate
R5-G11 Sample Benchmark Gate
```

`R5-G1`–`R5-G11` 已退出普通 stock workflow 的默认 routing。只有调用方明确请求
R5 report capability check 时才能运行；它们保留 local ID，并使用以下既有
G0–G10 owner 映射：

| local_check_id | mapped_global_gate_ids |
|---|---|
| `R5-G1` | `G1` |
| `R5-G2` | `G3\|G7` |
| `R5-G3` | `G2\|G3\|G7` |
| `R5-G4` | `G4\|G7` |
| `R5-G5` | `G3\|G7` |
| `R5-G6` | `G3\|G7` |
| `R5-G7` | `G3\|G7` |
| `R5-G8` | `G1\|G2\|G7` |
| `R5-G9` | `G2\|G7` |
| `R5-G10` | `G9` |
| `R5-G11` | `G7` |

每个 evaluator 输出至少包含：

```text
issue_id
severity
impact_scope
active_disposition
affected_capabilities
blocks_current_goal
gate_id
local_check_id
mapped_global_gate_ids
section
artifact
description
fix_owner_skill
next_action
```

local evaluator 只能说明某个 capability 是否可用、受限或有 defect。它不得直接
写 canonical status，也不得让 Bundle/R5 local pass 覆盖 unsupported-used、
double-count、hidden TODO 或 no-advice defect。

## 10. 唯一最终报告审核

活动状态使用：

```text
final_report_review_semantics_version: final_report_review_v1
automated_report_quality_passed: true | false
final_report_review_status: not_requested | pending | approved | changes_requested
final_report_review:
  report_path
  report_sha256
  reviewer
  reviewed_at
  decision
  notes
  change_scope
```

`pending` 由机器绑定 repo-relative 最终报告路径和当前字节 SHA-256；
`approved|changes_requested` 还必须有真实非机器 reviewer、ISO 时间和非空备注。
`decision` 必须等于顶层 status。`change_scope` 只在 `changes_requested` 中取
`automated_quality_defect|report_revision`，其他状态为空。

报告字节变化后，旧审核立即失效。`not_requested|pending` 不改变自动 workflow
outcome，也不阻止 `system_v1_complete`，但 `sample_quality_ready=false`。
`sample_quality_ready=true` 的必要条件包括全部必要自动质量检查通过、最终报告
`approved` 且当前 hash 匹配，以及其他适用样例质量条件；这些必要条件不得解释为
自动充分。`changes_requested` 揭示自动质量缺陷时进入 `needs_fix`，只要求报告
修订时不改变自动 outcome。

只有最终报告 hash 绑定人工审核。research pack、evidence、claim、metric、
candidate、计算、generation lock 和 receipt 的 hash 只用于机器完整性。
历史 Bundle 多份 exact-hash 人审保持只读，不能满足当前最终报告审核。

## 11. Writer 原则

Report writer / composer 只能做三件事：

```text
1. 组织结构；
2. 转译机器验证通过的研究资产；
3. 显式展示 source gap。
```

Report writer / composer 不能做三件事：

```text
1. 创造没有证据的数字；
2. 隐藏 TODO 或 MISSING_DISCLOSURE；
3. 用流畅叙事掩盖质量门未通过。
```
