# R5 Bundle 15R Close Readout

## 1. 执行结论

```yaml
engineering_implementation: complete
reviewed_evidence_qualification: operational
real_case_ready_count: 0
close_status: accepted_with_visible_evidence_blockers
canonical_workflow_state_mutated: false
sample_quality_allowed: false
p2_allowed: false
```

本次完成的是 Bundle 15R 工程实现和 fail-closed 运行验证，不代表四个真实案例已经完成研究复核。现有官方材料的 manifest 状态为 `reviewed`，但没有具名 reviewer，也没有 `accepted` / `accepted_with_limitations` 的 pack 级人工复核，因此不得构造可放行的 reviewed evidence pack。

## 2. Identity

- Base commit: `60f3e24af8572faaf1c7a9b12a37b4ac085d7b36`
- Implementation commit: `not_created`（补丁要求未经另行授权不得 commit/push）
- Branch: `codex/r5-bundle15r-reviewed-evidence-qualification`
- CI run: `not_run`（未 push）
- Qualification generation ID: `evidence_qualification_gen_r5_bundle15r_5d58d351d87c96fb`
- Bundle 14R generation ID: `golden_regression_gen_2d63ad9888407437`
- Package patch SHA-256: `b0e31b43db6e34b9acc60f0ae069ae68d4451aa63abbd81f51cbc8bba041e4e1`

## 3. Scope actually changed

以下 16 个仓库路径均为新增；除本 close readout 按真实结果填写外，其余内容来自补丁清单。

| Path | Change | Purpose |
|---|---|---|
| `.github/workflows/r5-bundle15r-evidence-qualification.yml` | added | Bundle 15R 专项 CI |
| `codex_tasks/r5_bundle15r/00_BASELINE_AND_SCOPE.md` | added | 基线与范围卡 |
| `codex_tasks/r5_bundle15r/01_INSTALL_AND_SEED.md` | added | 安装与 seed 卡 |
| `codex_tasks/r5_bundle15r/02_BUILD_REVIEWED_EVIDENCE_PACKS.md` | added | evidence pack 卡 |
| `codex_tasks/r5_bundle15r/03_COMPILE_AND_QUALIFY.md` | added | 编译资格卡 |
| `codex_tasks/r5_bundle15r/04_RUN_BUNDLE14R_SELECTIVELY.md` | added | 14R 选择性运行卡 |
| `codex_tasks/r5_bundle15r/05_EXACT_HASH_REVIEW_AND_CLOSE.md` | added | exact-hash close 卡 |
| `codex_tasks/r5_bundle15r/README.md` | added | 任务链索引 |
| `config/r5_bundle15r_evidence_qualification_policy.yaml` | added | 资格策略 |
| `docs/plans/R5_BUNDLE15R_REVIEWED_EVIDENCE_QUALIFICATION_PLAN.md` | added | 永久实施计划 |
| `docs/workflows/R5_BUNDLE15R_REVIEWED_EVIDENCE_QUALIFICATION.md` | added | 工作流合同 |
| `reports/p1_6/R5_BUNDLE15R_CLOSE_READOUT_TEMPLATE.md` | added and filled | 本次真实 close readout |
| `schemas/r5_bundle15r_reviewed_evidence_pack.schema.yaml` | added | evidence pack schema |
| `scripts/run_r5_bundle15r_evidence_qualification.py` | added | CLI runner |
| `src/research/r5_bundle15r_evidence_qualification.py` | added | qualification compiler |
| `tests/test_r5_bundle15r_evidence_qualification.py` | added | 聚焦测试 |

确认：

- 未改写 Bundle 14R runtime、四个 issuer workflow state、canonical artifact index、raw evidence 或既有报告。
- ZIP、缓存、外部 seed、生成目录和本地日志均不属于暂存范围。
- 补丁前已有的 2 个 modified、1 个 deleted、139 个 untracked 状态行仍保持原状态并留在暂存区外。
- 补丁清单之外没有新增拟暂存路径。

## 4. Automated validation

| Check | Result | Evidence |
|---|---|---|
| Exact baseline | PASS | `git rev-parse HEAD` → `60f3e24af8572faaf1c7a9b12a37b4ac085d7b36` |
| Patch integrity | PASS | package patch SHA-256 matches manifest |
| Apply check | PASS | `git apply --check` exit `0` |
| Python compile | PASS | Conda Python `3.12.13`; Bundle 15R module/CLI and repository Python compile exit `0` |
| Bundle 15R tests | PASS | `23 passed in 0.59s` |
| Empty-pack seed | PASS | two runs; each `4` cases, `0` packs, `0` complete, `0` ready |
| 15R seed determinism | PASS | output `14/14` files, scaffold `4/4` files, differing files `0` |
| Bundle 14R tests | PASS | `12 passed in 0.84s` |
| 15R → 14R selective rerun | PASS | 15R `14/14` files diff `0`; 14R `4/4` files diff `0`; return code `0` |
| Full repository tests | PASS | `847 passed, 2 skipped in 36.57s` |
| Git whitespace | PASS | `git diff --check` 与 `git diff --cached --check` 均为 exit `0` |
| Runtime generality scan | PASS | issuer names/tickers in generic runtime targets: `0` hits |
| Sensitive-pattern scan | PASS | credential/private-key patterns in 16 target paths: `0` hits |
| Ruff | NOT RUN | project Conda env 未安装 Ruff；现行 CI 不要求，未临时安装 |

所有 seed、scaffold、qualification 和 Bundle 14R 结果均写到仓库外：

`C:\Users\Q\AppData\Local\Temp\codex_bundle15r_qualification_019f65bd9e547f71`

## 5. Pre-existing worktree preservation

- 完整 Git 状态库存前后均为：`M=2`、`D=1`、`??=139`，合计 `142` 条状态行。
- 补丁只新增 manifest 声明的 16 个路径；应用时这 16 个路径均为 `??`，没有既有路径被 `git apply` 修改。
- 补丁前哈希快照经工具回传时有 6 个文件行被截断，故可做严格 SHA-256 前后逐项比较的是 `254/261` 个既有文件；这 254 个全部一致、0 个 mismatch。
- 剩余 7 个文件没有形成可复核的补丁前哈希记录，因此本 readout 不宣称 `261/261` 的哈希证明。它们仍受完整 Git 状态库存、add-only apply check 和操作范围约束保护。

该快照截断是审计证据覆盖限制，不是已观察到的文件变更。

## 6. Reviewed evidence inventory

现有 A 级、active、parsed 官方材料与 pack 级接受状态如下：

| Ticker | Active parsed A sources | Manifest `reviewed` | Pack-eligible accepted | Rejected |
|---|---:|---:|---:|---:|
| `301217` | 2 | 2 | 0 | 0 |
| `600988` | 3 | 3 | 0 | 2 |
| `603259` | 2 | 2 | 0 | 2 |
| `600673` | 5 | 5 | 0 | 2 |

Bundle 16R 的生成物和 Reader 不作为 15R evidence；四份 `human_review.yaml` 均为 `status: pending`、`reviewer: ''`，不能反向替代具名人工接受。

## 7. Four-case qualification

| Case | Accepted pack sources | Qualified drivers | Questions | Overlap | Forecast | Valuation | Semantic/lock | Bundle 14R | Human review |
|---|---:|---:|---:|---|---|---|---|---|---|
| 铜冠铜箔 / `301217.SZ` | 0 | 0/8 | 0/6 | blocked | blocked | ineligible | not passed | pending | not triggered |
| 赤峰黄金 / `600988.SH` | 0 | 0/9 | 0/6 | blocked | blocked | ineligible | not passed | pending | not triggered |
| 药明康德 / `603259.SH` | 0 | 0/11 | 0/7 | blocked | blocked | ineligible | not passed | pending | not triggered |
| 东阳光 / `600673.SH` | 0 | 0/18 | 0/9 | blocked | blocked | ineligible | not passed | pending | not triggered |

注意：表中的 `Semantic/lock` 指每个真实 evidence pack 的放行门；Bundle 15R/14R 工程 seed 本身已经证明 deterministic rerun 通过。

## 8. Remaining blockers and backflow

| Case | Issue | Stage | Skill | Evidence request | Trigger |
|---|---|---|---|---|---|
| `golden_copper_foil_product_generation` | `PACK_MISSING` | `T1_evidence_plan` | `evidence-ingest` | 具名复核的产能/利用率/良率/产品结构/加工费/营运资金证据 pack | pack reviewer、timestamp、physical hash 和 accepted 状态齐备 |
| `golden_gold_mining_cycle` | `PACK_MISSING` | `T1_evidence_plan` | `evidence-ingest` | 矿山产量/品位/回收率/成本/剥采/capex 证据 pack | 同上 |
| `golden_crdmo_backlog_conversion` | `PACK_MISSING` | `T1_evidence_plan` | `evidence-ingest` | backlog 定义/转化/阶段结构/产能/监管过渡/现金证据 pack | 同上 |
| `golden_multi_business_ai_infrastructure` | `PACK_MISSING` | `T1_evidence_plan` | `evidence-ingest` | 制冷剂/材料/液冷/IDC/并购融资分链证据 pack | 同上 |

下一步不是让 Writer 补叙事，而是由具名 reviewer 对物理归档官方材料和 driver/question 映射做 pack 级接受；完成后重新运行 Bundle 15R，再由生成的 owner/stage backflow 推进。

## 9. Machine-readable truthfulness fields

```yaml
status: accepted_with_visible_evidence_blockers
files_added:
  count: 16
  source: PATCH_MANIFEST.yaml
files_modified: []
commands_run:
  - git apply --check <bundle15r.patch>
  - conda run -p ./.conda/investment-system python -m py_compile <repository python files plus Bundle 15R files>
  - conda run -p ./.conda/investment-system python -m pytest -q tests/test_r5_bundle15r_evidence_qualification.py
  - conda run -p ./.conda/investment-system python scripts/run_r5_bundle15r_evidence_qualification.py <empty-pack seed A and B>
  - conda run -p ./.conda/investment-system python -m pytest -q tests/test_r5_bundle14r_golden_regression.py
  - conda run -p ./.conda/investment-system python scripts/run_r5_bundle15r_evidence_qualification.py --run-bundle14r <run A and B>
  - conda run -p ./.conda/investment-system python -m pytest -q
  - git diff --check
  - git diff --cached --check
exit_code:
  apply_check: 0
  python_compile: 0
  bundle15r_pytest: 0
  bundle15r_seed_a: 0
  bundle15r_seed_b: 0
  bundle14r_pytest: 0
  selective_chain_a: 0
  selective_chain_b: 0
  full_pytest: 0
  git_diff_check: 0
  git_cached_diff_check: 0
stdout_or_stderr_summary:
  bundle15r_pytest: 23 passed in 0.59s
  bundle14r_pytest: 12 passed in 0.84s
  full_pytest: 847 passed, 2 skipped in 36.57s
  deterministic_differing_files: 0
  runtime_issuer_token_hits: 0
  sensitive_pattern_hits: 0
known_todos:
  - 4 cases need named accepted reviewed-evidence packs
  - exact-hash human review is not triggered
  - pre-patch hash capture covers 254 of 261 pre-existing files; status inventory covers all 142 rows
next_recommended_patch: none; perform the owned T1 reviewed-evidence human-review handoff, then rerun Bundle 15R
inventory_status: 16 declared add-only paths; 0 extra staged paths expected
```

## 10. Governance result

```yaml
release_authority: false
canonical_workflow_state_mutated: false
exact_hash_human_review_status: not_triggered
sample_quality_allowed: false
p2_allowed: false
commit_created: false
push_performed: false
```
