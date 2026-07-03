# Data Layer Acceptance Checklist

## 1. Documentation merge

- [ ] `docs/workflows/DATA_LAYER_WORKFLOW.md` added.
- [ ] `ADR_0002_data_layer_as_evidence_ingest_subsystem.md` added.
- [ ] evidence-ingest references include source matrix, structured adapter contract, market context contract, quality gate.
- [ ] `config/data_source_registry_overlay.yaml` reviewed and either merged or kept as overlay.

## 2. Contract consistency

- [ ] `evidence-ingest/SKILL.md` lists the new reference docs.
- [ ] `source_registry.yaml` source groups align with source adapter matrix.
- [ ] `storage_manifest_contract.md` accepts `api_params_hash`, `as_of_date`, `source_group`, `material_claim_allowed=metric_only`.
- [ ] `candidate_generation_contract.md` distinguishes metric candidates, claim candidates, clue log.

## 3. Codex implementation readiness

- [ ] Codex can explain DL0-DL7 stages.
- [ ] Codex can explain why data layer is not a new research skill.
- [ ] Codex can explain Tushare and Baostock metric-only boundary.
- [ ] Codex can explain a-stock-data-inspired source priority without copying code.

## 4. First implementation acceptance

For the first Codex coding pass, require:

- [ ] local fixture mode still passes existing tests.
- [ ] Tushare adapter supports dry-run without token.
- [ ] Baostock adapter supports dry-run fixture even if package unavailable.
- [ ] no API token is written to any output.
- [ ] raw snapshot is immutable.
- [ ] evidence_manifest row created for each snapshot.
- [ ] metric_candidates generated only for numeric fields.
- [ ] source_gap_report generated when required data is missing.

## 5. Stock report readiness

Before using data layer for publishable stock report:

- [ ] `valuation_snapshot.yaml` exists or report marks `TODO_MARKET_DATA`.
- [ ] `technical_snapshot.yaml` exists or report marks `TODO_MARKET_DATA`.
- [ ] `financial_metric_pack.csv` exists or report marks `TODO_STRUCTURED_FINANCIAL_DATA`.
- [ ] `business_segment_metric_pack.csv` exists or business exposure remains `MISSING_DISCLOSURE`.
- [ ] `peer_market_snapshot.csv` exists before peer valuation comparison.
- [ ] data quality gate has no high issues.

## 6. Explicit blockers

Do not accept if:

- [ ] report uses market/context data as company fact.
- [ ] report uses Tushare/Baostock to prove segment revenue exposure.
- [ ] raw files are overwritten.
- [ ] metric candidates lack source evidence linkage.
- [ ] source field mapping is unknown for a promoted metric.
- [ ] report has buy/sell/hold wording from data layer.
