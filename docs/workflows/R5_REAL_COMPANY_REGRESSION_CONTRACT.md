# R5 Real-Company Golden Regression — Historical Contract

## 1. Purpose

Bundle 16R was a four-company regression evaluator for materially different
economic models. Its implementation, case-pack builder, case registry and
dedicated tests were retired in Git commit
`274d47ec299a42946bc3b83f7908257e80f0f99b` on 2026-07-27
(`chore(v1): remove retired bundle workflow history`). This document remains
as a historical contract for interpreting retained artifacts and fixed Git
generations; it does not describe an installed or callable four-case evaluator.

The sections below preserve the retired evaluator's case definitions, artifact
fields and local quality requirements. They do not set current report standards,
release gates or T0–T10 routing. Current workflow and review decisions remain
owned by `RESEARCH_WORKFLOW.md` and its workflow-state schema. Historical
per-case human-review, reviewer-authority and exact-hash records remain read-only
compatibility evidence.

The historical contract addressed one question:

> Can one issuer-neutral research runtime produce decision-useful, traceable and economically grounded research across four different business-model families without promoting sample prose into evidence?

A historical engineering pass is not a current sample-quality pass. This
contract authorizes neither P2 nor a write to canonical `workflow_state.status`.

## 2. Historical golden regression cases

| Case | Primary model family | Required operating bridge |
|---|---|---|
| 301217 铜冠铜箔 | high-end manufacturing / product generation | product generation + processing fee + capacity/utilization + certification → segment revenue and gross profit |
| 600988 赤峰黄金 | cyclical resource mining | commodity price + volume + grade/recovery + unit cost + capex/ramp → mine/product profit and cash flow |
| 603259 药明康德 | backlog and project-funnel services | backlog + project stage + conversion/recognition + capacity/mix → revenue, margin and risk scenarios |
| 600673 东阳光 | multi-business + project + acquisition | quota/price, manufacturing capacity, project acceptance, IDC utilization and deal consolidation → segment model and valuation eligibility |

The four sample reports supplied outside the repository served only as
narrative-density references for research dimensions, adversarial tests and
expected analytical emphasis. Their historical role does not make them evidence:
they must not be cited as facts, copied into evidence packs or used to seed
numeric model inputs.

## 3. Historical machine artifacts per case

The machine-artifact contract bound the following roles to physical,
repository-relative files and SHA-256 hashes within the historical generation:

1. `workflow_state`
2. `evidence_pack`
3. `operating_driver_pack`
4. `forecast_model`
5. `valuation_pack`
6. `reader_report`
7. `quality_readout`
8. `generation_lock`

A missing file, path escape, duplicate role or hash mismatch failed the local
Bundle16R artifact check. Historical paths and hashes must be assessed against
their recorded generation, including fixed Git recovery for retired files;
absence from the current worktree is not a new current-run failure by itself.
Any present issue is classified under the current workflow's scoped truth table.

The hashes on all eight roles, including `generation_lock`, recorded machine
integrity and reproducibility. Some historical generations also bound a ninth
`human_review` role. It may be read only as compatibility evidence, never as
current reviewer authority or as a source of the canonical automatic outcome
or `sample_quality_ready`.

## 4. Historical case-result manifest

The retired case-result schema used the following `<case_id>.json` structure.
This example preserves its fields and does not request a new case generation:

```json
{
  "schema_version": "r5_bundle16r_real_company_regression_v1",
  "case_id": "301217_high_end_copper_foil",
  "ticker": "301217",
  "issuer_name": "铜冠铜箔",
  "artifacts": [
    {
      "role": "evidence_pack",
      "path": "reports/workflow_runs/<run>/evidence_pack.json",
      "sha256": "<64 lowercase hex>",
      "source_class": "evidence"
    }
  ],
  "metrics": {
    "material_segment_driver_coverage": 0.85,
    "revenue_explained_ratio": 0.82,
    "gross_profit_explained_ratio": 0.81,
    "residual_revenue_ratio": 0.18,
    "residual_gross_profit_ratio": 0.19,
    "forecast_assumption_traceability": 0.95,
    "model_linked_core_section_ratio": 0.8,
    "section_novelty_ratio": 0.75,
    "citation_resolution_rate": 1.0,
    "company_specific_metric_count": 10,
    "future_event_model_link_count": 3,
    "qualified_peer_count": 3,
    "unresolved_critical_question_count": 0
  },
  "valuation": {
    "peer_multiple_used": true,
    "peer_definition_compatible": true,
    "peer_periods_aligned": true,
    "alternative_method": "none"
  },
  "truthfulness": {
    "sample_text_used_as_evidence": false,
    "management_guidance_recast_as_fact": false,
    "low_confidence_peer_ranked": false,
    "direct_trading_instruction_present": false,
    "past_event_presented_as_future": false,
    "undisclosed_segment_economics_presented_as_fact": false,
    "consensus_estimate_presented_as_issuer_fact": false
  }
}
```

The historical contract required metrics computed by upstream packs or a
documented adapter; values entered solely to satisfy the gate were not valid.

## 5. Historical operating-model quality floor

The retired evaluator did not accept generic prose as a substitute for a model.
Its local quality floor was the following; these fixed thresholds are retained
to interpret old results, not to redefine current report or release requirements:

- at least 80% of material segments bound to an explicit economic-driver contract;
- at least 80% of revenue explained by driver output;
- at least 80% of gross profit explained by driver output;
- residual revenue and gross profit each no more than 20%, explicitly labeled;
- at least 90% of material forecast assumptions traceable to evidence or declared estimate logic;
- at least 75% of core report sections linked to model or evidence objects;
- at least 70% section novelty so repeated thesis text cannot inflate quality;
- 100% citation resolution;
- at least 8 company-specific metrics;
- at least 2 future event-to-model links;
- zero unresolved critical research questions.

The historical contract required unresolved critical questions to remain
visible as `unknown` or `method_unavailable`, without passing them through a
generic proxy. Current treatment remains governed by `RESEARCH_WORKFLOW.md`:
using the missing input requires `needs_fix`; visible unused unknowns may allow
`accepted_with_todos`. Severity alone does not decide the current outcome.

## 6. Historical peer and valuation behavior

The retired evaluator permitted peer multiples only when:

- at least three peers pass operating-definition qualification;
- forecast periods are aligned;
- product/service boundaries and accounting definitions are compatible; and
- the report does not rank low-confidence peers.

When these conditions were not met, the case had to disable peer-multiple
conclusions and use an eligible fallback such as reverse valuation, scenario
valuation or an asset-value range. DCF and SOTP were subject to their upstream
eligibility rules. Current method eligibility continues to belong to the
applicable research and valuation contracts.

## 7. Historical anti-hardcoding rule

The historical harness required the same runtime to serve all four companies.
Issuer names, tickers and case-specific product labels were allowed in:

- the Bundle 16R case registry;
- case manifests and generated artifacts;
- benchmark metadata and test fixtures.

They were not allowed in the generic runtime implementation under
`src/research`, the orchestrator, stock-deep-dive, quality-review or general
scripts. The retired evaluator scanned those paths and failed when registered
issuer-specific tokens appeared outside explicit allow paths. This records
historical test coverage; this contract does not install a current scan.

## 8. Historical exact-hash review records

Older Bundle16R generations may contain one human-review record per case,
binding Reader report and generation-lock hashes. Those records preserve what
the legacy evaluator required at that historical generation; they are
read-only and must not be copied, refreshed, promoted or used to approve a
current report.

Active V1 has no per-case or generation-lock human approval. Current artifact
verification and scoped issue decisions follow `RESEARCH_WORKFLOW.md`, without
requiring the retired four-case evaluator. The only active human boundary is
the one final report named in
`final_report_review.report_path`, whose current bytes are bound by
`final_report_review.report_sha256`. That review uses
`final_report_review_status: not_requested|pending|approved|changes_requested`
and the record fields defined by the active workflow-state schema.

Automated jobs must never synthesize reviewer identity, review time,
approval or change requests. A historical Bundle reviewer or accepted decision
cannot satisfy the current final-report review.

## 9. Historical result semantics and current authority

| Historical state | Meaning |
|---|---|
| `engineering_pass=false` | one or more physical, truthfulness, model, semantic or hardcoding gates failed |
| `engineering_pass=true` | the recorded harness and four cases passed their local machine checks in that generation; this does not set current canonical status |
| historical `sample_quality_allowed` | read-only compatibility fact about the old four-review policy; ignored by active routing and never imported into `sample_quality_ready` |
| historical `p2_allowed` | read-only compatibility field; a separate canonical decision is always required |

The retired evaluator supplies no current state transition. Historical findings
do not automatically become active issues. When a current request independently
reevaluates a finding from those records, it uses the current workflow's existing
issue fields:

```text
impact_scope
active_disposition
affected_capabilities
blocks_current_goal
local_check_id
mapped_global_gate_ids
```

Historical Bundle16R check IDs preserve mappings to existing G0–G10 owners;
they do not create a current capability or a new global gate. Under the current
workflow, unsupported-used numbers,
calculation errors, true double-counting, hidden TODOs and no-advice failures
are `needs_fix`; visible unused unknowns may remain
`accepted_with_todos`; only failures that prevent any honest target output are
`blocked`.

An active run may set `sample_quality_ready=true` only under its current
workflow contract, after all necessary automatic quality conditions pass and the
current final report has a valid `approved` review with matching bytes, plus
all other applicable sample-quality conditions. Those are necessary, not
automatically sufficient, conditions.

## 10. Historical determinism and generated files

The retired evaluator emitted deterministic JSON and Markdown readouts into
run-specific or `bundle16r/generated/` directories. Its publication convention
required an explicit close task to promote a machine-qualified artifact and
excluded ZIP files, caches, backups and local evidence downloads from those
generated-output commits.

Existing tracked artifacts retain their evidence status under
`docs/meta/DOCS_REPORTS_RETENTION_DEPENDENCY_MANIFEST.yaml`. Historical generation
and publication conventions do not authorize regenerating, changing or deleting
those records, and this contract provides no current execution or publication
entry point.
