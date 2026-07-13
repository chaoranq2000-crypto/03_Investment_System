# `a-stock-data` Method Adoption Note

## Reference

Method reference: `https://github.com/simonlin1212/a-stock-data`.

The referenced project is published under Apache-2.0. This patch does **not** copy its endpoint
implementation. It adopts high-level operating methods and records the reference for transparency.
Any future direct code reuse must retain the required copyright, license and NOTICE information.

## Methods adopted

1. **Capability-first routing** — start from the required data category, then select a source and an
   endpoint, instead of letting downstream report code call arbitrary URLs.
2. **Independent fallback domains** — pair sources with different operational risks rather than
   duplicating a single vendor's endpoints.
3. **Public-endpoint hygiene** — serial requests, session/opener reuse, spacing, jitter, bounded retry,
   `Retry-After`, and no immediate retry for permission denials.
4. **Field-drift awareness** — treat undocumented field changes as a first-class failure and validate
   expected schemas with fixtures.
5. **Endpoint health ledger** — record success, transient failure, permission denial, schema drift and
   quarantine state so broken endpoints do not repeatedly poison research runs.
6. **Dead-endpoint quarantine** — disable or quarantine known-broken endpoints without deleting the
   historical route record.
7. **Official-source fallback for material events** — exchange and issuer disclosures outrank market
   aggregators for announcements, event dates and company facts.

## Methods deliberately not adopted

- No monolithic 100k-line skill copied into this repository.
- No endpoint output may bypass the evidence manifest and candidate review process.
- No news, hotlist, fund-flow or concept label may become a material company fact.
- No static anti-blocking threshold is treated as universally safe.
- No full valuation or trading conclusion is generated inside the data-acquisition layer.
- No undocumented endpoint is enabled in live mode before offline fixtures and field-map tests pass.

## Integration boundary

```text
external acquisition method
→ local route catalog
→ source-specific adapter
→ raw snapshot/archive
→ manifest and candidates
→ review/promotion
→ analysis pack
```

The expected improvement is broader and fresher coverage with fewer silent endpoint failures. It does
not replace issuer disclosures, research judgment, bottom-up forecasting or valuation reasoning.
