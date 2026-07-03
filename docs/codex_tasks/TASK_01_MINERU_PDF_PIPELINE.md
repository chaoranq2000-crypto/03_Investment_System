# TASK 01 — Implement MinerU PDF Pipeline

## Goal

Implement a reusable local PDF parsing runner that calls the user's existing MinerU installation and normalizes outputs into the project evidence contract.

## Files to create or modify

```text
src/ingest/mineru_parse_runner.py
src/ingest/pdf_candidate_extractor.py
src/ingest/table_inventory_builder.py
tests/test_mineru_parse_runner.py
tests/test_pdf_candidate_extractor.py
```

## Required behavior

1. Read `.agents/skills/evidence-ingest/assets/mineru_parse_job_template.yaml` or a job yaml.
2. Validate raw PDF path exists.
3. Call MinerU using local command path from env var `MINERU_BIN` or config.
4. Collect MinerU outputs.
5. Normalize outputs to:

```text
data/processed/text/<evidence_id>.md
data/processed/layout/<evidence_id>_content.json
data/processed/layout/<evidence_id>_middle.json
data/processed/tables/<evidence_id>_tables.json
data/processed/page_maps/<evidence_id>_page_map.yaml
data/processed/logs/<evidence_id>_parse_log.json
```

6. Generate table inventory.
7. Generate draft claim candidates and metric candidates from key annual report sections.
8. Never overwrite raw PDF.
9. If MinerU fails, write parse_log with FAILED and create a high issue.

## Acceptance tests

```text
pytest tests/test_mineru_parse_runner.py
pytest tests/test_pdf_candidate_extractor.py
```

## Manual debug case

Use the existing 002837 annual report evidence in `wf_20260703_stock_first_002837_invic`. The run passes only when page_map, table_map, parse_log and candidates exist.
