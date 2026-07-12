# R5 Bundle 8.1 — Evidence Coverage Matrix

## 目标

将 Bundle 7 的 `independent_research_evidence_below_minimum` 和 `peer_operating_evidence_missing` 转化为可审计的来源覆盖矩阵，而不是继续按 Evidence 卡数量计数。

## 输入

- 现有 reviewed evidence；
- 新增公司公告、IR、客户/项目/订单线索；
- 行业协会、监管/政府、研究机构数据；
- 至少三家真正可比公司的定期报告或经营披露。

## 输出

- `R5_bundle8_evidence_source_catalog.yaml`
- `evidence_coverage_matrix.yaml`
- `company_operating_evidence_pack.yaml`
- `peer_operating_pack.yaml`

## 必须满足

- 以 `underlying_source_id` 去重；
- 未审查和过期来源不得计数；
- 至少四个独立底层来源；
- 至少三家独立同业实体有经营数据；
- 所有缺口保持显式，不得推断补齐；
- 生成物可从 source catalog 可重复重建。

## 禁止事项

- 不改 Reader；
- 不改 forecast/valuation；
- 不把搜索结果摘要直接升级为 reviewed evidence；
- 不关闭 workflow TODO。
