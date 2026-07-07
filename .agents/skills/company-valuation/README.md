# Company Valuation

`company-valuation` is an A-share Research OS sub-skill for `stock-deep-dive`.

It converts reviewed financial metrics, forecast assumptions, market snapshots and peer context into:

```text
valuation_model.yaml
valuation_snapshot.yaml
peer_comparison.csv
sensitivity_table.csv
valuation_section_draft.md
valuation_gap_requests.yaml
valuation_quality_handoff.yaml
```

It does **not** acquire data, promote claims, generate business exposure proof, assemble the full stock report, or output direct trading advice.

## Normal caller

```text
stock-deep-dive RP6 / SDD-2.5
```

## Main references

```text
references/valuation_model_contract.md
references/method_selection.md
references/output_writing_rules.md
```

## Core boundary

Use valuation as research context:

```text
估值情景 / 估值分布 / 同业倍数位置 / 敏感性 / 反证 / 后续验证
```

Do not use it as:

```text
买入 / 卖出 / 持有 / 仓位 / 目标价指令 / 保证收益
```
