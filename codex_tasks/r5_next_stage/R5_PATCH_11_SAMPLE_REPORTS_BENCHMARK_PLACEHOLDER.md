# R5 Patch 11：sample reports benchmark placeholder policy

## 背景

R5 需要对齐样例质量，但不要在仓库中直接粘贴外部版权研报全文。用户提供的样例可作为本地参考，但 benchmark 目录应先放 README / metadata / placeholder policy。本 patch 不写真实样例正文。

## 目标

1. 新增 sample reports benchmark 使用规则。
2. 新增 sample metadata schema。
3. 新增 section expectation mapping。
4. 新增测试，确保 benchmark 不要求直接复制全文。
5. 输出 readout。

## 允许修改文件

- `benchmarks/sample_reports/README.md`
- `benchmarks/sample_reports/sample_report_metadata.schema.yaml`
- `benchmarks/sample_reports/section_expectation_mapping.yaml`
- `tests/test_sample_report_benchmark_policy.py`
- `reports/p1_6/R5_PATCH_11_SAMPLE_BENCHMARK_POLICY_READOUT.md`

## 禁止事项

- 不粘贴外部版权研报正文。
- 不把样例评级、交易建议复制为系统输出要求。
- 不生成真实个股报告。
- 不修改 R5 composer。
- 不接 API。

## 交付物

- sample reports README。
- metadata schema。
- section mapping。
- tests。
- readout。

## 验收标准

1. README 说明 sample reports 只用于结构、密度、章节能力、证据要求的 benchmark。
2. metadata schema 至少包含：sample_id、company_name、sections_present、forecast_present、valuation_present、technical_present、sentiment_present、catalyst_present、copyright_status、local_user_provided。
3. section mapping 能把样例章节映射到 R5 rubric sections。
4. 明确禁止直接复制外部版权正文到 generated report。
5. pytest 通过。

## 测试命令

```bash
pytest tests/test_sample_report_benchmark_policy.py
```

## 输出要求

1. 列出修改文件。
2. 粘贴测试结果。
3. 输出 readout 文件。
