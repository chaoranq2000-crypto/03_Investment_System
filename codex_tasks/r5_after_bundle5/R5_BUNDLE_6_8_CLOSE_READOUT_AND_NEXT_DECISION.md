# R5 Bundle 6.8 — Close readout and next decision

## Goal

Close Bundle 6 truthfully and decide whether the report is ready for human acceptance, not whether the system may self-promote.

## Required close checks

1. Re-run all owner-card focused tests.
2. Re-run truthfulness gates.
3. Re-run the reader-quality gate.
4. Re-render the report twice and compare hashes.
5. Validate the traceability appendix and all display references.
6. Run full repository tests.
7. Run `git diff --check`.
8. Confirm the human-review form remains pending.
9. Confirm sample-quality and P2 remain false.

## Allowed close states

### Successful implementation

```text
R5_002837_READER_FACING_REPORT_V2_CANDIDATE_READY
```

This means the candidate passed automated gates and is ready for a human quality decision.

### Honest partial close

```text
R5_002837_READER_FACING_REPORT_V2_REMEDIATION_INCOMPLETE
```

Use this when critical data, analytical or presentation blockers remain.

### Blocked

```text
R5_002837_READER_FACING_REPORT_V2_BLOCKED
```

Use this when truthfulness, traceability or arithmetic fails.

## Prohibited close claims

Do not claim:

- sample-quality achieved;
- user acceptance;
- human review completed;
- P2 readiness;
- report suitable for direct investment action.

## Next-decision rule

Only an explicit human acceptance of the rendered report hash may authorize a later, narrowly scoped promotion task. Any accepted report must be rechecked if its content hash changes.

## Required output

- `reports/p1_6/R5_BUNDLE_6_READER_REPORT_QUALITY_REMEDIATION_CLOSE_READOUT.md`
- updated canonical index only if repository policy requires it
- artifact inventory with hashes
- known limitations
- recommended next patch
