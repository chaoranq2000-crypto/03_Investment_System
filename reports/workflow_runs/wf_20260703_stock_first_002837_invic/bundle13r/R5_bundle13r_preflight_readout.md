# R5 Bundle 13R — Preflight 阻断读数

> 状态说明（2026-07-15）：本文主体保留原始包的首次 preflight 诊断。两项 critical 已完成修复；当前权威基线见 `baseline_audit.yaml`（`decision=pass`），原始失败证据保存在 `baseline_audit_original_package.yaml`。后续严格回流已进入 `backflow_execution_in_progress`。

## 结论

Bundle 13R 的实现补丁已成功应用并通过实现层测试，但 **13R.0 基线与哈希绑定未通过**。本轮在 T1/T2 之前安全停止，未把测试夹具内容推广为正式经营证据。

当前状态：`needs_fix_before_bundle13r_execution`。这是一项 preflight 诊断状态，不冒充包内允许的 13R 关闭状态。

## 输入与基线

- package: `R5_BUNDLE_13R_EVIDENCE_BACKFLOW_PACKAGE_20260715.zip`
- package_sha256: `c9fbd577647b2e7eba2c9269f57bcfedf4664d7008695d7643c80b83e9ea0a49`
- observed_head: `64f6787beaf7b41807f3f41fefa305242e299004`
- observed_branch: `main`
- baseline_commit_match: `true`
- expected_bundle12r_generation: `op_evidence_gen_r5_bundle12r_e3567efdc999aa91`
- observed_bundle12r_generation: `op_evidence_gen_r5_bundle12r_fd5d23c5eb35ac27`

## 已完成

1. 校验压缩包 SHA256、包内 `SHA256SUMS`、manifest 和 33 个 payload 文件。
2. 运行集成工具 `--check --allow-dirty`，确认补丁可无冲突应用到当前 HEAD。
3. 应用 33 个新增实现文件；逐文件比对 payload，结果 `missing=0`、`mismatch=0`。
4. 聚焦测试通过：`17 passed`。
5. 全仓测试通过：`771 passed, 2 skipped`。
6. 运行真实 13R baseline audit，输出 `baseline_audit.yaml`，决策为 `needs_fix`。

## Critical 阻断

### 1. generation 与物理哈希错误绑定

13R 合同绑定的是旧 12R 包的 `validation_artifacts/invic_gap` 测试夹具，而不是当前 canonical 12R 运行。

| artifact | 13R 绑定哈希 | canonical 12R 物理哈希 |
|---|---|---|
| `R5_bundle12r_backflow_plan.yaml` | `159581e28354f24723bdb5188e0d680ca53228f42898eb0b0fc8d19e833efb77` | `8aacce378fc1b4838d9470770b71a82efb0ba614fe2ab3917059904485c5103f` |
| `R5_bundle12r_operating_evidence_input_snapshot.yaml` | `00a6db8aa57f036d2ae9ed2c3c873a22da1b55a26e7e5dc9781cd66fe0e9f418` | `9de6bc0588d0e27fb43d8071379880dfe02cd4b22218a5991cd11d177a3d203f` |
| `R5_bundle12r_operating_evidence_result.yaml` | `d5fab0526bff6e7e767a1f81f8090e27b58cc623749bd77329c8bb07ff3a14b8` | `6bd9ff2064babdb013eb16b58f8b0b0dba2b89c7a9f2d8dd079ef6fbdf739eec` |
| `R5_bundle12r_research_question_plan.yaml` | `d286da50cfc634541bccb90cd15c4f75ec57054de851833062f27569e8bdbd41` | `4260648fa3a9871dcea6031e2cb62af9141a46e4b2fd5709867aa1dd1bec0407` |

### 2. 研究对象结构不兼容

- 13R 夹具模板：`broad_data_center_thermal`、`liquid_cooling_related`，11 个问题。
- canonical 12R：`room_cooling`、`cabinet_cooling`、`data_center_liquid_cooling_related`，13 个问题。
- 夹具驱动使用 `project_count / unit_value / acceptance_rate / gross_margin`；真实 12R 还使用 `volume / unit_price / product_mix`。

因此不能只替换 generation ID 和哈希；必须重新生成 reviewed-backfill 模板、执行合同、夹具和相应测试。

## 未执行与边界

- 未调度 `evidence-ingest` 或 `stock-deep-dive`，因为 13R.0 critical 门禁未通过。
- 未生成、推广或修改任何正式经营证据。
- 未重跑 Bundle 12R。
- 未启动 `company-valuation`、Reader 重建或人工审阅继承。
- 未修改 canonical `workflow_state.yaml`、12R 历史、raw evidence、sample-quality 或 P2 状态。
- `human_review_status` 不提升；`sample_quality_allowed=false`；`p2_allowed=false`。

## 修复 owner 与下一步

- owner: `research-orchestrator`
- severity: `critical`
- next_action: 基于 canonical generation `op_evidence_gen_r5_bundle12r_fd5d23c5eb35ac27` 及其真实 question/segment/driver 结构重新生成 13R 包；重新校验物理哈希、负向测试、聚焦测试和全仓测试后，再从 13R.0 重启。

## 修复结果（2026-07-15）

- 13R contract 已绑定 canonical generation `op_evidence_gen_r5_bundle12r_fd5d23c5eb35ac27` 和四个真实物理哈希。
- 正式 reviewed-backfill 模板已改为 `room_cooling`、`cabinet_cooling`、`data_center_liquid_cooling_related`，包含九个 T1 驱动响应和三组物理 overlap。
- 旧 `e356...` 结构被隔离到 fixture-only contract；canonical 入口新增精确哈希、队列计数和 stale-fixture 拒绝测试。
- 修复后 baseline audit 为 `pass`；严格回流为 `6 resolved / 11 unresolved / 0 blockers`，没有跳过哈希检查。
