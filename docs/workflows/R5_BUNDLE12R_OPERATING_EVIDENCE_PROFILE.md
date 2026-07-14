# R5 Bundle 12R — 经营证据资格化与估值方法资格 Profile

> 本文件是 `stock-deep-dive` / `research-orchestrator` 的局部执行 profile。
> 它不新增永久 `workflow_type`，不定义新的全局 `G` gate，也不覆盖
> `docs/workflows/RESEARCH_WORKFLOW.md` 的全局接口。

## 1. 基线与边界

Bundle 12R 以 `main@c155e0791adc6e65fc3c9c203f65b832a7f39980` 为最低祖先基线。
Bundle 11R 的精确哈希人工复核属于已锁定历史事实，Bundle 12R 不修改、不继承、不重写该复核。

Bundle 12R 只解决以下问题：

1. 将经营信息统一标记为 `confirmed / bounded_estimate / missing / conflicting`；
2. 将重大业务线绑定到可组合经营驱动 archetype；
3. 量化收入、毛利和关键驱动覆盖；
4. 显式识别宽口径业务与独立业务暴露之间的包含、重叠和重复计算；
5. 独立判断同业倍数、DCF 和 SOTP 是否具备输入资格；
6. 把失败项路由回证据、个股研究或估值步骤。

Bundle 12R 不得把自动门升级为：

- 样例质量授权；
- P2 授权；
- 旧 Reader 人审继承；
- 直接买卖、目标价或仓位建议。

## 2. 局部执行链

```text
T1 公司证据
  → RP-12R-1 经营业务线与 archetype 识别
  → RP-12R-2 经营问题计划
  → RP-12R-3 经营观察值资格化
  → RP-12R-4 重叠与残差协调
  → RP-12R-5 收入/毛利/驱动覆盖门
  → RP-12R-6 同业/DCF/SOTP 方法资格
  → RP-12R-7 backflow 或 generation lock
```

唯一局部门为 `RP-12R-OE`；不得使用新的全局 `G` 编号。

## 3. 释放下限

- 重大业务线均绑定已登记 archetype；
- 重大业务线 essential driver 覆盖率至少 80%；
- 收入经营解释覆盖率至少 80%；
- 毛利经营解释覆盖率至少 70%；
- 未解释 residual 不超过 20%；
- overcoverage 不超过 2%；
- 重大业务线具备独立量化暴露；
- 同业、DCF、SOTP 分别独立判定资格，不允许互相补偿。

## 4. 失败路由

| 问题 | 返回阶段 | owner skill |
|---|---|---|
| 关键经营变量缺失、来源等级不足 | T1 | `evidence-ingest` |
| 业务定义、重叠、残差、独立暴露失败 | T2 | `stock-deep-dive` |
| 同业定义、DCF 或 SOTP 输入资格失败 | RP6 | `company-valuation` |
| 输入身份或 schema 失败 | T0 | `research-orchestrator` |

## 5. 真实回归边界

仓库内 fixture 只能证明代码、Schema、重叠门和方法资格逻辑可复现。
四个真实公司回归必须使用审阅后的官方来源包；样例报告只作为分析维度与叙事密度参考，不能作为事实证据。
