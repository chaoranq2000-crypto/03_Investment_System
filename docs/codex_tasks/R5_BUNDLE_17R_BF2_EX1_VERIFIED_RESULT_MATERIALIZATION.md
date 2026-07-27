# R5 Bundle 17R-BF2-EX1 — Verified Result Materialization

## Baseline and boundary

- Required baseline ancestor: `07088cf73f031858cc0bae92129ea86a1cd16a93`
- Current branch family: `codex/r5-bundle17r-bf2-execution-receipts`
- Stage remains inside Bundle 17R targeted backflow / BF2 execution.
- Do **not** open Bundle 18R until the physical 16R → 15R → 14R → 17R rerun reaches 4/4 engineering pass and zero blocker occurrences.
- Do **not** mutate canonical workflow state, synthesize a human-review decision, grant sample quality, or open P2.

## Why this patch exists

BF1 compiled every blocker occurrence into deterministic work orders. BF2 installed an exact-hash intake,
receipt, artifact-classification, promotion-manifest, and review-handoff gate. The remaining operator gap is
that a hand-written BF2 result can claim that a check passed without binding that claim to a physical check
report or review record.

EX1 materializes BF2-compatible result packages only after proving:

1. the BF1 work-order and issue-ledger files are exact-hash bound by the BF1 generation lock;
2. the result spec owns the declared blocker occurrences;
3. a passed result resolves every blocker owned by that work order;
4. every exact BF1 acceptance-check string has a passed check entry;
5. every passed check binds a physical evidence file and exact SHA-256;
6. reviewer-owned routes bind a real, hash-backed manual attestation;
7. every dependency work order is already passed;
8. repository promotion targets are safe and collision-free;
9. local source files are copied only into the BF2 dropzone, never into the repository.

## Added paths

```text
.github/workflows/r5_bundle17r_bf2_ex1.yml
config/r5_bundle17r_verified_result_policy.yaml
docs/codex_tasks/R5_BUNDLE_17R_BF2_EX1_VERIFIED_RESULT_MATERIALIZATION.md
schemas/r5_bundle17r_verified_result_manifest.schema.json
schemas/r5_bundle17r_verified_work_order_spec.schema.json
scripts/run_r5_bundle17r_verified_result_materializer.py
src/research/r5_bundle17r_verified_result_materializer.py
templates/r5_bundle17r_verified_result_manifest.yaml
templates/r5_bundle17r_verified_work_order_spec.yaml
tests/test_r5_bundle17r_verified_result_materializer.py
tests/test_r5_bundle17r_verified_result_materializer_cli.py
```

## Required execution sequence

### 1. Apply and test the implementation

```bash
git apply --check r5_bundle17r_bf2_ex1_verified_results.patch
git apply r5_bundle17r_bf2_ex1_verified_results.patch
python -m py_compile \
  src/research/r5_bundle17r_verified_result_materializer.py \
  scripts/run_r5_bundle17r_verified_result_materializer.py
pytest -q \
  tests/test_r5_bundle17r_verified_result_materializer.py \
  tests/test_r5_bundle17r_verified_result_materializer_cli.py
```

### 2. Create the run manifest

Copy `templates/r5_bundle17r_verified_result_manifest.yaml` into `.local/` and replace the three
input hashes with the exact BF1 physical hashes. The declared baseline must remain the implementation
commit or a reviewed ancestor.

### 3. Materialize specs in dependency batches

Place one spec per BF1 work order beneath:

```text
.local/r5_bundle17r_verified_result_specs/<work_order_id>/spec.yaml
```

Execute in BF1 order:

```text
B0 physical integrity / route review
B1 official evidence
B2 evidence mapping and qualification
B3 operating economics and overlap
B4 forecast and valuation
B5 semantic Reader and traceability
B6 terminal 16R → 15R → 14R → 17R rerun
```

Do not mark a work order passed until all its exact acceptance checks have physical evidence receipts.

### 4. Run EX1 twice

```bash
python scripts/run_r5_bundle17r_verified_result_materializer.py \
  --repo-root . \
  --manifest .local/R5_bundle17r_bf2_ex1_manifest.yaml \
  --output-dir .local/r5_bundle17r_bf2_ex1_run_a

python scripts/run_r5_bundle17r_verified_result_materializer.py \
  --repo-root . \
  --manifest .local/R5_bundle17r_bf2_ex1_manifest.yaml \
  --output-dir .local/r5_bundle17r_bf2_ex1_run_b
```

Require byte-identical output trees. The configured dropzone becomes the input to existing BF2.

### 5. Run existing BF2

```bash
python scripts/run_r5_bundle17r_backflow_execution.py \
  --repo-root . \
  --manifest .local/R5_bundle17r_bf2_execution_manifest.yaml
```

Inspect all receipts, unresolved blocker occurrences, rejected artifacts, target collisions, and the
status proposal. Generated `reports/p1_6/r5_bundle17r_bf2*` directories remain local by default.

### 6. Resolve actual research work

EX1 is not a substitute for the physical research/model reruns. For the four cases, resolve the existing
BF1 work orders with the economic bridges already defined by policy:

- `301217`: HVLP generation / processing fee / capacity / utilization / certification;
- `600988`: commodity price / production / recovery / unit cost / stripping / capex;
- `603259`: backlog / project stage / conversion / capacity / mix / cash conversion;
- `600673`: quota-price-volume, materials capacity and mix, liquid-cooling project value and acceptance,
  IDC utilization and unit revenue, consolidation and financing cost.

### 7. Release boundary

The success condition for leaving 17R targeted backflow is still:

```text
4 / 4 engineering pass
+ 0 blocker occurrences
+ two-run deterministic equality for 16R / 15R / 14R / 17R
+ pending exact-hash human-review handoff for every passing case
+ sample_quality_allowed = false
+ p2_allowed = false
```

Only then may a separate commit propose Bundle 18R exact-hash human review.

## Commit boundary

Recommended commits:

1. `feat(r5): add verified BF2 result materialization gate`
2. `research(r5): add reviewed targeted-backflow result packages` — only reviewed, promotable physical
   artifacts; no caches, ZIPs, screenshots, raw local runs, or unrelated changes.
3. `chore(r5): bind BF2 receipts and activation proposal` — only after exact-hash verification.

The first implementation commit should contain only the 11 paths listed above.
