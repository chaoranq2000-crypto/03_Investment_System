# Stock Report Quality Gates V2

## 1. Purpose

Upgrade quality-review from debug gate to sample-quality stock report gate.

## 2. Gate summary

```text
SRQ1 Evidence Completeness Check
SRQ2 Claim Locator Check
SRQ3 Metric Normalization Check
SRQ4 Business Breakdown Check
SRQ5 Segment Exposure Check
SRQ6 Forecast Model Check
SRQ7 Valuation Check
SRQ8 Technical / Sentiment / Event Check
SRQ9 Report Expression Check
SRQ10 No Unsupported Advice Check
SRQ11 Backflow & Maintenance Check
```

These are stock-report checklist IDs, not global `gate_id` values. Map them to
the global gates in `docs/workflows/RESEARCH_WORKFLOW.md` when writing issues.

## 3. Severity rules

```yaml
high:
  definition: Blocks R3 report or may cause hallucinated material conclusion.
medium:
  definition: Does not block draft but must be fixed before maintained report.
low:
  definition: Style, completeness or non-critical polish issue.
```

## 4. SRQ1 Evidence Completeness Check

High issue if:

```text
- latest annual report missing or unparsed.
- no evidence_manifest row for key source.
- PDF parse has no page_map.
- report uses a source not in manifest.
```

## 5. SRQ2 Claim Locator Check

High issue if:

```text
- material claim lacks claim_id.
- claim lacks quote_or_excerpt.
- claim lacks page_no_or_section / table_id.
- D-level clue supports material claim.
```

## 6. SRQ3 Metric Normalization Check

High issue if:

```text
- financial metric lacks period / unit / source_evidence_id.
- reported metrics and estimates are mixed.
- Tushare/Baostock metric is used as business exposure fact.
```

## 7. SRQ4 Business Breakdown Check

High issue if:

```text
- business line revenue/gross margin is invented.
- revenue_pct is written as exact without disclosure.
- customer/order/capacity statements lack source.
```

Medium issue if:

```text
- business breakdown is incomplete but gaps are explicit.
```

## 8. SRQ5 Segment Exposure Check

High issue if:

```text
- segment_exposure updates registry without reviewed claims.
- exposure_type=revenue without revenue evidence.
- exposure_score >=4 without claim/metric support.
```

## 9. SRQ6 Forecast Model Check

High issue if:

```text
- forecast has numbers but no assumptions.
- forecast presented as fact.
- no sensitivity or scenario for R3.
```

## 10. SRQ7 Valuation Check

High issue if:

```text
- valuation lacks as_of_date.
- peer table missing for R3.
- target price appears as trading instruction.
```

## 11. SRQ8 Technical / Sentiment / Event Check

High issue if:

```text
- technical section lacks data date.
- sentiment clue written as fact.
- event date lacks source or estimate label.
```

## 12. SRQ9 Report Expression Check

Medium issue if:

```text
- report is only bullet points and lacks narrative.
- major section lacks conclusion sentence.
- evidence gaps are hidden in appendix only.
```

## 13. SRQ10 No Unsupported Advice Check

High issue if:

```text
- report says buy/sell/hold as instruction.
- report gives position sizing or immediate trading action.
- report gives unsupported target price.
```

Allowed:

```text
research_status: high_conviction_watch / watch / neutral_watch / risk_watch
scenario valuation range as model output
```

## 14. SRQ11 Backflow & Maintenance Check

High issue if:

```text
- accepted report does not update report_status.
- reviewed claims/metrics not recorded.
- exposure backflow decision missing.
```

## 15. Acceptance levels

```yaml
blocked:
  high_issues: any issue that invalidates evidence or advice boundary
needs_fix:
  high_issues: >0
accepted_with_todos:
  high_issues: 0
  medium_issues: allowed with explicit TODOs
accepted_sample_quality:
  high_issues: 0
  medium_issues: 0 or non-blocking
  evidence_map: present
  open_questions: present
```
