# P1.6 Phase B1 Only — Codex Execution Plan

## Operating boundary

Only execute P1.6 Phase B1: `evidence-ingest` post-patch verification, repair, and debug readout.

Do not start B2 or any later workflow. Do not modify `segment-research`, `company-universe`, `segment-company-mapping`, `stock-deep-dive`, `quality-review`, `memo-writer`, or `refresh-research` except for reading their files to ensure B1 does not break existing repo tests.

Do not create new segment reports, stock reports, comparison reports, scorecards, watchlist decisions, thesis memos, P2 readiness reports, or trading language.

## Why this replaces the previous patch plan

The previous patch prompt `codex_prompts/P1_6_DETAILED_PLAN_FOR_CODEX.md` is over-scoped. It includes Phase A, B2-B8, segment-led debug, stock-led debug, interlock debug, and P2 readiness. That is not the current task.

For now, use this file as the only Codex plan.

## Current B1 goal

Turn `.agents/skills/evidence-ingest/` into a verified, repo-compatible, executable contract.

B1 is accepted only when:

1. the patch files are present and aligned with the existing repo structure;
2. the B1 scripts run successfully in the actual repo, not just in the patch fixture;
3. the existing repo tests still pass;
4. B1 debug cases pass;
5. `config/source_registry.yaml` is reconciled with the B1 source registry contract without blindly overwriting existing config;
6. B1 produces a filled debug readout;
7. all B1 outputs remain evidence-layer artifacts only.

## Files to keep

Keep and validate these files from the patch:

```text
.agents/skills/evidence-ingest/SKILL.md
.agents/skills/evidence-ingest/references/**
.agents/skills/evidence-ingest/scripts/**
.agents/skills/evidence-ingest/assets/**
tests/test_phase_b1_evidence_ingest_contract.py
reports/p1_6/B1_EVIDENCE_INGEST_DEBUG_READOUT_TEMPLATE.md
config/source_registry.b1_patch.example.yaml
```

`config/source_registry.b1_patch.example.yaml` is an example and migration guide. Do not replace `config/source_registry.yaml` with it automatically.

## Files not to use for the current task

Do not use these files as the active plan:

```text
codex_prompts/P1_6_DETAILED_PLAN_FOR_CODEX.md
P1_6_WORKFLOW_BUILDOUT_PLAN.md, if copied into the repo as an active Codex task
```

They are broader P1.6 planning references. They discuss B2-B8 and later debug phases, so they should be archived or treated as future notes.

Do not commit patch-transport files if they were accidentally copied into the repo root:

```text
README_PATCH.md
apply_phase_b1_patch.py
phase_b1_patch.zip
phase_b1_patch/
repo_overlay/
```

They are delivery artifacts, not repo runtime artifacts.

## Step 0 — Create a clean working branch

```bash
git status --short
git checkout -b p1-6-b1-evidence-ingest-verify
```

If a branch already exists, stay on it and make sure unrelated changes are not mixed into the B1 commit.

## Step 1 — Check accidental over-copy

Run:

```bash
git status --short
find . -maxdepth 3 -type f \
  \( -name 'README_PATCH.md' -o -name 'apply_phase_b1_patch.py' -o -name 'phase_b1_patch.zip' \)
find . -maxdepth 3 -type d \
  \( -name 'phase_b1_patch' -o -name 'repo_overlay' -o -name 'codex_prompts' \)
```

Expected:

- no patch transport files in the repo root;
- no `repo_overlay/` directory inside the repo;
- no active `codex_prompts/P1_6_DETAILED_PLAN_FOR_CODEX.md` used for this task.

If found, remove them from the working tree unless they are intentionally stored under a docs/archive path.

## Step 2 — Verify B1 file presence

Run:

```bash
python - <<'PY'
from pathlib import Path
required = [
    '.agents/skills/evidence-ingest/SKILL.md',
    '.agents/skills/evidence-ingest/references/source_types.md',
    '.agents/skills/evidence-ingest/references/source_registry_contract.md',
    '.agents/skills/evidence-ingest/references/ingest_modes.md',
    '.agents/skills/evidence-ingest/references/storage_manifest_contract.md',
    '.agents/skills/evidence-ingest/references/parsing_outputs_contract.md',
    '.agents/skills/evidence-ingest/references/candidate_generation_contract.md',
    '.agents/skills/evidence-ingest/references/ingest_quality_gate.md',
    '.agents/skills/evidence-ingest/references/failure_handling.md',
    '.agents/skills/evidence-ingest/references/field_dictionary.md',
    '.agents/skills/evidence-ingest/references/evidence_id_naming.md',
    '.agents/skills/evidence-ingest/references/structured_data_sources.md',
    '.agents/skills/evidence-ingest/references/adapter_notes/cninfo_sse_szse.md',
    '.agents/skills/evidence-ingest/references/adapter_notes/tushare.md',
    '.agents/skills/evidence-ingest/references/adapter_notes/baostock.md',
    '.agents/skills/evidence-ingest/scripts/compute_hash.py',
    '.agents/skills/evidence-ingest/scripts/validate_manifest.py',
    '.agents/skills/evidence-ingest/scripts/check_paths.py',
    '.agents/skills/evidence-ingest/scripts/validate_candidates.py',
    '.agents/skills/evidence-ingest/scripts/write_ingest_log.py',
    '.agents/skills/evidence-ingest/scripts/run_debug_cases.py',
    '.agents/skills/evidence-ingest/assets/evidence_manifest.example.csv',
    '.agents/skills/evidence-ingest/assets/claim_candidates.example.csv',
    '.agents/skills/evidence-ingest/assets/metric_candidates.example.csv',
    '.agents/skills/evidence-ingest/assets/clue_log.example.csv',
    '.agents/skills/evidence-ingest/assets/ingest_log.example.json',
    '.agents/skills/evidence-ingest/assets/evidence_card_template.md',
    '.agents/skills/evidence-ingest/assets/parse_log_template.json',
    'tests/test_phase_b1_evidence_ingest_contract.py',
    'reports/p1_6/B1_EVIDENCE_INGEST_DEBUG_READOUT_TEMPLATE.md',
    'config/source_registry.b1_patch.example.yaml',
]
missing = [p for p in required if not Path(p).exists()]
if missing:
    print('MISSING:')
    for p in missing:
        print(' -', p)
    raise SystemExit(1)
print('B1_FILE_PRESENCE=PASS')
PY
```

If files are missing, restore only from the patch overlay. Do not copy broad plan files.

## Step 3 — Run the B1 debug runner

Run:

```bash
python .agents/skills/evidence-ingest/scripts/compute_hash.py \
  .agents/skills/evidence-ingest/assets/debug_cases/manual_file_success/input/sample_policy.md

python .agents/skills/evidence-ingest/scripts/run_debug_cases.py --repo .
```

Expected:

```text
B1_DEBUG_READOUT=PASS
```

If it fails, fix only B1 files:

```text
.agents/skills/evidence-ingest/SKILL.md
.agents/skills/evidence-ingest/references/**
.agents/skills/evidence-ingest/scripts/**
.agents/skills/evidence-ingest/assets/**
tests/test_phase_b1_evidence_ingest_contract.py, only if the test is incompatible with the intended contract
```

Do not fix failures by weakening guardrails around D-level sources, candidate draft status, path validation, date validation, or no-advice boundaries.

## Step 4 — Run B1 pytest

Run:

```bash
pytest -q tests/test_phase_b1_evidence_ingest_contract.py
```

Expected: all tests pass.

If the repo has a broader test suite, then run:

```bash
pytest -q
```

If broader tests fail for unrelated existing reasons, document them in the readout. Do not expand the B1 task into unrelated repairs unless the failure is caused by the B1 patch.

## Step 5 — Reconcile `source_registry.yaml`

Compare:

```text
config/source_registry.yaml
config/source_registry.b1_patch.example.yaml
.agents/skills/evidence-ingest/references/source_registry_contract.md
```

Do not blindly overwrite the existing registry. Merge only the structural rules needed for B1:

```text
source_group
supported_source_types
default_reliability_rank
allowed_claim_types
material_claim_allowed
raw_archive_required
raw_archive_policy_default
requires_token
rate_limit_policy
fallback_sources
manual_review_required
stale_after
license_note_required
notes
```

Minimum required source entries for B1:

```text
cninfo
sse
szse
tushare
baostock
brokerage_report
news
```

B1 source rules:

- official disclosure sources may support material claims when archived and locatable;
- Tushare is structured metric snapshot source only;
- Baostock is structured market-data fallback only;
- brokerage reports are analyst/estimate/context sources, not official facts;
- news/social/hotlist sources are clue-only and cannot support material claims.

After merging, rerun the B1 debug runner and pytest.

## Step 6 — Check manifest compatibility with the existing repo

Inspect existing files:

```bash
ls -lah data/manifests || true
python - <<'PY'
from pathlib import Path
for p in ['data/manifests/evidence_manifest.csv', 'data/manifests/claims_draft.csv', 'data/manifests/metrics_draft.csv', 'data/manifests/clue_log.csv']:
    path = Path(p)
    if path.exists():
        print('\n---', p, '---')
        print(path.read_text(encoding='utf-8').splitlines()[0][:500])
PY
```

Then validate if a manifest exists:

```bash
python .agents/skills/evidence-ingest/scripts/validate_manifest.py \
  --repo . \
  --manifest data/manifests/evidence_manifest.csv
```

Possible outcomes:

- PASS: record in the readout.
- FAIL due to old schema mismatch: do not rewrite the whole manifest immediately. Create a TODO in the readout: `manifest_schema_migration_needed`.
- FAIL due to invalid path/date/D-source misuse introduced by B1: fix B1.

B1 should not perform a risky bulk migration of existing evidence unless separately approved.

## Step 7 — Validate candidate examples and existing drafts

Run against examples:

```bash
python .agents/skills/evidence-ingest/scripts/validate_candidates.py \
  --repo . \
  --claims .agents/skills/evidence-ingest/assets/claim_candidates.example.csv \
  --metrics .agents/skills/evidence-ingest/assets/metric_candidates.example.csv \
  --manifest .agents/skills/evidence-ingest/assets/evidence_manifest.example.csv
```

If existing draft files exist, run cautiously:

```bash
python .agents/skills/evidence-ingest/scripts/validate_candidates.py \
  --repo . \
  --claims data/manifests/claims_draft.csv \
  --metrics data/manifests/metrics_draft.csv \
  --manifest data/manifests/evidence_manifest.csv
```

If this fails because older draft files do not match the new B1 schema, document as a B1 follow-up migration TODO. Do not silently promote draft rows into registry.

## Step 8 — Fill the B1 debug readout

Create:

```text
reports/p1_6/B1_EVIDENCE_INGEST_DEBUG_READOUT.md
```

Use the template as the base.

Required contents:

```text
run_date
repo_commit
commands_run
B1 file presence status
run_debug_cases result
pytest result
source_registry reconciliation status
existing manifest validation status
candidate validation status
issues table
B1 decision
remaining TODOs
```

Valid B1 decisions:

```text
accepted
accepted_with_todos
needs_fix
blocked
```

Decision rule:

- `accepted`: B1 debug runner and B1 pytest pass; no high/critical issue; existing repo compatibility checked.
- `accepted_with_todos`: debug runner and B1 pytest pass; only medium/low migration TODOs remain.
- `needs_fix`: debug runner or B1 pytest fails but issue is local to B1.
- `blocked`: failures indicate B1 contract cannot be safely applied without broader repo decisions.

## Step 9 — Commit only B1-relevant changes

Review:

```bash
git status --short
git diff --stat
git diff -- .agents/skills/evidence-ingest config tests reports/p1_6
```

Commit only B1 files and readout. Do not commit generated debug outputs under `data/raw/` or `data/processed/` unless they are intentionally part of a small fixture and clearly belong under `.agents/skills/evidence-ingest/assets/`.

Suggested commit message:

```text
p1.6 b1: verify evidence-ingest contract and debug fixtures
```

## Stop conditions

Stop and report instead of continuing if any of these occur:

1. `run_debug_cases.py --repo .` fails after B1-local fixes.
2. `pytest -q tests/test_phase_b1_evidence_ingest_contract.py` fails.
3. B1 requires changing non-B1 skills.
4. Existing manifests require a bulk schema migration.
5. `source_registry.yaml` requires a policy decision rather than a mechanical merge.
6. Any output attempts to create reports, scorecards, watchlist decisions, or investment recommendations.

## Final Codex response format

Codex should end with:

```text
B1 status: accepted | accepted_with_todos | needs_fix | blocked
Commands run:
- ...
Files changed:
- ...
Issues:
- severity / issue / fix / status
Remaining TODOs:
- ...
Not started:
- B2 segment-research
- B3 company-universe
- B4 segment-company-mapping
- B5 stock-deep-dive
- B6 quality-review
- B7 memo-writer
- B8 refresh-research
- Phase C/D/E/F debug and P2 readiness
```
