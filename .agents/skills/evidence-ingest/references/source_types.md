# Source Types and Data Classes

## Three data classes

| Class | Definition | Destination | Material claim rule |
|---|---|---|---|
| `evidence` | Auditable, reviewable and citable source material or archived snapshot. | `evidence_manifest`, processed text/tables, claim candidates. | May support material claims depending on source rank and review status. |
| `metric_snapshot` | Structured market, financial, index, macro or corporate-action snapshot. | raw snapshots, normalized data, metric candidates/draft. | Supports metric facts only; does not prove business exposure. |
| `clue` | News, social media, hotlists, concept labels, rumors or weak signals. | `clue_log`, TODOs, low-confidence candidate list. | Cannot support material claims alone. |

## Initial source_type enum

Use these source types in B1:

```text
official_disclosure
annual_report
announcement
regulator_statistics
policy_document
structured_market_data
structured_financial_data
company_ir_product
third_party_research
news_social_clue
user_uploaded
private_note
unknown_source
```

## Default handling

| source_type | Default class | Default reliability | Typical claim types |
|---|---|---|---|
| `annual_report` | evidence | A | fact, metric_statement, management_comment |
| `announcement` | evidence | A | fact, metric_statement, management_comment |
| `official_disclosure` | evidence | A | fact, metric_statement, management_comment |
| `regulator_statistics` | evidence / metric_snapshot | A/B | fact, metric_statement |
| `policy_document` | evidence | A/B | fact, policy_context |
| `structured_market_data` | metric_snapshot | B | metric_statement, metric_candidate |
| `structured_financial_data` | metric_snapshot | B | metric_statement, metric_candidate |
| `company_ir_product` | evidence | B/C | management_comment, company_claim, clue |
| `third_party_research` | evidence | B/C | analyst_view, estimate, context |
| `news_social_clue` | clue | D | clue only |
| `user_uploaded` | evidence / clue | C/unknown | depends on metadata and review |
| `private_note` | evidence / clue | C/unknown | depends on metadata and review |
| `unknown_source` | clue | unknown | none until classified |

## Hard rules

1. D-level material cannot support material claims.
2. Structured data snapshots can support metrics but cannot replace official annual reports or announcements for business-exposure claims.
3. Management statements must be labeled as `management_comment` or `company_claim`, not verified fact.
4. Third-party estimates must be labeled `estimate=true` or `claim_type=estimate`.
5. User-uploaded/private notes need explicit `license_note` and `review_status`.
