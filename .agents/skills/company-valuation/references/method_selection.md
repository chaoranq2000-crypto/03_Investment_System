# Valuation Method Selection

## 1. Principle

Do not force DCF + relative + SOTP for every company. Choose valuation methods according to business model, disclosure sufficiency and forecast quality.

Unsupported methods should be skipped with explicit reasons.

## 2. Method matrix

| Company type | Primary methods | Conditional methods | Skip / caution |
|---|---|---|---|
| Mature industrial / manufacturing | dynamic PE, EV/EBITDA, peer comparison, scenario valuation | DCF if FCFF assumptions are supportable | Do not overfit terminal value |
| High-growth technology / AI theme | PS, EV/Revenue, dynamic PE if profit visible, scenario sensitivity | SOTP if business lines are disclosed | Avoid peer premium as fact |
| Resource / commodity | mid-cycle PE/EV/EBITDA, NAV/resource EV, price sensitivity | DCF with commodity price scenarios | Current peak-cycle earnings may mislead |
| Multi-segment conglomerate | SOTP, peer segment multiples, consolidated sanity check | DCF at group level | SOTP needs segment disclosure |
| Banks | P/B, ROE/PB, dividend, excess return | DDM | Avoid industrial EV multiples |
| Insurance | P/EV, P/B, ROE, solvency and investment yield context | DDM | Avoid simple PE without embedded value context |
| REIT-like / infrastructure cash flow | DCF / dividend yield / NAV | EV/EBITDA | Check leverage and distribution policy |
| Loss-making early-stage | PS, EV/Revenue, cash runway, scenario milestones | option-style qualitative scenarios | Do not imply precise fair value |
| Cyclical semiconductor / electronics | mid-cycle PE, EV/EBITDA, PS, scenario sensitivity | DCF with normalized margins | TTM PE can be distorted |
| Biotech / CXO / healthcare services | dynamic PE, PEG-like context, order backlog sensitivity | DCF if backlog and margins visible | Regulatory/geopolitical risks must be visible |

## 3. Method readiness gates

### 3.1 Relative valuation

Can be used when:

```text
- market snapshot exists or explicit TODO_MARKET_DATA is visible;
- at least 3 peers have same-period multiples, or low-confidence label is attached;
- peer selection reason is documented.
```

### 3.2 Dynamic valuation

Can be used when:

```text
- forecast_model has 2026E/2027E/2028E profit or EPS assumptions;
- assumptions are labeled estimate / inference / analyst_view;
- period and unit are explicit.
```

### 3.3 SOTP

Can be used when:

```text
- at least 2 business segments have reviewed revenue / profit / asset / KPI disclosure;
- each segment has a method and peer basis;
- unallocated costs, net debt and minority interests are handled or TODO-labeled.
```

If segment revenue or profit is missing, do not fabricate SOTP. Use `TODO_SEGMENT_DISCLOSURE`.

### 3.4 DCF

Can be used when:

```text
- revenue, margin, tax, capex, working capital and discount-rate assumptions are available;
- forecast horizon and terminal assumptions are documented;
- sensitivity table is included;
- WACC > terminal growth is checked.
```

If FCFF inputs are weak, use DCF only as a low-confidence scenario, not as the dominant conclusion.

### 3.5 NAV / resource EV

Use for miners, oil & gas, utilities, real estate-like assets, or asset-heavy companies when:

```text
- reserve / capacity / project asset data exists;
- commodity price or utilization assumptions are explicit;
- discount rate and capex assumptions are documented.
```

## 4. Scenario defaults

Use three scenarios only as research context:

```yaml
bear:
  demand: lower-than-base
  margin: lower-than-base
  multiple: lower-than-peer-or-historical
base:
  demand: current-consensus-or-supported-base
  margin: supported-base
  multiple: peer-or-historical-mid
bull:
  demand: higher-than-base
  margin: higher-than-base
  multiple: upper-but-explained
```

Do not convert scenario output into a trading command.

## 5. Common mistakes

```text
- Using TTM PE at cycle trough/peak without normalizing.
- Using peer average instead of median without explaining outliers.
- Comparing companies with different segment exposure without limitation notes.
- Calling analyst target price a fact.
- Treating market price reaction as proof of intrinsic value.
- Writing “估值底部”“上行空间” as if it were guaranteed.
```
