# R5 reader-quality gate contract

The gate validates the visible report and its traceability appendix as a pair. Candidate readiness requires a score of at least 82/100, zero critical blockers, truthfulness checks passing, and human review still pending.

Critical blockers include unsupported material facts, unresolved or duplicate citations, internal IDs/paths or raw gap tokens in the main body, repeated machine sections, over-precise currency dumps, unreconciled forecasts, valuation without date/denominator control, direct investment instructions, sample evidence, and fabricated human-review acceptance.

The scored dimensions are evidence integrity (20), coverage completeness (15), analytical synthesis (20), forecast and valuation (15), narrative/readability (15), presentation hygiene (10), and risks/watch conditions (5). A score never overrides a blocker.

The gate output must list the report and appendix hashes, each dimension score, blocker evidence, unresolved citations, required-section coverage, fixed flags, and its deterministic decision. It must fail closed if either input is absent or malformed.

Human review is a later external gate. This automated gate may only produce `candidate_ready_for_human_review`; it may not claim final publication quality, sample quality, P2 readiness, or an investment recommendation.
