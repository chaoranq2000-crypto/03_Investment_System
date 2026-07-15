# R5 Bundle 16R Real-Company Regression Close Readout

## 1. Identity and decision

- Bundle: `R5 Bundle 16R`
- Package: `R5_bundle16r_next_patch_20260715.zip`
- Package SHA-256: `cb7ee782665519f3140f9ef73376e68e9debf29a6fed6e884a4d6fb41f43242b`
- Package integrity: `15 / 15 PASS`
- Base commit: `1d4b1f151b97337d8def33c409532f28794b6652`
- Implementation commit: `NOT_CREATED_PACKAGE_STOPS_AT_NARROW_STAGING`
- Branch: `codex/r5-bundle16r-real-company-regression`
- Evaluator schema: `r5_bundle16r_real_company_regression_v1`
- Information cutoff: `2026-07-15`
- Close decision: `engineering_closed_human_pending`

The latest local archive was rediscovered immediately before close and remains Bundle 16R.
All four real-company cases now pass the automated engineering gate using reviewed official
disclosures and issuer-neutral generation code. Exact-hash human review is deliberately still
`pending`; therefore sample quality and P2 remain blocked.

## 2. Intended source scope

| Path | New / modified | Purpose | Why needed |
|---|---|---|---|
| `src/research/r5_bundle16r_real_company_regression.py` | new + narrow integration | deterministic four-case evaluator and issue-to-owner backflow metadata | supplied evaluator plus package-required failure routing |
| `config/r5_bundle16r_real_company_cases.yaml` | new | four-case registry, thresholds and release policy | supplied contract input |
| `tests/test_r5_bundle16r_real_company_regression.py` | new + narrow integration | evaluator adversarial, determinism and backflow tests | supplied coverage plus exact-hash backflow assertion |
| `docs/workflows/R5_REAL_COMPANY_REGRESSION_CONTRACT.md` | new | governing local contract | supplied workflow boundary |
| `codex_tasks/r5_bundle16r/R5_BUNDLE16R_TASK_CARD.md` | new | ordered execution requirements | supplied task card |
| `codex_tasks/r5_bundle16r/R5_BUNDLE16R_ACCEPTANCE_MATRIX.yaml` | new | non-compensating acceptance gates | supplied acceptance contract |
| `reports/p1_6/R5_BUNDLE16R_REAL_COMPANY_REGRESSION_READOUT_TEMPLATE.md` | new | readout template | supplied reporting surface |
| `scripts/build_r5_bundle16r_case_pack.py` | new | issuer-neutral adapter from reviewed case inputs to physical model/report artifacts | current upstream packs did not expose all Bundle 16R metrics |
| `tests/test_r5_bundle16r_case_pack_builder.py` | new | deterministic generation, strict reconciliation and failure routing tests | proves derived metrics are not hand-entered into manifests |
| `reports/p1_6/R5_BUNDLE16R_REAL_COMPANY_REGRESSION_CLOSE_READOUT.md` | new | actual close decision and handoff | required closing artifact |

Confirmed intended staging boundary:

- [x] no ZIP file is included;
- [x] `bundle16r/generated/` is excluded;
- [x] raw/processed official evidence, run-specific case inputs and parser outputs remain local;
- [x] caches, backups, screenshots and unrelated files remain excluded;
- [x] the pre-existing deletion of `r5_after_patch12_patch_package.zip` remains unstaged;
- [x] no commit, push or pull request was created because the user did not request publication.

The local evidence manifest and ingest-run ledger were updated to support reproducibility, but
remain outside the intended source staging boundary together with downloaded evidence. Six SSE
anti-bot HTML responses are preserved as failed/rejected records, bound to explicit rejection
notes, and superseded by valid CNINFO disclosures; none is eligible for material claims.

## 3. Automated results

| Gate | Result | Evidence |
|---|---|---|
| latest-package rediscovery | PASS | Bundle 16R remains the newest local ZIP; SHA-256 matches above |
| package integrity | PASS | 15 package checksum checks, 0 failures |
| registry validation | PASS | registry validates against `r5_bundle16r_real_company_regression_v1` |
| official evidence manifest | PASS | manifest schema and physical-path validators both pass |
| PDF review | PASS | 12 representative annual, quarterly, forecast, M&A and contract pages rendered and visually checked |
| case-builder tests | PASS | `3 passed` |
| evaluator focused tests | PASS | `18 passed` |
| full repository CI-equivalent | PASS | `812 passed, 2 skipped in 35.91s` |
| four-case physical artifacts | PASS | 9 required roles × 4 cases; all paths and SHA-256 values match |
| four-case generation determinism | PASS | 40 physical files byte-identical across two complete rebuilds |
| suite JSON determinism | PASS | both runs `4f89e4829a83d3f473d9bbb11b1d70c8fdaff353954cb6dae720eb61c28c3178` |
| suite Markdown determinism | PASS | both runs `1142d928010721cc5309dcfd652036492feb3ffa96233b34e91c5206d00e8919` |
| issuer-neutral runtime scan | PASS | no `issuer_specific_runtime_token`; suite `issues=[]` |
| real four-case suite | PASS | `engineering_pass=true`, `all_cases_present=true` |
| sample-quality release | BLOCKED AS DESIGNED | all four human reviews remain `pending` |
| P2 | BLOCKED AS DESIGNED | `p2_allowed=false` always under Bundle 16R |

Generated suite readouts are local and intentionally uncommitted:

```text
bundle16r/generated/readout/bundle16r_suite_readout.json
bundle16r/generated/readout/bundle16r_suite_readout.md
```

## 4. Four-case matrix

| Case | Reviewed official sources | Driver coverage | Revenue explained | Gross profit explained | Forecast traceability | Company metrics / future events | Valuation behavior | Human review | Engineering |
|---|---:|---:|---:|---:|---:|---|---|---|---|
| 301217 铜冠铜箔 | 2 | 1.00 | 1.00 | 1.00 | 1.00 | 11 / 2 | peer multiple disabled; scenario context only | `pending` | PASS |
| 600988 赤峰黄金 | 3 | 1.00 | 1.00 | 1.00 | 1.00 | 14 / 2 | peer multiple disabled; scenario context only | `pending` | PASS |
| 603259 药明康德 | 2 | 1.00 | 1.00 | 1.00 | 1.00 | 12 / 2 | peer multiple disabled; scenario context only | `pending` | PASS |
| 600673 东阳光 | 5 | 1.00 | 1.00 | 1.00 | 1.00 | 14 / 3 | peer multiple disabled; scenario context only | `pending` | PASS |

All four cases also have `citation_resolution_rate=1.00`,
`model_linked_core_section_ratio=1.00`, `section_novelty_ratio=1.00`, zero residual
revenue/gross-profit ratios, and zero unresolved critical questions. These metrics are computed
from reconciled upstream packs by the adapter and are not copied into inputs as gate values.

## 5. Evidence and backflow state

No automated engineering issue remains. Open items are either non-critical evidence refreshes or
the package-mandated human boundary.

| Issue / gap | Case | Owning stage / skill | Exact next step | Status |
|---|---|---|---|---|
| high-end product unit economics | 301217 | `evidence-ingest` + `stock-deep-dive` | on the next interim/annual filing, add grade-level sales, processing fee or margin evidence if disclosed | open_noncritical |
| quarterly cost normalization | 600988 | `refresh-research` + `stock-deep-dive` | replace the H1 forecast anchor with formal half-year production, price, unit cost and AISC data | open_noncritical |
| backlog conversion interval | 603259 | `refresh-research` + `stock-deep-dive` | update backlog-to-revenue conversion from half-year revenue, backlog and project-stage changes | open_noncritical |
| project acceptance economics | 600673 | `evidence-ingest` + `refresh-research` | add delivery, acceptance, utilization, revenue, cost and cash collection evidence as disclosed | open_noncritical |
| acquisition close and consolidation | 600673 | `refresh-research` + `quality-review` | track approval, registration, antitrust, closing, financing cost and consolidation date | open_noncritical |
| exact-hash review | all four | review handoff / `research-orchestrator` | a named real reviewer must inspect each Reader and sign the exact Reader/lock hashes below | pending_blocking_sample_quality |

The generic adapter routes future metric failures to their actual owners: operating-driver engine,
forecast model, report planner/semantic quality, evidence/research-question planner or quality
review. The evaluator routes physical/hash failures to the artifact producer, issuer hardcoding to
runtime integration, peer failures to valuation eligibility, and exact-hash failures to review
handoff.

## 6. Exact-hash human-review binding

No automated process filled reviewer identity, timestamp or acceptance.

| Case | Review status | Reviewer | Reviewed at | Reader SHA-256 | Generation-lock SHA-256 | Accepted exact match |
|---|---|---|---|---|---|---|
| 301217 | `pending` | blank | blank | `102fa201d16d980a5c813e095928c725e9b9cfc22cc342c5ef71e3eaf28981fa` | `02953ca1a4f932e34a1298ab3e883c66daf26fc3cffbac96c4137b764b64f461` | false |
| 600988 | `pending` | blank | blank | `edc6e089537e64e4bbcc7578e02465cfa6d0d5c259f575e6f0eeff5e716b6030` | `5cffa5fee240c6bb3c9f7bbf3b07d7cf4c2e8c799e1f07aa839cfb2449a3f0d1` | false |
| 603259 | `pending` | blank | blank | `04ec8a53a023c3678dfdb7682901c5b229b7040c86af216930b0b4eea739f701` | `80d673824269e8a65083e36694d4f64eaed0bd6380362cac9b25c8f6a1e0375f` | false |
| 600673 | `pending` | blank | blank | `2fc4dff78527743b5fa884df4c5329ef4cd014c73686e1b10cef7edff45daed9` | `cd445f4dade57e60f446dd0c5b747db4c298e4da5d2c0db11f1c4d3f9813c24e` | false |

Any Reader or generation-lock change invalidates these handoff hashes and requires regeneration
before a reviewer can accept.

## 7. Canonical state decision

```yaml
bundle16r_patch_harness_status: validated
bundle16r_engineering_status: closed
bundle16r_quality_decision: engineering_closed_human_pending
package_task_chain_processed: true
all_four_cases_present: true
all_four_engineering_pass: true
all_four_exact_hash_human_reviews_accepted: false
sample_quality_allowed: false
p2_allowed: false
next_stage: bundle16r_exact_hash_human_review
```

No existing canonical P2 state was modified. Engineering close is an explicit package state and
does not imply sample-quality acceptance.

## 8. Residual risks

- Forecast values are declared scenario estimates, not issuer guidance, consensus or price targets.
- Peer multiples remain disabled for all four cases because no three-company, definition-compatible,
  period-aligned peer set was reviewed; no ranking is produced from low-confidence proxies.
- 301217 still lacks grade-level high-end product profitability; 603259 still lacks a single disclosed
  backlog conversion interval.
- 600988 H1 data remain an unaudited management estimate until the formal half-year report.
- 600673 compute-service contract amounts are contract estimates, not revenue; acquisition effects
  remain zero until the transaction closes and a consolidation date is supportable.
- Bundle 17R and P2 are not opened by this close. The next authorized action is real human review of
  the four exact-hash Readers, followed by a separate canonical decision if all are accepted.
