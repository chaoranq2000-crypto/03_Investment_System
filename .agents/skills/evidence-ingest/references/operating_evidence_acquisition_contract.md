# evidence-ingest — 经营证据采集合同

对每一个 Bundle 12R research question，`evidence-ingest` 必须返回：

- `driver_id`；
- `status`：confirmed / bounded_estimate / missing / conflicting；
- `value` 或 `lower_bound` / `upper_bound`；
- `unit`、`period`；
- `source_tier`、`confidence`；
- `evidence_ids` 与 locator；
- `financial_mapping`；
- 必要时 `methodology`。

不得用行业规模、产品存在、客户意向或管理层叙事自动替代公司收入、利润、项目验收和现金回款数据。

## 当前资格边界

该证据资格规则也适用于普通 operating-driver handoff，但不加载任何 Bundle
工序。`missing` 与 `conflicting` 不能由更长文本、其他能力的高分或总分抵消，
也不能为了完成模型而改写成数值。

业务线只有在独立量化指标、证据锚点、期间和单位均明确，且能够与更宽口径
分部协调、重叠已经分配或扣除时，才可支持完整 SOTP 或业务线级同业经营比较。
不满足时保留可见缺口，并由估值方法选择规则决定可用的降级方法；不得激活旧
Bundle 文档中的固定方法数量门槛。
