# R5 Patch 11 Readout — sample benchmark placeholder policy

## Result

Status: completed_placeholder_policy

This patch adds sample report benchmark policy metadata only. It does not paste external copyrighted report text, copy sample ratings/trading advice, generate a real stock report, modify R5 composer, or call APIs.

## Files changed

- `benchmarks/sample_reports/README.md`
- `benchmarks/sample_reports/sample_report_metadata.schema.yaml`
- `benchmarks/sample_reports/section_expectation_mapping.yaml`
- `tests/test_sample_report_benchmark_policy.py`
- `reports/p1_6/R5_PATCH_11_SAMPLE_BENCHMARK_POLICY_READOUT.md`

## Tests

```bash
pytest tests/test_sample_report_benchmark_policy.py
```

Result:

```text
tests/test_sample_report_benchmark_policy.py: 4 passed
```
