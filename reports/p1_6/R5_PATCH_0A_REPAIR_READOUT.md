# R5 Patch 0A Readout — format and parse repair

## Result

Status: completed_format_guard

This patch adds a regression test for the existing R5 Patch 0 artifacts. It does not implement R5 validator logic, composer logic, dry-run logic, real stock research output, or live data access.

## Files changed

- `tests/test_r5_patch0_artifacts_parse.py`
- `reports/p1_6/R5_PATCH_0A_REPAIR_READOUT.md`

Existing Patch 0 artifacts were already multi-line and parseable during this run, so no semantic rewrite was needed.

## Diff summary

- Added YAML parse checks for `templates/r5_stock_research_pack.yaml` and `benchmarks/r5_report_quality_rubric.yaml`.
- Added anti-regression checks so core R5 Markdown/YAML files cannot collapse into single-line blobs.
- Added checks that the R5 spec retains the R4/R5 distinction, research-pack fact-source rule, 12 subpacks, 10 report sections, downgrade rules, and no-advice boundary.

## Tests

```bash
python - <<'PY'
import yaml
for p in ["templates/r5_stock_research_pack.yaml", "benchmarks/r5_report_quality_rubric.yaml"]:
    with open(p, "r", encoding="utf-8") as f:
        yaml.safe_load(f)
print("yaml ok")
PY
pytest tests/test_r5_patch0_artifacts_parse.py
```

Result:

```text
yaml ok
tests/test_r5_patch0_artifacts_parse.py: 4 passed
```

## Not Done

- No R5 validator/composer/dry-run implementation in this patch.
- No real stock report generation.
- No historical workflow run modifications.
