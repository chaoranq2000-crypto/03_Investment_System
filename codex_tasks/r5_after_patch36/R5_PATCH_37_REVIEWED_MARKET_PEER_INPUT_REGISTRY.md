# Codex Task Card — R5 Patch 37：reviewed market / peer input registry

## 任务名称

reviewed market / peer input registry

## 背景

当前 readiness / close gate 已明确：R5 仍处于 `R5_CONTRACTS_EXECUTABLE_WITH_TODOS_ONLY`；`valuation_todo` 的原因是估值仍缺 `TODO_MARKET_DATA` / `TODO_PEER_DATA`。下一步不能直接生成估值结论，而应先建立一个可审查的 market / peer input registry，使后续 valuation pack 只能消费已登记、已标注来源等级和 as_of_date 的输入。

## 目标

1. 新增 R5 market / peer reviewed input registry schema。
2. 为 002837 workflow run 建立一个 source-gapped registry fixture，默认保持 TODO，不填真实数值。
3. 新增 validator，检查 as_of_date、source_type、review_status、evidence_id / missing_reason。
4. 更新 quality / readiness 只识别 reviewed registry，不识别散落的市场数据。

## 允许新增 / 修改文件

- `.agents/skills/stock-deep-dive/references/r5_market_peer_input_registry_contract.md`
- `.agents/skills/stock-deep-dive/assets/r5_market_peer_input_registry.example.yaml`
- `.agents/skills/stock-deep-dive/scripts/validate_r5_market_peer_input_registry.py`
- `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_market_peer_input_registry.yaml`
- `tests/test_validate_r5_market_peer_input_registry.py`
- `reports/p1_6/R5_PATCH_37_MARKET_PEER_INPUT_REGISTRY_READOUT.md`

## 禁止事项

- 不联网、不接真实 API、不抓实时行情。
- 不填无法溯源的 current_price、market_cap、PE、PB、PS 或同业倍数。
- 不把 market / peer TODO 改成 pass，除非有 `evidence_id` 且 `review_status: reviewed`。
- 不生成估值结论、目标价或交易动作。
- 不修改历史 R4 报告正文。

## Schema 要求

Registry 至少包含：

```yaml
schema_version: r5_market_peer_input_registry_v0.1
artifact_type: R5_market_peer_input_registry
workflow_id: wf_20260703_stock_first_002837_invic
stock_code: '002837'
as_of_date: null
review_status: pending
market_inputs:
  current_price:
    value: TODO_MARKET_DATA
    unit: CNY_per_share
    evidence_id: null
    source_type: market_snapshot
    missing_reason: TODO_MARKET_DATA
  market_cap:
    value: TODO_MARKET_DATA
    unit: CNY
    evidence_id: null
    source_type: market_snapshot
    missing_reason: TODO_MARKET_DATA
peer_inputs:
  peer_set:
    value: TODO_PEER_DATA
    evidence_id: null
    source_type: peer_snapshot
    missing_reason: TODO_PEER_DATA
  peer_valuation_multiples:
    value: TODO_PEER_DATA
    evidence_id: null
    source_type: peer_snapshot
    missing_reason: TODO_PEER_DATA
allowed_usage:
  - valuation_context_only_when_reviewed
blocking_rules:
  - if review_status != reviewed, valuation pack must remain degraded
```

## 验收标准

1. validator 对 example 和 002837 registry 能通过结构校验。
2. 如果 `review_status: reviewed` 但任一核心字段缺 `evidence_id`，validator 必须失败。
3. 如果没有 `as_of_date` 且状态不是 `pending`，validator 必须失败。
4. TODO registry 不得放行 sample-quality，也不得放行 P2。
5. readout 明确说明“本 patch 不提供真实市场/同业数据”。

## 测试命令

```bash
python -m py_compile .agents/skills/stock-deep-dive/scripts/validate_r5_market_peer_input_registry.py
pytest -q tests/test_validate_r5_market_peer_input_registry.py --tb=short
python .agents/skills/stock-deep-dive/scripts/validate_r5_market_peer_input_registry.py reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_market_peer_input_registry.yaml
```

## 输出要求

完成后输出：新增/修改文件、测试结果、diff summary、未完成项、readout 路径。
