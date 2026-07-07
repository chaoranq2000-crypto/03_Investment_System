# R5 Patch 9：evidence-ingest R5 stock evidence plan

## 背景

R5 样例质量依赖上游证据密度。当前 evidence-ingest 已有基础契约，但 R5 需要更完整的 stock evidence plan：官方披露、财务结构化、市场快照、同业快照、行业线索、事件线索。本 patch 只做 plan schema 与 validator，不抓取数据。

## 目标

1. 新增 R5 stock evidence plan contract。
2. 新增 example YAML。
3. 新增 validator。
4. 新增 pytest。
5. 输出 readout。

## 允许修改文件

- `.agents/skills/evidence-ingest/references/r5_stock_evidence_plan_contract.md`
- `.agents/skills/evidence-ingest/assets/r5_stock_evidence_plan.example.yaml`
- `.agents/skills/evidence-ingest/scripts/validate_r5_stock_evidence_plan.py`
- `tests/test_validate_r5_stock_evidence_plan.py`
- `reports/p1_6/R5_PATCH_9_EVIDENCE_PLAN_READOUT.md`

## 禁止事项

- 不新增 downloader。
- 不接真实 API。
- 不下载任何公告、行情或新闻。
- 不修改 data/raw / data/processed。
- 不生成真实 claims / metrics。

## 交付物

- R5 stock evidence plan contract。
- example YAML。
- validator。
- tests。
- readout。

## 验收标准

1. plan 至少包含：official_filings、structured_financial_data、market_snapshot、peer_snapshot、industry_context、news_event_clues、investor_relations、source_gap_policy。
2. 每个 evidence request 必须有 `source_priority`、`required_for_pack`、`freshness_requirement`、`fallback_if_missing`。
3. 官方披露优先级高于三方摘要。
4. 缺 disclosure 时必须写 `MISSING_DISCLOSURE`，不得编造。
5. plan 可输出 expected artifacts：manifest rows、claim candidates、metric candidates、ingest log。
6. pytest 通过。

## 测试命令

```bash
python .agents/skills/evidence-ingest/scripts/validate_r5_stock_evidence_plan.py .agents/skills/evidence-ingest/assets/r5_stock_evidence_plan.example.yaml
pytest tests/test_validate_r5_stock_evidence_plan.py
```

## 输出要求

1. 列出修改文件。
2. 粘贴测试结果。
3. 明确说明未抓取真实数据。
4. 输出 readout 文件。
