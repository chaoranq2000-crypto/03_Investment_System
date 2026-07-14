# R5 Bundle 13R 关闭读数

## 关闭结果

最新补丁包的 13R.0—13R.6 执行链已按允许状态 `R5_BUNDLE13R_BACKFLOW_IN_PROGRESS` 完成技术关闭。经营证据并未被伪装为 requalified：严格回流固化为 `6 resolved / 11 unresolved / 0 validation blockers`，研究质量结果为 `needs_fix`。

## 基线与补丁修复

- package: `R5_BUNDLE_13R_EVIDENCE_BACKFLOW_PACKAGE_20260715.zip`
- package_sha256: `c9fbd577647b2e7eba2c9269f57bcfedf4664d7008695d7643c80b83e9ea0a49`
- baseline commit: `64f6787beaf7b41807f3f41fefa305242e299004`
- canonical upstream generation: `op_evidence_gen_r5_bundle12r_fd5d23c5eb35ac27`
- backflow generation: `backflow_gen_r5_bundle13r_fb8cefccfaa93293`

原包错误绑定旧 `e356...` fixture generation，首次 baseline audit 因 generation 和四个哈希不一致而拒绝执行。修复后，正式 contract 绑定 canonical 12R 的四个物理哈希；旧结构仅保留在 fixture-only contract，原始失败审计和已解决 critical issue 均保留用于追溯。

## T1 / T2 结果

已解决的 6 项：

- 2025A revenue 与 gross-profit 分母；
- `room_cooling`、`cabinet_cooling`、`data_center_liquid_cooling_related` 三项独立暴露；
- room/cabinet 的 `disjoint` 关系。

未解决的 11 项：

- room/cabinet 的 `volume`、`unit_price`、`product_mix` 共 6 项；
- liquid-cooling 的 `unit_value`、`acceptance_rate`、`gross_margin` 共 3 项；
- room/liquid 与 cabinet/liquid 两组 `overlaps` 的收入和毛利扣减。

2026-07-15 live 刷新已登记 SZSE 和 CNINFO IR 新 evidence IDs、raw/normalized 路径及管理层表述候选，但没有同口径量化披露可以关闭上述缺口。2024A 液冷约 3 亿元仍是 `management_comment / bounded_estimate`，不与 2025A 机房、机柜产品线相加。

## 条件卡执行决定

| card | decision | reason |
|---|---|---|
| 13R.3 Bundle 12R rerun | not_executed | 13R decision 不是 `ready_for_bundle12r_rerun`；生成的命令仅保留为条件说明。 |
| 13R.4 valuation eligibility | not_executed | 未达到 `operating_evidence_requalified`；peer、DCF、SOTP 继续关闭。 |
| Reader / human review | not_triggered | 没有新 Reader；Bundle 11R 精确哈希人审不迁移。 |

## 验证

- baseline audit: `pass`。
- focused Bundle 13R: `19 passed`。
- historical forward-state compatibility: `20 passed`。
- full repository: `773 passed, 2 skipped, 33.25s`。
- generation lock: valid；同输入二次运行 8 个工件 `hash_drift_count=0`。
- evidence manifest/path/candidate validation: pass。
- workflow state、doc drift、YAML/CSV schema、AST compile、`git diff --check`: pass。

## 状态与后续触发器

- workflow status: `in_progress`
- current stage: `R5_bundle13r_t1_t2_evidence_backflow`
- required next skill: `evidence-ingest`
- next trigger: 新的、可定位、同期间且可量化的发行人正式经营披露
- open high TODOs: `R5B13R-DRIVER-001`、`R5B13R-OVERLAP-001`

## 边界

`human_review_status=pending`；`sample_quality_allowed=false`；`p2_allowed=false`。没有重算模型、生成 Reader、创建提交、推送分支或给出直接投资指令。
