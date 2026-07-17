# P2G 行为分析路线图

## 决策摘要

P2G 的第一张补丁只冻结跨 Trade Episode 的确定性事实样本，不做行为归因。
这样可先固定双时间、修订、来源、排除原因和发布边界，再让后续分析保持可追溯、
可重放、可反驳。

## P2G-1：事实 cohort（本补丁）

实施顺序：

1. 固定 P2F 发布基线并复跑定向/全仓测试；
2. 复用 canonical JSON、原子 I/O、review validator、revision validator 和 replay；
3. 定义 `p2g.behavior_cohort.v1` schema 与排除原因 registry；
4. 实现纯 selection/builder：双时间过滤、cutoff-aware leaf、稳定排序和 filters；
5. 实现 offline validation、query、load/save 和 exact source replay；
6. 接入 `behavior-cohort-build/show/validate` CLI；
7. 完成定向、P2F、全仓、clean-checkout、patch/tree/reverse 和 CI 门禁。

P2G-1 输出完整 P2F facts projection，因此后续信号层不需要重新打开 P2F source、
模型或数据库。

## 后续阶段（明确不属于本补丁）

- **P2G-2**：只在冻结 cohort 上计算 registry 驱动的 facts-only 行为信号；保留
  numerator、denominator、缺失状态和原始 fact/source refs。
- **P2G-3**：受约束的行为假设、替代解释、反方审查和 provenance；无安全解释时
  回退 facts-only。
- **P2G-4**：人工 accept/reject/correct、append-only hypothesis revision、
  merge/supersede/diff/render。
- **P2G-5**：端到端发布门禁及周/月观察报告；禁止单笔结果直接固化长期规则。

进入任一后续阶段前，都必须先有新的明确任务和对应门禁；P2G-1 的完成不自动授权。
