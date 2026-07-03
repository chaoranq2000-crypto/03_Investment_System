# Evidence Ingest References

This directory contains stable contracts for the `evidence-ingest` skill.

`SKILL.md` is intentionally short. Detailed rules live here:

| File | Purpose |
|---|---|
| `source_types.md` | Evidence/data/clue classes and source type taxonomy. |
| `source_registry_contract.md` | Required source registry matrix fields and reliability rules. |
| `ingest_modes.md` | Supported ingest modes and input/output expectations. |
| `storage_manifest_contract.md` | Manifest fields, state enums and archive policy. |
| `field_dictionary.md` | Cross-file field definitions. |
| `evidence_id_naming.md` | Stable evidence ID naming rules. |
| `parsing_outputs_contract.md` | Raw-to-processed output rules and file naming. |
| `candidate_generation_contract.md` | Draft claim/metric candidate schema and promotion rules. |
| `ingest_quality_gate.md` | Success/failure definitions and validation gates. |
| `failure_handling.md` | Common failure modes and required handling. |
| `structured_data_sources.md` | Tushare/Baostock positioning and metric snapshot boundary. |
| `source_adapter_matrix.md` | Data-layer source routing matrix and adapter status labels. |
| `structured_data_adapter_contract.md` | Structured API snapshot contract and metric-only boundary. |
| `market_context_snapshot_contract.md` | Valuation, technical, sentiment and peer market snapshot contract. |
| `data_layer_quality_gate.md` | Data-layer quality gates and acceptance states. |
| `adapter_notes/` | Source-specific notes for later adapter implementation. |

No reference file should contain transient run state. Run state belongs in `data/manifests/`, `data/processed/logs/` or reports/readouts.
