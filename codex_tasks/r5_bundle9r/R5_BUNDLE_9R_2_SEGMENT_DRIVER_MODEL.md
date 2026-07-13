# 9R.2 — Segment driver model

## Goal

Replace hard-coded top-line growth assumptions with a traceable business-driver model.

## Required model views

1. **Issuer-disclosed view**: room cooling, cabinet cooling and other businesses using the company's reporting perimeter.
2. **Analytical view**: an optional liquid-cooling estimate inside the disclosed perimeter, with explicit overlap control, confidence and gap ID.

## Rules

- Do not present liquid cooling as a separately disclosed segment.
- Revenue drivers should prefer project/volume/capacity × unit value; when unavailable, use explicitly reviewed proxy drivers and state the limitation.
- Each segment/year/scenario needs revenue, growth, gross margin, gross profit, supporting IDs, claim type and falsification condition.
- Analytical liquid-cooling revenue cannot be added on top of the issuer-disclosed total without an elimination line.

## Output

`R5_bundle9r_segment_driver_model.yaml`.
