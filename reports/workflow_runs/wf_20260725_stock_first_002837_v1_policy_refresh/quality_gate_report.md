# 002837 V1 policy refresh quality gate

- Workflow: `wf_20260725_stock_first_002837_v1_policy_refresh`
- Derived status: `accepted_with_todos`
- Automated report quality: `pass`
- Final report review: `not_requested`

| Gate | Status | Evidence summary |
|---|---|---|
| G0 | pass | 002837、两份正式披露、离线边界和目标run均明确。 |
| G1 | pass | 两份PDF与两份processed text哈希一致，页码locator全部解析。 |
| G2 | pass | 直接披露标为fact；room/liquid关系标为有边界的inference。 |
| G3 | pass | 使用的每个数均有期间、单位、来源、页码和方法；缺失驱动未使用。 |
| G4 | pass | ai_server_liquid_cooling exposure由正式披露下界与显式缺口支持。 |
| G5 | not_applicable | 本次stock-first刷新不重建company universe。 |
| G6 | pass | room/liquid部分重叠与未知金额并存；cabinet关系保持unknown且未聚合。 |
| G7 | pass | 自动报告展示事实、来源、限制和TODO，无隐藏缺口。 |
| G8 | pass | backflow为run-scoped更新；未越权修改全局exposure。 |
| G9 | pass | 没有交易指令、仓位建议、收益保证或确定性承诺。 |
| G10 | pass | 六件套唯一，辅助产物、重放receipt和哈希索引齐全。 |

四条 high issue 均保持 open，但它们是可见、未使用、非阻断的 unknown 或 method limitation。severity 本身不替代 current-goal disposition。
