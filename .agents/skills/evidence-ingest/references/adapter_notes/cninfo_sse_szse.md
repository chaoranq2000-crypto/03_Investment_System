# CNINFO / SSE / SZSE / BSE Adapter Notes

Official disclosure sources are preferred for A-level company facts, annual/interim/quarterly reports, announcements, prospectuses and exchange inquiries.

## B1 handling

B1 does not need a complete crawler. It must define official-disclosure ingestion expectations and validate files once acquired.

## Required metadata

- `source_name`: `cninfo`, `sse`, `szse`, `bse`, `company_filing`
- `source_type`: `annual_report`, `announcement`, `official_disclosure` or `regulator_statistics`
- `stock_code` / company identity when applicable
- `title`
- `publisher`
- `publish_date`
- `source_url`
- `raw_file_path`
- `page_count` if PDF
- `reliability_rank=A`

## Output boundary

Official filings may generate fact and metric candidates, but still require page/section/table locators and review before registry promotion.

## Fallback rule

If third-party summaries exist, use them only as clues or search aids when original filing is unavailable. Prefer official PDF/source whenever possible.
