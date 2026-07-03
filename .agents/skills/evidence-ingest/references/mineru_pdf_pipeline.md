# MinerU PDF Pipeline Contract

## 1. Goal

Use locally deployed MinerU to transform official PDF disclosures into auditable processed text, tables, page maps, parse logs, claim candidates and metric candidates.

This reference is execution guidance for `evidence-ingest`. It is not a standalone research skill.

## 2. Inputs

```yaml
parse_job:
  job_id:
  evidence_id:
  stock_code:
  company_id:
  source_type: annual_report | interim_report | quarterly_report | announcement | exchange_inquiry_reply | industry_report
  raw_pdf_path:
  output_root:
  mineru_profile: default | table_strict | scanned_pdf | fast
  parse_quality_target: standard | strict
  force_reparse: false
```

## 3. Expected output paths

```text
data/processed/text/<evidence_id>.md
data/processed/layout/<evidence_id>_content.json
data/processed/layout/<evidence_id>_middle.json
data/processed/tables/<evidence_id>_tables.json
data/processed/page_maps/<evidence_id>_page_map.yaml
data/processed/logs/<evidence_id>_parse_log.json
data/processed/candidates/claim_candidates_<evidence_id>.csv
data/processed/candidates/metric_candidates_<evidence_id>.csv
```

If MinerU produces different filenames on the local machine, `src/ingest/mineru_parse_runner.py` should normalize them into the above contract.

## 4. Page map contract

```yaml
evidence_id:
raw_pdf_path:
processed_text_path:
parse_engine: MinerU
parse_engine_version:
pages:
  - page_no:
    section_title:
    markdown_start_line:
    markdown_end_line:
    table_ids: []
    image_ids: []
    quality_flags:
      - table_detected
      - ocr_used
      - low_confidence
```

## 5. Table map contract

```yaml
table_id:
evidence_id:
page_no:
section_title:
table_title:
raw_table_format: html | markdown | json | csv
normalized_table_path:
columns:
rows_count:
contains_financial_metric: true | false
contains_business_breakdown: true | false
quality_flags: []
```

## 6. Parse log contract

```json
{
  "job_id": "",
  "evidence_id": "",
  "status": "SUCCESS | PARTIAL_SUCCESS | FAILED",
  "mineru_version": "",
  "started_at": "",
  "finished_at": "",
  "raw_pdf_sha256": "",
  "outputs": [],
  "page_count": 0,
  "tables_detected": 0,
  "ocr_pages": [],
  "low_confidence_pages": [],
  "blocking_issues": [],
  "next_todos": []
}
```

## 7. Claim candidate extraction zones

Prioritize sections containing these keywords:

```text
主营业务
经营情况讨论与分析
分行业
分产品
分地区
收入构成
毛利率
产销量
产能
在建工程
募投项目
研发项目
前五名客户
前五名供应商
重大合同
订单
风险因素
管理层讨论
```

## 8. Claim candidate schema

```csv
claim_candidate_id,
evidence_id,
source_type,
entity_type,
entity_id,
stock_code,
claim_text,
claim_type,
quote_or_excerpt,
page_no_or_section,
table_id,
confidence,
review_status,
notes
```

## 9. Metric candidate schema

```csv
metric_candidate_id,
source_evidence_id,
entity_type,
entity_id,
stock_code,
metric_name,
metric_category,
period,
period_type,
value,
unit,
currency,
original_value_text,
original_unit_text,
table_id,
page_no_or_section,
calculation_method,
is_estimate,
is_reported,
confidence,
review_status,
notes
```

## 10. Quality flags

```yaml
quality_flags:
  - missing_page_map
  - missing_table_map
  - no_business_breakdown_table_found
  - no_customer_supplier_section_found
  - no_segment_related_keyword_found
  - table_parse_low_confidence
  - scanned_pdf_ocr_used
  - needs_manual_review
```

## 11. Failure handling

| Situation | Required action |
|---|---|
| MinerU fails completely | Register parse failure in parse_log, keep raw evidence, create high issue |
| Text ok but table missing | Mark PARTIAL_SUCCESS, create evidence_gap_request for table extraction |
| Table extracted but columns unclear | Keep raw table, mark low confidence, require manual review |
| No segment keywords found | Do not infer exposure; create TODO |
| Page map missing | Do not promote claims |

## 12. Codex implementation task

Codex should implement `src/ingest/mineru_parse_runner.py` and tests. This document defines the contract; do not implement inside SKILL.md.
