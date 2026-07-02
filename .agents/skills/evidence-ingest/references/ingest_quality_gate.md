# Ingest Quality Gate

## Ingest result enum

```text
SUCCESS
PARTIAL_SUCCESS
SKIPPED_DUPLICATE
FAILED
```

## SUCCESS

All are true:

1. manifest row exists;
2. raw file or archive policy is valid;
3. file/content/API hash is valid;
4. source registry classification is valid;
5. reliability rank is determined;
6. processed output is complete or not required;
7. `parse_status` is `parsed` or `not_required`;
8. manifest validation passes.

## PARTIAL_SUCCESS

Manifest row and raw/snapshot exist, but one or more non-blocking issues remain:

- partial table parse;
- OCR required;
- candidate generation skipped;
- license requires manual review;
- source needs follow-up metadata.

## SKIPPED_DUPLICATE

- Hash already exists.
- No duplicate raw file is written.
- Ingest log records duplicate details.
- Additional URL/retrieval metadata may be appended as notes.

## FAILED

Any critical failure:

- raw source cannot be acquired and metadata is insufficient;
- required fields missing;
- hash failed;
- invalid source registry classification;
- path write failed;
- severe date anomaly;
- source/rank would contaminate material claims.

## Validation gates

### Manifest gate

- required fields are non-empty;
- `evidence_id` unique;
- hash formats valid;
- URL and local paths separated;
- local paths exist when required;
- status enums valid;
- reliability rank compatible with material claim flag;
- D-level sources have `material_claim_allowed=false`;
- no unexplained future ingest/retrieve dates.

### Parse gate

- text is not empty when parse status is `parsed`;
- scanned PDFs marked `ocr_required` or `manual_required`;
- table extraction failures logged;
- CSV/XLSX preserve schema/sheet info;
- API snapshots include parameter hash.

### Candidate gate

- candidate references valid evidence ID;
- candidate has quote/table/page locator when needed;
- metric has period/value/unit or missing reason;
- estimates explicit;
- D-level rows only generate clues;
- C-level rows do not produce verified facts without A/B support.

### No-advice gate

Evidence ingest outputs must not contain buy/sell/hold, target price calls or formal investment recommendations.
