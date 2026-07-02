# Source Registry Contract

`config/source_registry.yaml` should be treated as a source matrix, not a flat source-type ranking table.

## Required source matrix shape

```yaml
sources:
  <source_name>:
    display_name: <human-readable name>
    source_group: official_disclosure | structured_database | structured_database_fallback | regulator_policy | company_source | third_party_analysis | clue | user_uploaded
    default_reliability_rank: A | B | C | D | unknown
    supported_source_types: []
    allowed_claim_types: []
    material_claim_allowed: true | false | metric_only
    raw_archive_required: true | false
    raw_archive_policy_default: full_file_archived | snapshot_archived | metadata_only | evidence_card_only | not_archived_license
    requires_token: true | false
    rate_limit_policy: <free text or enum>
    fallback_sources: []
    manual_review_required: true | false
    stale_after: <duration or blank>
    license_note_required: true | false
    notes: <free text>
```

## Reliability ranks

| Rank | Meaning | May support | Must not do |
|---|---|---|---|
| A | Official original disclosure, exchange/regulator original material. | Company facts, filing facts, audited/reported financial facts, policy facts. | Still needs page/section/table locator. |
| B | Structured database, official statistics, high-quality industry background. | Metric facts, time series, valuation metrics, market background. | Cannot replace original filings for business exposure. |
| C | Management statements, company website, brokerage/third-party research, interviews. | Management commentary, analyst views, estimates, product clues. | Cannot be written as verified fact unless backed by A/B. |
| D | News, social media, hotlists, concept labels, market narrative. | Clues and TODOs. | Cannot support material claims. |
| unknown | Source not classified. | Nothing until reviewed. | Must not enter registry as material support. |

## Recommended source entries

- `cninfo`: official disclosure source for annual reports, announcements and prospectuses; A rank.
- `sse`, `szse`, `bse`: exchange filings; A rank.
- `tushare`: structured database; B rank; metric-only material support; token/points/frequency controlled.
- `baostock`: structured market-data fallback; B/C rank depending on use; metric-only support.
- `company_website`, `ir_record`, `interactive_qna`: C rank unless backed by official filing.
- `brokerage_report`, `industry_report`: B/C rank; analyst_view/estimate/context only.
- `news`, `social_media`, `market_hotlist`: D rank; clue only.

## Validation expectations

`validate_manifest.py` should check:

1. `source_name` exists in the registry or is explicitly `unknown_source`.
2. `source_type` is allowed for the source.
3. `reliability_rank` does not exceed source default unless manually justified in `notes`.
4. `material_claim_allowed=false` when `reliability_rank=D`.
5. `raw_archive_policy` follows the source default or explains exception.
