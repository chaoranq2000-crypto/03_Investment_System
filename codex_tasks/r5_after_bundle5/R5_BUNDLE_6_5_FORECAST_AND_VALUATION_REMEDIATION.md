# R5 Bundle 6.5 — Forecast and valuation remediation

## Goal

Replace mechanical output presentation with an explicit, reconcilable research model and decision-useful valuation context.

## Forecast requirements

### Historical-to-forecast bridge

Build a bridge from 2025A and the latest quarter to 2026E-2028E covering:

- revenue by disclosed broad product line where available;
- revenue growth assumptions;
- gross-margin assumptions;
- selling/admin/R&D/finance expense assumptions where available;
- tax and minority-interest treatment;
- diluted share count;
- net-profit and EPS reconciliation.

Do not create a separate liquid-cooling revenue line unless reviewed disclosure supports it.

### Scenario design

At minimum provide:

- base case;
- downside or bear case;
- upside or bull case;
- a sensitivity table for the two most important variables.

Scenarios must differ through explicit drivers, not arbitrary EPS percentages.

### Latest-quarter treatment

Explain how the unusually weak 2026Q1 profit and cash flow are handled. Acceptable choices include:

- provisional normalization supported by reviewed one-off evidence;
- seasonal treatment supported by historical quarterly data;
- conservative carry-forward;
- wider scenario bands when the driver is unknown.

The model must not silently annualize or dismiss the quarter.

## Valuation requirements

### Method selection

Assess method eligibility before output:

- forward PE only when earnings scenario is sufficiently meaningful;
- EV/Sales or PS when profit is unstable, with explicit limitations;
- DCF only after FCFF inputs are reviewed and reconciled;
- SOTP only when segment economics are sufficiently separated.

### Peer context

Use a transparent peer matrix with:

- business exposure;
- revenue/profit mix;
- growth and margin profile;
- valuation date and period;
- inclusion reason;
- comparability limitation.

### Market-implied expectations

Explain what the current price and multiples require in terms of future revenue growth, margin recovery or earnings expansion. This section should focus on expectations and risk, not a trading instruction.

### Output boundary

No target price, rating, position size or timing instruction. Scenario valuation ranges may be shown as research context only when denominators and methods are explicit.

## Required artifacts

- `R5_bundle6_forecast_bridge.yaml`
- `R5_bundle6_valuation_reasoning_pack.yaml`
- forecast/valuation validation results
- reconciliation tests

## Acceptance gate

- all forecast rows reconcile;
- every scenario has explicit drivers;
- latest-quarter treatment is visible;
- peer matrix has grounded inclusion logic;
- valuation date and denominators are consistent;
- inactive methods do not emit fake values;
- no direct advice language is produced.
