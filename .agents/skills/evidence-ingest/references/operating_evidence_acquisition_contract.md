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
