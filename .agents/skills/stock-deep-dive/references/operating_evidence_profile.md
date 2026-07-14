# stock-deep-dive — Bundle 12R 经营证据接口

`stock-deep-dive` 在 T2 / RP-12R-1 至 RP-12R-5 负责：

- 识别重大业务线；
- 为每条业务线选择一个可组合 archetype；
- 将证据映射到经营 driver；
- 维护收入、毛利、现金流映射；
- 解决分部、产品、项目和主题口径的包含与重叠；
- 保留 residual，不把未解释部分隐藏到“其他”。

调用：

```bash
python scripts/run_r5_bundle12r_operating_evidence_gate.py \
  --input <reviewed_input.yaml> \
  --output-dir <workflow_run>/bundle12r \
  --strict
```

若返回码为 2，必须消费 `R5_bundle12r_backflow_plan.yaml`，不得继续生成新的样例质量 Reader。
