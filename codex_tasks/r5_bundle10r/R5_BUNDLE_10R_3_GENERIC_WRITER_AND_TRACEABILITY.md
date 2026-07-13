# 10R.3 — Generic Writer and traceability

## Goal

Render a company-specific report from structured analysis assets without issuer-specific literals in the Writer source.

## Required work

- Consume all analysis-unit fields, not only a one-sentence judgment.
- Render tables from payload data rather than fixed company rows.
- Keep display references in the Reader and internal evidence identifiers in a separate traceability appendix.
- Fail on unresolved, duplicated, or unused material references.
- Keep deterministic ordering and byte-stable output for identical inputs.

## Acceptance

- Generic Writer source contains no ticker, issuer name, product-line name, or fixed report date for the pilot company.
- Cross-company fixture renders without modifying Python.
- Main report has no internal paths, raw evidence IDs, or TODO/readiness tokens.
