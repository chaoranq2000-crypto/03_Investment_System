# Quality Guardrails — 质量检查与反幻觉规则

## 1. 目标

质量体系的目标不是让报告更长，而是让研究更可靠、可复查、可更新。

所有研究产物都必须通过最小质量门槛：

```text
证据可追溯
口径可解释
不确定性可见
反证可见
更新有痕
不输出直接交易指令
```

---

## 2. 最小质量门槛

任一研究产物交付前，至少检查：

| 检查项 | 要求 |
|---|---|
| 证据引用 | 关键结论有 `evidence_id` 或 `claim_id` |
| claim 类型 | 事实、估计、推断、管理层表述、第三方观点分开 |
| 数据口径 | 指标定义、单位、周期、来源明确 |
| 缺失数据 | 缺失项标记 `TODO` / `MISSING` / `UNKNOWN` / `LOW_CONFIDENCE` |
| 反证 | 重要结论配套风险或反证 |
| 过期证据 | 可能过期的证据标记 `stale` |
| 多对多映射 | 个股与细分关系使用 exposure 记录 |
| 更新记录 | 新证据导致变化时输出 change log |
| 投资边界 | Research 永久无直接交易建议；Portfolio 只陈述事实；Investment Review 只有在显式当前输入齐备时才可给建议 |

---

## 3. 当前目标范围与 outcome

质量 issue 必须把风险描述与工作流决定分开；severity 只描述风险大小和处理
优先级，不能单独决定 run status。字段级 issue contract 由
`.agents/skills/quality-review/references/issue_schema.md` 定义，canonical outcome
只由 `docs/workflows/RESEARCH_WORKFLOW.md` 第 6.3 节定义。本政策不复制字段 enum、
truth table 或状态推导。

质量审查应返回有证据的 finding、受影响能力、修复 owner 与下一步；编排器再消费
上述 owners 形成 run 状态。

### 3.1 缺失信息降级阶梯

```text
发行人直接披露
→ 经审计的聚合口径
→ 明示假设、边界和不确定性的有界估计 / 情景
→ unknown 或省略依赖该字段的结论
```

低一级不得被写成高一级。进入 `unknown` / omit 后，只关闭真正依赖该
字段的 claim、section、calculation 或 method；其他可诚实完成的产物继续。

### 3.2 机器验证与最终报告人工审核

活动 V1 的 evidence、claim、metric、字段、candidate、research pack、计算、
generation lock 和 receipt 通过机器 provenance、schema、claim-type、metric、
citation、hash 和 no-advice 检查。`reviewed` 在这些中间对象上表示
machine-qualified，不表示人工批准，也不要求 reviewer authority、签名或逐项决定。

唯一活动人工边界是最终报告质量审核：

机器负责计算并校验最终报告当前字节的 SHA-256；真实 reviewer 负责报告质量判断。
报告字节变化必须使旧决定失效。人工审核不能批准伪造数据、替代证据检查或绕过
自动质量失败，机器也不得合成 reviewer、时间或决定。

最终报告审核结构、状态迁移和 legacy 字段兼容见
`.agents/skills/research-orchestrator/references/workflow_state_schema.md` 与
`schemas/r5_final_report_review.schema.json`；本政策不复制字段级规则。
`sample_quality_ready` 的业务含义和自动 outcome 边界以
`docs/workflows/RESEARCH_WORKFLOW.md` 为准。

除最终报告 SHA-256 外，其他 hash 只用于机器完整性和重放。历史 Bundle/Night
的人审、authority、独立 receipt 和 candidate decision 只读，不进入活动 routing。

---

## 4. 事实、估计、推断、观点分离

### 4.1 允许标签

```text
fact
estimate
inference
management_comment
analyst_view
opinion
unknown
```

### 4.2 常见错误

| 错误 | 正确做法 |
|---|---|
| 把“公司预计”写成事实 | 标为 `management_comment` 或 `estimate` |
| 把券商目标价写成估值事实 | 标为 `analyst_view` |
| 把市场传闻写成订单落地 | 标为 `low_confidence` 或不采用 |
| 把收入、订单、产能混为一谈 | 明确指标口径 |
| 把概念相关写成业绩暴露 | exposure_type 标为 `narrative` |

---

## 5. 证据质量检查

### 5.1 来源等级

| 等级 | 可靠性 | 使用限制 |
|---|---|---|
| A | 高 | 可支撑核心事实 |
| B | 中高 | 可支撑行业、政策、供需判断 |
| C | 中 | 需说明口径和限制 |
| D | 低 | 只能作线索，不能单独支撑关键结论 |

### 5.2 检查问题

- 证据是否来自原始披露？
- 证据是否有日期？
- 证据是否有页码、段落或表格定位？
- 证据是否可能过期？
- 证据是否和其他来源冲突？
- 证据是否只是管理层说法？
- 证据是否只是市场叙事？

---

## 6. 指标口径检查

任何指标都需要回答：

```text
指标名称是什么？
属于公司、细分、行业还是市场？
期间是什么？
单位是什么？
来源是什么？
是否估算？
计算方法是什么？
是否和其他报告口径一致？
```

常见高风险指标：

- 市场空间
- 渗透率
- 收入占比
- 毛利率
- 订单金额
- 产能
- 市占率
- ASP
- capex
- 客户集中度
- 估值倍数

---

## 7. Segment-company exposure 检查

每条 exposure 记录必须检查：

```text
是否有 segment_id？
是否有 company_id / stock_code？
exposure_type 是否明确？
exposure_score 是否有证据支撑？
收入占比是否为披露值还是估计值？
confidence 是否标注？
evidence_ids 是否存在？
valid_from / valid_to 是否需要？
是否只是 narrative？
```

禁止：

- 看到关键词就给高暴露分。
- 把技术储备等同于收入兑现。
- 把产能规划等同于利润贡献。
- 把单一新闻报道等同于确认订单。

---

## 8. 报告交付检查

### 8.1 细分报告

必须包含：

- metadata
- 一句话结论：事实 / 推断 / 不确定性分开
- 细分定义和边界
- 产业链位置
- 需求驱动
- 供给与竞争格局
- 利润池
- A 股公司池
- 关键指标体系
- 催化剂
- 风险与反证
- 评分卡
- 后续跟踪清单
- 证据地图

### 8.2 个股报告

必须包含：

- metadata
- 业务拆解
- 细分方向暴露
- 财务质量
- 竞争优势
- 客户与供应链
- 估值场景
- 催化剂
- 风险
- 反证清单
- 跟踪指标
- 证据地图

### 8.3 对比报告

必须包含：

- 可比对象定义
- 统一评分口径
- 数据来源说明
- 评分矩阵
- 关键分歧
- 风险和不确定性
- 后续研究队列

---

## 9. 更新质量检查

刷新研究时不能只新增材料，必须判断对旧结论的影响。

检查：

```text
新增 evidence 是什么？
影响哪些 claim？
哪些 claim stale？
哪些 claim superseded？
哪些 claim contradicted？
scorecard 是否变化？
watchlist 是否变化？
哪些报告需要重跑？
最终报告是否已形成；如需样例质量，是否已请求唯一最终报告审核？
```

---

## 10. 反证要求

重要结论至少配套一种反证视角：

- 需求低于预期
- 价格下行
- 竞争恶化
- 客户订单不及预期
- 产能释放低于预期
- 毛利率压力
- 估值过高
- 政策变化
- 技术路径替代
- 财务质量恶化
- 证据质量不足

---

## 11. Research、Portfolio 与 Investment Review 的边界

所有 Research 工作流产出都应默认包含研究边界：

> 本内容用于研究流程与证据管理，不构成任何买入、卖出、持有或其他交易建议。

可以给：

- 观察清单
- 研究优先级
- 风险清单
- 验证指标
- 场景假设

不应给：

- 直接买入/卖出结论
- 明确交易价位指令
- 保证收益判断
- 无风险表述

Portfolio 只负责账务记录、对账、持仓、现金、成本、收益和行情等可验证事实。
它不推断交易动机，不生成个性化交易动作或目标仓位，也不把 Portfolio 行业标签
回写为 Research exposure。

独立的 `investment-review` 可以解释 Portfolio 事实、生成明确标注的动机假设并复盘
操作，但普通周期报告必须保持 `observation_only`。只有当用户在当前请求中明确要求
advice，并提供当前投资期限、风险预算及与本次建议有关的仓位或组合约束时，Review
才可以生成个性化动作或建议仓位。系统默认、历史实验参数、推断出的偏好、收益目标和
人类可读章程都不能替代这些输入。

缺少任何必需输入或证据不足时，Review 的 `action` 和 `target_position` 必须为空；
可以说明事实、变化、风险、场景和待确认问题，但不能以 `buy`、`sell`、`hold`、
`add`、`reduce`、`exit` 的形式给出建议。允许给建议时，也必须把事实、动机推断和
建议分开，标明数据截止时间、依据、风险、失效条件与重要缺失。

`docs/policies/PERSONAL_HIGH_RISK_EQUITY_STRATEGY_CHARTER.md` 只提供人类判断边界。
`C-HUMAN-005` 保持 `pending` / `null`；不得从 P10、30%、35% 或任何回报目标生成
自动回撤、仓位或减风险规则。任何产品都不得连接券商、执行订单或保证收益。
