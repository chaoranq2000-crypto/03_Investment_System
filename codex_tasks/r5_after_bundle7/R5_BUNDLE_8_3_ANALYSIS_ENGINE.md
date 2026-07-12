# R5 Bundle 8.3 — Analysis Pack v2

## 目标

解决 `insufficient_analytical_unit_coverage`，用证据—机制—财务影响—反证—验证指标的闭环替换“字段非空即 ready”。

## 输入

- 通过门槛的 `evidence_coverage_matrix.yaml`；
- source-only evidence packs；
- 分析师填写的 `R5_bundle8_analysis_inputs_v2.yaml`。

## 输出

- `analysis_pack_v2.yaml`
- `thesis_tree.yaml`
- `business_driver_tree.yaml`
- `segment_economics.yaml`
- `competitive_position_matrix.yaml`
- `risk_counterevidence_pack.yaml`

## 必须满足

- 七个必需章节各至少一个 complete 单元；
- 所有 source/metric 引用可解析；
- 每个单元有反证、可证伪条件和观察指标；
- 行业、竞争和风险使用独立来源；
- 财务、业务驱动和分业务经济性含发行人来源；
- 不能用通用空话、重复文本或缺失标记获得 complete；
- pack 必须从 source catalog、coverage matrix 与 analysis inputs 可重复重建。
