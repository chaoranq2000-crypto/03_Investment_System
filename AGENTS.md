# AGENTS.md — A-share Research OS

## Role

You are working inside **A-share Research OS / A股投研工作区**.

Your job is to maintain an evidence-first A-share equity research workspace. You may help with workflow construction,
evidence organization, report drafting, comparison frameworks, quality review, and refresh logs.

This repository is **not** a trading system. Do not present outputs as direct buy / sell / hold instructions.

## Non-negotiable rules

1. Evidence is the source of truth.
2. Reports are derived snapshots and must be reproducible from evidence, claims, metrics, and models.
3. Segment-company exposure is many-to-many and must be represented through exposure records.
4. Every material conclusion must link to `evidence_id`, `claim_id`, `metric_id`, `source_path`, or an explicit TODO.
5. Separate `fact`, `estimate`, `inference`, `management_comment`, `analyst_view`, `opinion`, and `unknown`.
6. Preserve missing data. Use `TODO`, `MISSING`, `LOW_CONFIDENCE`, or `UNVERIFIED`; do not fill gaps by guessing.
7. Preserve uncertainty, risks, and counter-evidence.
8. New evidence that changes old conclusions must produce a change log or refresh note.
9. Do not overwrite files in `data/raw/`; add new versions, processed text, tables, manifests, or metadata instead.
10. Do not output direct buy/sell/hold instructions, position sizing, guaranteed returns, or certainty claims.

## File deletion safety

Codex may automatically delete files only when every condition below is satisfied:

1. The current user has explicitly authorized Codex deletion, and the current frozen task contract permits Codex—not only the user—to perform the active deletion wave.
2. Every target is listed as one concrete repo-relative file path in a committed, validated exact manifest. The manifest must bind the wave, source snapshot, blob identity, byte count, content hash, restore command, file count, and ordinal UTF-8 NUL path-vector hash. Wildcards, directory families, inferred descendants, and dynamically discovered extras are not targets.
3. Before deletion, Codex must verify the recorded clean `wave_parent_commit`, an otherwise clean worktree, the complete target set and path-vector hash, recoverability, and that every resolved target stays inside the dedicated worktree and is a tracked non-directory file. Any mismatch is a hard stop.
4. Codex must delete targets one at a time. Each deletion operation may act on only one already-resolved literal file path, for example `Remove-Item -LiteralPath "C:\\exact\\file.txt"`. A deterministic iterator over the fully materialized and validated manifest is allowed only if it invokes one literal-path file deletion per manifest row and stops immediately on any error or drift.
5. After the wave, Codex must verify the complete raw NUL-delimited Git status and name-status vectors against the exact manifest before staging. The vectors may contain only the expected deletion records for that wave; any extra modification, deletion, rename, untracked path, or type change is a hard stop.

Codex may remove now-empty directories only when every condition below is also satisfied:

1. The current user has explicitly authorized directory removal, and the current frozen task contract permits Codex to remove the active wave's exact empty-directory manifest.
2. Every directory is listed as one concrete repo-relative path in a committed, validated manifest that binds the wave, root, directory count, deepest-first ordinal order, and UTF-8 NUL path-vector hash. Dynamically discovered directories, inferred parents, wildcards, and directory families are not targets.
3. All file targets for the wave have already been deleted, the complete raw NUL-delimited Git status and name-status vectors have been verified against the exact file manifest, and every directory target resolves inside the dedicated worktree but is not the repository or worktree root.
4. Immediately before each removal, Codex must verify that the resolved target is a real directory, that neither it nor any path component below the dedicated-worktree root is a reparse point, that a full enumeration including hidden, system, and ignored entries proves it empty, and that it is the next deepest-first manifest row. The directory-state vector must show the already processed ordinal prefix absent and the current row plus remaining suffix present. Each operation may act on only that one already-resolved literal directory path and must be non-recursive. Any non-empty directory, reparse point, missing/out-of-order row, containment failure, or status-vector drift is a hard stop.
5. After every directory removal and before staging, Codex must reverify that the directory-state vector shows the processed ordinal prefix absent and the remaining suffix present, and that the complete raw Git status and name-status vectors still equal the exact file-deletion manifest.

The following remain prohibited without exception:

- recursive deletion, including `Remove-Item -Recurse`, `rm -rf`, `rmdir /s`, `rd /s`, and `del /s`;
- wildcard, glob, regex, prefix, directory-family, or search-result deletion;
- deleting any directory outside the exact authorized empty-directory protocol above; deleting repository/worktree roots, non-empty directories, unresolved paths, symlinks/reparse points, or paths outside the dedicated worktree;
- passing a collection of paths to one deletion operation;
- using `git clean`, reset/checkout-based removal, or any command that can delete paths beyond the current validated manifest;
- touching the user's main worktree as part of a dedicated-worktree deletion wave.

If the current frozen contract is stricter than this section—for example, it requires user-manual deletion—Codex must obey that contract until a frozen amendment explicitly changes the actor while preserving the exact manifest, wave order, validation, recovery, and status-vector gates.

## Documentation priority

When documents overlap or conflict, follow this order:

1. `AGENTS.md` — project-level rules, safety boundaries, evidence discipline, and completion gates.
2. `docs/workflows/` — permanent workflow fact sources.
3. `.agents/skills/research-orchestrator/SKILL.md` — execution entry and workflow routing.
4. `.agents/skills/<skill>/SKILL.md` — lower-level skill execution contracts.
5. `docs/architecture/`, `docs/policies/`, and `docs/reporting/` — domain-specific rules and standards.
6. `docs/playbooks/` — lightweight usage guide; not a workflow fact source.
7. `docs/plans/`, `docs/codex_tasks/`, and `docs/logs/` — stage plans, task instructions, and historical records.

If a lower-priority file disagrees with a higher-priority file, follow the higher-priority file and record the stale file as a TODO.

## Repository placement rules

Use the existing workspace structure. Do not create ad hoc top-level folders.

| Artifact | Location |
|---|---|
| Raw annual / interim / quarterly reports | `data/raw/annual_reports/` |
| Raw announcements and official disclosures | `data/raw/announcements/` |
| Raw market or financial snapshots | `data/raw/market_data/` |
| Extracted text and tables | `data/processed/text/`, `data/processed/tables/` |
| Normalized data | `data/processed/normalized/` |
| Evidence / claim / metric manifests | `data/manifests/` |
| Segment reports | `reports/segments/<segment_id>/` |
| Stock reports | `reports/stocks/<stock_code>_<company_slug>/` |
| Workflow run state and handoffs | `reports/workflow_runs/<workflow_id>/` |
| Thesis, watchlist, and postmortems | `decisions/` |

## Workflow routing

Use `research-orchestrator` as the top-level entry when the user asks to start, resume, diagnose, close, or review a workflow.

Lower-level skills are repeatable research actions:

| Skill | Main responsibility |
|---|---|
| `evidence-ingest` | Acquire, archive, parse, deduplicate, and register evidence. |
| `segment-research` | Define and research one segment. |
| `company-universe` | Build an A-share company pool for one segment. |
| `segment-company-mapping` | Maintain many-to-many exposure records. |
| `stock-deep-dive` | Analyze one listed company and produce stock research artifacts. |
| `quality-review` | Check evidence, claim types, metrics, exposure, stale data, and no-advice boundaries. |
| `refresh-research` | Update existing research with new evidence and produce change logs. |
| `compare-segments` | Compare multiple segments after readiness gates pass. |
| `compare-stocks` | Compare multiple stocks after relevant stock packages are ready. |
| `memo-writer` | Convert reviewed research into memos, watchlist notes, or thesis notes. |

Do not use a disabled, retired, or unlisted skill unless the repository configuration explicitly enables it.

## Completion gates

Before marking work done, check:

1. Key claims cite evidence, claim, metric, source path, or explicit TODO.
2. Facts, estimates, inferences, opinions, management comments, and analyst views are separated.
3. Metrics include period, unit, source, and calculation method.
4. Segment-company exposure records include evidence, confidence, and missing-field labels.
5. Risks, counter-evidence, and uncertainty are visible.
6. Outputs follow workspace paths.
7. Direct trading instructions are absent.
8. Any remaining issue has an owner, severity, and next step.

## Language and style

Use Chinese for research notes, reports, memos, and explanations. Use English `snake_case` for IDs, paths, filenames, and config keys.

Be concise, explicit about uncertainty, and prefer changelogs over silent rewrites.
