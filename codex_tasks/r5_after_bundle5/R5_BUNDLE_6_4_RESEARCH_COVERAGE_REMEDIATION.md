# R5 Bundle 6.4 — Research coverage remediation

## Goal

Fill the material report gaps that can be filled with reviewed, date-controlled inputs. Do not force unsupported sections merely to imitate sample length.

## Required coverage inventory

Create an inventory for each report dimension with:

- current reviewed evidence;
- missing evidence;
- preferred source type;
- date requirement;
- expected output;
- whether the section is mandatory for the reader candidate;
- owner and review status.

## Priority A — required before reader candidate

### Industry structure and competition

Onboard reviewed evidence sufficient to discuss:

- data-center thermal-management demand drivers;
- liquid-cooling adoption drivers and constraints;
- cooling value-chain positioning;
- relevant competitor business mixes;
- company advantages and disadvantages supported by evidence.

Prefer official disclosures, standards, regulator/industry-association data and clearly dated authoritative research. Market-size estimates must preserve source/date/definition and must not be blended across incompatible definitions.

### Peer comparability

Expand the peer set only with exposure-grounded rationale. For each peer record:

- why included;
- why not fully comparable;
- primary business mix;
- valuation date;
- denominator period;
- source;
- confidence.

A larger but incoherent peer set is worse than a small transparent one.

### Dated company events

Onboard material official company announcements and scheduled verification points. Separate:

- completed facts;
- scheduled events;
- management plans;
- market expectations.

## Priority B — required when method is activated

### Historical market series

Onboard a reviewed historical OHLCV series sufficient for objective trend statistics. Do not generate chart-pattern narratives from a single snapshot.

Minimum requirements:

- date range and adjustment method;
- missing-date handling;
- price source;
- 60/120/250-day return or equivalent objective statistics;
- volatility and drawdown metrics where useful.

### Sentiment

Sentiment remains optional. Do not scrape low-quality social data merely to fill a section. A dated fund-flow, ownership or analyst-consensus input may be used only when reviewed and definitionally clear.

## Liquid-cooling disclosure boundary

Do not make publication of a liquid-cooling-specific segment split a prerequisite because the issuer may not disclose it. The report should instead distinguish:

1. confirmed product exposure;
2. broad reported product-line economics;
3. unverified liquid-cooling-specific economics;
4. measurable future disclosures that would narrow the gap.

## Expected artifacts

- `R5_bundle6_coverage_inventory.yaml`
- `R5_bundle6_industry_event_market_input_plan.yaml`
- accepted reviewed-input records and registry changes only after normal validation/promotion controls
- coverage readout

## Acceptance gate

- industry section has reviewed, dated evidence;
- peer inclusion/exclusion rationale is explicit;
- material company events are date-controlled;
- no sample evidence is used;
- unresolved liquid-cooling economics remain a natural-language boundary;
- no method is activated without its required inputs.
