# R5 Real-Company Golden Regression Contract

## 1. Purpose

Bundle 16R is a retained legacy capability evaluator for four real companies
with materially different economic models. It is not a release gate, is not
part of ordinary T0–T10 routing, and does not replace
`RESEARCH_WORKFLOW.md`. It may be invoked only when the caller explicitly asks
for this four-case regression capability and supplies the required local inputs.
Its active invocation is automated only. Historical per-case human-review,
reviewer-authority and exact-hash records remain read-only compatibility
evidence and do not participate in active routing.

The contract answers one question:

> Can one issuer-neutral research runtime produce decision-useful, traceable and economically grounded research across four different business-model families without promoting sample prose into evidence?

An engineering pass is not a sample-quality pass. P2 is never authorized by
this contract, and a Bundle16R-local result never writes canonical
`workflow_state.status`.

## 2. Golden regression cases

| Case | Primary model family | Required operating bridge |
|---|---|---|
| 301217 铜冠铜箔 | high-end manufacturing / product generation | product generation + processing fee + capacity/utilization + certification → segment revenue and gross profit |
| 600988 赤峰黄金 | cyclical resource mining | commodity price + volume + grade/recovery + unit cost + capex/ramp → mine/product profit and cash flow |
| 603259 药明康德 | backlog and project-funnel services | backlog + project stage + conversion/recognition + capacity/mix → revenue, margin and risk scenarios |
| 600673 东阳光 | multi-business + project + acquisition | quota/price, manufacturing capacity, project acceptance, IDC utilization and deal consolidation → segment model and valuation eligibility |

The four sample reports supplied outside the repository are narrative-density references only. They may be used to define research dimensions, adversarial tests and expected analytical emphasis. They must not be cited as facts, copied into evidence packs or used to seed numeric model inputs.

## 3. Required machine artifacts per case

Each active automated case result must bind the following roles to physical,
repository-relative files and SHA-256 hashes:

1. `workflow_state`
2. `evidence_pack`
3. `operating_driver_pack`
4. `forecast_model`
5. `valuation_pack`
6. `reader_report`
7. `quality_readout`
8. `generation_lock`

A missing file, path escape, duplicate role or hash mismatch is a hard failure
for the explicitly requested Bundle16R capability. It becomes canonical
`blocked` only if an identity/path/parse/source failure prevents any honest
current-goal output; otherwise it limits the affected capability and is routed
through the canonical truth table.

The hashes on all eight roles, including `generation_lock`, are machine
integrity and reproducibility checks. A historical ninth `human_review` role
may be read only by an explicit compatibility reader; it is never required by
an active case, never supplies current reviewer authority and never controls
the canonical automatic outcome or `sample_quality_ready`.

## 4. Case-result manifest

Each `<case_id>.json` in the case-results directory must use:

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

The metrics must be computed by upstream packs or a documented adapter. They must not be manually typed solely to satisfy the gate.

## 5. Operating-model quality floor

A case cannot pass by filling sections with generic prose. The minimum release floor is:

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

A critical question may be explicitly unresolved during research. The
evaluator must preserve it as `unknown` or `method_unavailable` rather than
pass with a generic proxy. If the current case actually uses that missing input,
the affected case result is `needs_fix`; if it remains visible and unused, the
canonical workflow may be `accepted_with_todos`. Severity alone does not decide
either result.

## 6. Peer and valuation behavior

Peer multiples are permitted only when:

- at least three peers pass operating-definition qualification;
- forecast periods are aligned;
- product/service boundaries and accounting definitions are compatible; and
- the report does not rank low-confidence peers.

When these conditions are not met, the case must disable peer-multiple conclusions and use an allowed fallback such as reverse valuation, scenario valuation or an asset-value range. DCF and SOTP remain subject to their own upstream eligibility rules.

## 7. Anti-hardcoding rule

The same runtime must serve all four companies. Issuer names, tickers and case-specific product labels may appear in:

- the Bundle 16R case registry;
- case manifests and generated artifacts;
- benchmark metadata and test fixtures.

They may not appear in the generic runtime implementation under `src/research`, the orchestrator, stock-deep-dive, quality-review or general scripts. The Bundle 16R evaluator scans these paths and fails when registered issuer-specific tokens are found outside explicit allow paths.

## 8. Historical exact-hash review records

Older Bundle16R generations may contain one human-review record per case,
binding Reader report and generation-lock hashes. Those records preserve what
the legacy evaluator required at that historical generation; they are
read-only and must not be copied, refreshed, promoted or used to approve a
current report.

Active V1 has no per-case or generation-lock human approval. It machine-checks
the case artifacts and their hashes, then applies the canonical scoped issue
rules. The only active human boundary is the one final report named in
`final_report_review.report_path`, whose current bytes are bound by
`final_report_review.report_sha256`. That review uses
`final_report_review_status: not_requested|pending|approved|changes_requested`
and the record fields defined by the active workflow-state schema.

Automated jobs must never synthesize reviewer identity, review time,
approval or change requests. A historical Bundle reviewer or accepted decision
cannot satisfy the current final-report review.

## 9. Legacy evaluator semantics

| Local or historical state | Meaning |
|---|---|
| `engineering_pass=false` | one or more physical, truthfulness, model, semantic or hardcoding gates failed |
| `engineering_pass=true` | the explicitly requested automated harness and four cases passed their local machine checks; this does not set canonical status |
| historical `sample_quality_allowed` | read-only compatibility fact about the old four-review policy; ignored by active routing and never imported into `sample_quality_ready` |
| historical `p2_allowed` | read-only compatibility field; a separate canonical decision is always required |

Bundle 16R must not edit canonical state to claim sample-quality or P2 merely
because the evaluator is installed. Each local finding must be converted to an
active issue with:

```text
impact_scope
active_disposition
affected_capabilities
blocks_current_goal
local_check_id
mapped_global_gate_ids
```

Bundle16R checks map only to the existing G0–G10 owners for the capability they
inspect. They do not create a new global gate. Unsupported-used numbers,
calculation errors, true double-counting, hidden TODOs and no-advice failures
are `needs_fix`; visible unused unknowns may remain
`accepted_with_todos`; only failures that prevent any honest target output are
`blocked`.

An active run may set `sample_quality_ready=true` only outside this legacy
evaluator, after all necessary automatic quality conditions pass and the
current final report has a valid `approved` review with matching bytes, plus
all other applicable sample-quality conditions. Those are necessary, not
automatically sufficient, conditions.

## 10. Determinism and generated files

The evaluator emits deterministic JSON and Markdown readouts. Generated
outputs belong under a run-specific or `bundle16r/generated/` directory and
are not committed unless a later close task explicitly promotes a
machine-qualified artifact. ZIP files, caches, backups and local evidence
downloads are excluded from commits.
