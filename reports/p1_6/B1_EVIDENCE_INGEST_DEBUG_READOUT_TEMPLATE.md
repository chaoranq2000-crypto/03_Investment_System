# B1 Evidence-Ingest Debug Readout

## Metadata

- phase: P1.6 Phase B1
- skill: evidence-ingest
- run_date:
- operator:
- repo_commit:

## Scope

This readout validates the evidence-ingest contract. It does not create research conclusions, scorecards, watchlist decisions or trading advice.

## Contract files checked

| Area | Files | Status | Notes |
|---|---|---|---|
| SKILL | `.agents/skills/evidence-ingest/SKILL.md` |  |  |
| References | `references/*.md` |  |  |
| Scripts | `scripts/*.py` |  |  |
| Assets | `assets/*` |  |  |
| Debug cases | `assets/debug_cases/*` |  |  |

## Debug cases

| Case | Expected | Result | Notes |
|---|---|---|---|
| manual_file_success | manifest PASS |  |  |
| local_dir_duplicate | duplicate hash detected |  |  |
| structured_api_pull_snapshot | metric-only manifest/candidate PASS |  |  |
| d_source_clue_blocked | clue-only PASS |  |  |
| invalid_manifest_failure | validator fails as expected |  |  |

## Validation summary

| Gate | Result | Issues |
|---|---|---|
| Manifest gate |  |  |
| Path gate |  |  |
| Candidate gate |  |  |
| No-advice gate |  |  |

## Issues

| severity | issue | fix | blocking_for_stage |
|---|---|---|---|
|  |  |  |  |

## Decision

- B1 status: `accepted` / `accepted_with_todos` / `needs_fix` / `blocked`
- High severity issue count:
- Medium TODO count:
- Ready for B2: yes/no

## Remaining TODO

- 
