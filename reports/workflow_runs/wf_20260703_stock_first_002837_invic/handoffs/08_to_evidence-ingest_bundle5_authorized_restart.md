# Handoff: T1 Company Evidence -> evidence-ingest

## Workflow

| field | value |
|---|---|
| workflow_id | `wf_20260703_stock_first_002837_invic` |
| workflow_type | `stock_first_closed_loop` |
| run_mode | `normal` |
| current_stage | `R5 Bundle 5 authorized real-input onboarding` |
| target_skill | `evidence-ingest` |

## Authorization Boundary

| field | value |
|---|---|
| authorized_by | `workspace_user` |
| authorization_text | `授权` |
| authorization_date | `2026-07-12` |
| reviewer_identity | `codex` |
| reviewer_role | `user-authorized evidence and reviewed-input reviewer for this run` |

The authorization permits Codex to acquire project-approved official disclosures and structured data, review them against repository contracts, and record genuine reviewer metadata. It does not permit fabrication, registry promotion before the relevant gate, sample-quality publication, P2 work, or trading advice.

## Objective

Restart Bundle 5.1 from the prior `blocked_source_gapped` state by archiving immutable official evidence, refreshing the real-input inventory and provenance matrix, and deciding whether Card 5.2 is now authorized. This handoff does not itself accept a reviewed input or promote a registry.

## Approved Sources

| source | class | intended use |
|---|---|---|
| CNINFO / SZSE official disclosure PDFs | source rank A | financial history and broad business breakdown |
| project-configured Tushare endpoint | structured source | later Card 5.3 market and peer snapshots after offline review |

## Guardrails

- Preserve raw evidence immutably; never overwrite an existing raw file.
- Treat the existing 7-page PDF as the annual-report summary, not the full report.
- Do not infer liquid-cooling revenue share, margin, or profit contribution from broader product categories.
- Do not treat download or parse success as review acceptance.
- Keep `promotion_allowed`, `sample_quality_report_allowed`, and `p2_allowed` false.
- Keep unresolved fields explicit as `MISSING`, `UNKNOWN`, or a scoped TODO.

## Next Gate

Card 5.2 is allowed only if the refreshed inventory resolves a real official-disclosure evidence chain to a physical immutable source.
