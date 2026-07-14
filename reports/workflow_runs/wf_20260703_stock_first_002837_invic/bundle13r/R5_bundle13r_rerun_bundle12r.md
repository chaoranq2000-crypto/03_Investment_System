# Bundle 12R 重跑命令

仅当 Bundle 13R 结果为 `ready_for_bundle12r_rerun` 时执行：

```bash
python scripts/run_r5_bundle12r_operating_evidence_gate.py \
  --input R5_bundle13r_promoted_operating_evidence_input.yaml \
  --contract config/r5_bundle12r_operating_evidence_contract.yaml \
  --output-dir reports/workflow_runs/wf_20260703_stock_first_002837_invic/bundle12r_rerun_after_13r \
  --strict
```

重跑结果仍为 `needs_backflow` 时，不得启动 BF12R-001 估值资格刷新。
无论结果如何，`sample_quality_allowed=false`、`p2_allowed=false`。
