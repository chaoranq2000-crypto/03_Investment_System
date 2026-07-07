# R5 Sentiment Event Pack Contract

## Purpose

`r5_sentiment_event_pack` carries macro, industry, company sentiment and catalyst/event scenario structure for R5. It prevents writer-created news judgments.

## Required sentiment layers

```yaml
macro_sentiment: []
industry_sentiment: []
company_sentiment: []
```

Each sentiment row must carry at least one of `source_id`, `metric_id`, `claim_id`, or `missing_reason`.

## Catalyst event fields

Each catalyst event must contain:

```text
event_date
event_name
impact_path
verification_metric
counterevidence_condition
```

## Event scenario matrix

The matrix must contain `base`, `upside`, and `downside`. `upside` and `downside` may be TODO when source gaps remain.

## Boundaries

- No live news scrape in the validator.
- News and sentiment cannot independently prove financial facts.
- Events do not imply trading actions.
