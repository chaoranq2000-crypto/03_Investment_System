# research-orchestrator — Bundle 13R dependency routing

The Bundle 12R backflow YAML lists RP6, T1 and T2 actions, but execution must follow dependency order rather than file order:

1. `BF12R-002` → `evidence-ingest` / T1;
2. `BF12R-003` → `stock-deep-dive` / T2;
3. re-run `RP-12R-OE` with the promoted input;
4. only after `operating_evidence_ready`, open `BF12R-001` → `company-valuation` / RP6.

Exit handling:

- `blocked_invalid_reviewed_backfill`: route to evidence review fixes;
- `backflow_execution_in_progress`: route to the first unresolved T1/T2 item;
- `ready_for_bundle12r_rerun`: run Bundle 12R, do not start valuation;
- `operating_evidence_requalified`: valuation eligibility refresh may begin.

Never copy Bundle 11R human acceptance to Bundle 13R, and never open sample quality or P2.
