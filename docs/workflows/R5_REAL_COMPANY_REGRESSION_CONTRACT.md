# R5 Real-Company Golden Regression Contract

## 1. Purpose

Bundle 16R introduces the first release gate that is evaluated on four real companies with materially different economic models. It does not add a new global workflow and does not replace `RESEARCH_WORKFLOW.md`. It consumes the existing T0–T10 workflow, Bundle 11R–15R runtime outputs, model packs, Reader artifacts and quality readouts.

The contract answers one question:

> Can one issuer-neutral research runtime produce decision-useful, traceable and economically grounded research across four different business-model families without promoting sample prose into evidence?

An engineering pass is not a sample-quality pass. P2 is never authorized by this contract.

## 2. Golden regression cases

| Case | Primary model family | Required operating bridge |
|---|---|---|
| 301217 铜冠铜箔 | high-end manufacturing / product generation | product generation + processing fee + capacity/utilization + certification → segment revenue and gross profit |
| 600988 赤峰黄金 | cyclical resource mining | commodity price + volume + grade/recovery + unit cost + capex/ramp → mine/product profit and cash flow |
| 603259 药明康德 | backlog and project-funnel services | backlog + project stage + conversion/recognition + capacity/mix → revenue, margin and risk scenarios |
| 600673 东阳光 | multi-business + project + acquisition | quota/price, manufacturing capacity, project acceptance, IDC utilization and deal consolidation → segment model and valuation eligibility |

The four sample reports supplied outside the repository are narrative-density references only. They may be used to define research dimensions, adversarial tests and expected analytical emphasis. They must not be cited as facts, copied into evidence packs or used to seed numeric model inputs.

## 3. Required physical artifacts per case

Each case result must bind the following roles to physical, repository-relative files and SHA-256 hashes:

1. `workflow_state`
2. `evidence_pack`
3. `operating_driver_pack`
4. `forecast_model`
5. `valuation_pack`
6. `reader_report`
7. `quality_readout`
8. `generation_lock`
9. `human_review`

A missing file, path escape, duplicate role or hash mismatch is a hard failure.

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

A critical question may be explicitly unresolved during research, but the case must then remain blocked rather than pass with a generic proxy.

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

## 8. Exact-hash human review

Human review starts as `pending`. An `accepted` review is valid only when it contains:

- the exact physical Reader report SHA-256;
- the exact generation-lock SHA-256;
- a non-empty reviewer identity; and
- a non-empty review timestamp.

Any report rerender or lock change invalidates the previous acceptance. Automated jobs must never synthesize reviewer identity or acceptance.

## 9. Release semantics

| State | Meaning |
|---|---|
| `engineering_pass=false` | one or more physical, truthfulness, model, semantic or hardcoding gates failed |
| `engineering_pass=true`, `sample_quality_allowed=false` | the harness and four cases pass automated gates, but at least one exact-hash human review is pending or rejected |
| `sample_quality_allowed=true` | all four cases pass automated gates and all four exact-hash human reviews are accepted |
| `p2_allowed=false` | always false in Bundle 16R; a separate canonical decision is required |

Bundle 16R must not edit canonical state to claim sample-quality or P2 merely because the evaluator is installed.

## 10. Determinism and generated files

The evaluator emits deterministic JSON and Markdown readouts. Generated outputs belong under a run-specific or `bundle16r/generated/` directory and are not committed unless a later close task explicitly promotes a reviewed artifact. ZIP files, caches, backups and local evidence downloads are excluded from commits.
