# 投资复盘系统实施计划

基线：`a12cbb8a9b90e348c117f8eff3087a5a89c5c1b3`

## 目标架构

系统以交易事件为基本单位，以个股与组合为双重视角，以事实、解释、替代解释和长期模式为输出，不生成机械总分。确定性程序负责数据治理、会计重放、指标与检验；AI 只负责语义理解、上下文连接和带不确定性的解释。

## Gate 1：数据契约与来源追溯（本补丁）

### 交付

- 独立 `investment_review.sqlite3`；
- `data_sources`、`ingest_runs`、`trade_events`、`decisions`、关联表和快照预留表；
- 对现有 portfolio SQLite 的只读 `doctor`；
- mapping 驱动的 CSV/SQLite 导入；
- 双时间字段 `occurred_at` / `known_at`；
- 稳定事件 ID、raw payload、SHA-256、幂等导入与冲突检测；
- 复盘库 application ID、不可变 source config version、mapping/source hash 锁；
- 正式 SQLite 的源路径、表名与实时表结构签名锁，CSV 的稳定 source identity；
- event ↔ ingest run 明细关联与全量 snapshot 缺失检测；
- 非成交现金事件的独立 `cash_amount`；
- 决策笔记录入和事件关联；
- 自动化测试、操作手册和可回滚补丁。

### 退出条件

- 确认真实持仓数据库和成交表；
- 生成并人工审核 mapping；
- 至少一批真实成交 dry-run 无字段错位；
- 重复导入幂等；
- 自动生成 mapping 不能绕过人工审核进入正式导入；
- 人工审核后的 mapping 内容被 SHA-256 锁定，任何字段漂移都阻断正式导入；
- 换库、换表或表结构变化必须重新 doctor / review；旧 v1 旁路库不得伪升级；
- 源数据库保持未修改；
- 复盘库完整性检查通过。

## Gate 2：决策事件重构与组合快照

### 交付顺序

1. 针对真实 portfolio schema 固化只读 adapter，而不是长期依赖字段猜测；
2. 将订单、成交、转入转出、期初持仓和价格快照统一成事件流；
3. 重建 `TradeEpisode`：观点产生、首次建仓、加减仓、退出和复盘；
4. 在每个关键事件前生成 `PortfolioSnapshot`，记录现金、总仓位、单股/行业集中度和该标的组合角色；
5. 建立 source record → canonical event → episode → snapshot 的完整 lineage；
6. 对跨市场、ETF、公司行动和转账场景补充显式规则与测试。

### 退出条件

- 任意一笔成交都能追溯到原始记录；
- episode 数量、持仓数量和现有 portfolio 重放结果可对账；
- 关键操作时点都有组合上下文；
- 无未来信息进入当时快照。

## Gate 3：确定性分析引擎

### 模块

- 个股执行：入场、加减仓、退出、持有周期漂移；
- 组合背景：现金、集中度、行业和重复暴露；
- 序列特征：连续盈亏后仓位/频率变化、追回、追价、过早兑现；
- 市场环境：趋势、震荡、波动和风险偏好标签；
- 结果归因：市场、行业、个股、时机、仓位、费用和滑点；
- 现实反事实：原计划持有、小仓位、不临时加仓、减仓而非清仓。

所有结果输出“指标 + 证据范围 + 适用条件”，不汇总成单一评分。

### 退出条件

- 每个指标有确定公式、输入 lineage 和测试；
- 盈亏结果与决策质量分开；
- 反事实不使用事后最佳价格；
- 缺失数据会降级或标记未知，而不是补造事实。

## Gate 4：AI 复盘编排

### 逻辑角色

- 事实时间线；
- 个股分析；
- 组合分析；
- 市场环境；
- 历史相似案例；
- 反方审查；
- 综合复盘；
- 长期画像更新。

中央编排器只消费可追溯数据包。每个结论必须标记为 `fact`、`interpretation`、`hypothesis` 或 `alternative_explanation`，并附 source/episode/finding 引用。单笔交易不得直接固化为长期人格标签。

### 退出条件

- 单笔、周度和月度复盘采用统一输出契约；
- 主要结论附证据和替代解释；
- 用户修正可以回写并保留版本；
- 模型不可访问决策时点之后的 `known_at` 数据；
- 输出保持 no-advice 边界。

## Gate 5：交互与长期闭环

- 在现有 portfolio 页面增加只读复盘入口；
- 时间线、组合快照、证据抽屉和结论纠错；
- 周/月/季度任务编排；
- `BehaviorHypothesis` 需要多个历史样本才能升级置信度；
- `Intervention` 记录尝试、适用条件、副作用和后续观察；
- 逐步形成个人交易画像与方法库，但允许撤销和版本回退。

## 当前下一动作

Gate 1 已完成现场执行。P2A 已获得单独批准并实现 Gate 2 的一个受限子集：组合/持仓
快照契约、单快照确定性指标、决策/episode 上下文和输出接线。下一步仍不是自动推进
完整 Gate 2；真实历史快照生成、事件重放、episode 重构与现有 portfolio 对账需另行批准，
并继续消费已审核 mapping / schema signature，不能重新猜测 portfolio 字段。

## 2026-07-15 Phase 1 现场执行状态

- 已针对正式 `portfolio.sqlite3` 生成 schema manifest；
- 已保留 generated mapping，并建立人工审核后的 reviewed mapping；
- 已完成真实数据 dry-run、正式导入、幂等复跑和源库只读验证；
- 当前停在 Gate 1，Gate 2–5 未启动；
- 详细证据和未决项见 `reports/investment_review/phase1/gate1_acceptance.md`、
  `quality_gate_report.md` 与 `quality_issues.csv`。

## 2026-07-15 P2A 实施状态

- 已实现 `PositionSnapshot`、`PortfolioSnapshot`、`PortfolioContext`；
- 已实现现金、gross/net、权重、Top 1/5、HHI、行业/标签暴露和前后仓位变化；
- 已将事前事实与事后观察分区，阻断晚于决策时点的 `known_at`；
- 已复用 v2 旁路库预留快照表，不修改现有 portfolio 源库；
- 已增加独立组合仓位分析 JSON/Markdown 输出；
- 未进入完整 episode 重构、复杂风险模型、AI 编排或 UI 阶段。
