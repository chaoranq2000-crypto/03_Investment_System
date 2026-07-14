# company-valuation — Bundle 13R deferred valuation rule

Do not execute BF12R-001 while Bundle 12R still returns `needs_backflow`.

After Bundle 12R returns `operating_evidence_ready` on the exact promoted input:

- refresh peer eligibility from official, definition-compatible operating evidence;
- refresh DCF eligibility only with qualified operating coverage, three OCF/capex periods, working-capital bridge, tax, WACC and terminal growth;
- refresh SOTP eligibility only when every material segment has independent exposure, qualified financials and resolved overlap;
- keep ineligible methods closed rather than filling them with proxies;
- preserve `sample_quality_allowed=false` and `p2_allowed=false`.
