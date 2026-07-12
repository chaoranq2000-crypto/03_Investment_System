# R5 Bundle 8 Research Depth Execution Plan

- Decision: `bundle8_plan_ready`
- Workflow: `wf_20260703_stock_first_002837_invic`
- Baseline: `6513350ab371cd2e5612fe2fb4a3f4c1f2f5f9d0`
- Entry reader score: `59` / `82`
- Accepted Bundle 8 issues: `4`
- Deferred issues: `8`

## Execution order

### 1. B8-M3-EVIDENCE-COVERAGE

- Owner: `evidence-ingest`
- Stage: `T2_evidence_acquire_parse`
- Dependencies: `none`
- Source issues: `R5Q-B7-44F6297D, R5Q-B7-E54AC257`
- Outputs:
  - `R5_bundle8_evidence_source_catalog.yaml`
  - `evidence_coverage_matrix.yaml`
  - `company_operating_evidence_pack.yaml`
  - `peer_operating_pack.yaml`
- Exit criteria:
  - all blocking coverage rows are covered
  - underlying-source deduplication is applied
  - at least four independent underlying sources are reviewed
  - at least three unique peers have operating evidence
  - issuer-only material does not satisfy independent-industry thresholds

### 2. B8-M3-INDUSTRY-RESEARCH

- Owner: `segment-research`
- Stage: `T5_analysis_pack_build`
- Dependencies: `B8-M3-EVIDENCE-COVERAGE`
- Source issues: `R5Q-B7-8E0E9760`
- Outputs:
  - `industry_evidence_pack.yaml`
  - `competitive_position_matrix.yaml`
- Exit criteria:
  - industry demand has at least two independent underlying sources
  - industry supply/competition has at least two independent underlying sources
  - counterevidence and uncertainty remain visible
  - peer comparability and non-comparability are explicit

### 3. B8-M4-ANALYSIS-ENGINE

- Owner: `stock-deep-dive`
- Stage: `T5_analysis_pack_build`
- Dependencies: `B8-M3-EVIDENCE-COVERAGE, B8-M3-INDUSTRY-RESEARCH`
- Source issues: `R5Q-B7-0BF5FA3E`
- Outputs:
  - `R5_bundle8_analysis_inputs_v2.yaml`
  - `analysis_pack_v2.yaml`
  - `thesis_tree.yaml`
  - `business_driver_tree.yaml`
  - `segment_economics.yaml`
  - `competitive_position_matrix.yaml`
  - `risk_counterevidence_pack.yaml`
- Exit criteria:
  - at least seven complete analysis units pass
  - each required unit contains judgment, trend, mechanism and financial impact
  - each required unit contains counterevidence, falsification and watch metrics
  - all source and metric references resolve to reviewed inputs
  - generic or duplicated template analysis is rejected

### 4. B8-INTEGRATION-GATE

- Owner: `quality-review`
- Stage: `T9_quality_review`
- Dependencies: `B8-M4-ANALYSIS-ENGINE`
- Source issues: `none`
- Outputs:
  - `R5_bundle8_research_depth_gate.yaml`
  - `R5_bundle8_research_depth_gate.md`
- Exit criteria:
  - evidence coverage gate passes
  - analysis pack gate passes
  - workflow state is not mutated by the gate
  - reader report is not regenerated in Bundle 8
  - Bundle 9 handoff is explicit and Bundle 8 is not auto-closed

## Boundary

Planning does not change workflow state, resolve TODOs, regenerate the reader report, or close Bundle 8.

Forecast/valuation are deferred to Bundle 9; technical/sentiment/event, Writer and end-to-end benchmarking are deferred to Bundle 10.
