# R5 Patch 33 — Market and Peer Input Stubs and Validators

status: `TASK_CARD`

## 背景

R5 sample-quality 最关键的后续缺口之一是 market_snapshot / peer_snapshot。但当前阶段不能调用实时 API。应先建立输入 stub 与 validator。

## 目标

定义 market / peer input schema，并用 002837 source-gapped workflow 生成 TODO-visible stubs。

## 允许修改

```text
.agents/skills/stock-deep-dive/references/r5_market_peer_input_contract.md
.agents/skills/stock-deep-dive/assets/r5_market_snapshot.example.yaml
.agents/skills/stock-deep-dive/assets/r5_peer_snapshot.example.yaml
.agents/skills/stock-deep-dive/scripts/validate_r5_market_peer_inputs.py
tests/test_validate_r5_market_peer_inputs.py
reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_market_snapshot_stub.yaml
reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_peer_snapshot_stub.yaml
reports/p1_6/R5_PATCH_33_MARKET_PEER_INPUTS_READOUT.md
```

## 要求

- market snapshot 必须有 `as_of_date` 或 `missing_reason: TODO_MARKET_DATA`。
- peer snapshot 必须有 peer set selection method 或 `missing_reason: TODO_PEER_DATA`。
- 不能填入未审查价格、市值、PE、PB、PS。
- validator 必须在 sample-quality candidate 缺 market/peer 时返回 blocking。

## 全局禁止事项

- 不生成任何买入、卖出、持有、建仓、减仓、仓位建议。
- 不生成 sample-quality 个股报告。
- 不进入 P2。
- 不调用 live API。
- 不把 TODO / MISSING_DISCLOSURE / LOW_CONFIDENCE_CLUE_ONLY 写成事实。
- 不用 readout 自述替代实际命令、exit_code、stdout/stderr 和 artifact evidence。


## 必跑命令

```bash
python -m py_compile .agents/skills/stock-deep-dive/scripts/validate_r5_market_peer_inputs.py
python -m pytest -q tests/test_validate_r5_market_peer_inputs.py --tb=short
python .agents/skills/stock-deep-dive/scripts/validate_r5_market_peer_inputs.py --market reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_market_snapshot_stub.yaml --peer reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_peer_snapshot_stub.yaml
```

## 验收标准

- TODO stubs 可通过 source-gapped draft 验证。
- sample-quality path 缺 market/peer 必须 fail。
- readout 包含命令证据。
