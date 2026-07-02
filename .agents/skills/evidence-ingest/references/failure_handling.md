# Failure Handling

| Failure type | Handling | Result |
|---|---|---|
| Duplicate hash | Skip raw copy; record `duplicate_of` in log. | `SKIPPED_DUPLICATE` |
| Missing local path | Do not create active row unless archive policy explains it. | `FAILED` or `PARTIAL_SUCCESS` |
| URL download failure | Retry/fallback; if unavailable, metadata/evidence-card only. | `PARTIAL_SUCCESS` or `FAILED` |
| PDF text empty | Mark `ocr_required` or `manual_required`. | `PARTIAL_SUCCESS` |
| Table parse failure | Keep text output; log table parse partial. | `PARTIAL_SUCCESS` |
| Unknown source registry | Mark `unknown_source` and block material use. | `FAILED` or `blocked` |
| Future date anomaly | Block unless explained in notes. | `FAILED` |
| License unclear | Require manual review and block material claim use. | `PARTIAL_SUCCESS` |
| D-level material claim | Convert to clue/TODO or block candidate. | `FAILED` for candidate validation |
| API rate limit | Retry/backoff and log. | `PARTIAL_SUCCESS` or `FAILED` |

## Issue schema

Use this schema for `ingest_issues.csv` or script output:

```csv
issue_id,run_id,evidence_id,severity,status,issue_type,object_type,object_id,file_path,field_name,issue,fix,owner,blocking_for_stage,created_at,closed_at,notes
```

Severity:

```text
critical  blocks write or contaminates evidence base
high      blocks registry promotion or material claim usage
medium    acceptable with TODO
low       cleanup only
```
