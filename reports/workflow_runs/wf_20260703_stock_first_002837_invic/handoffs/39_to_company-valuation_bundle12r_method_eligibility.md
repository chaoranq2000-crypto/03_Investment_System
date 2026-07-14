# Handoff: stock-deep-dive -> company-valuation

## Objective

分别判定同业倍数、DCF与SOTP资格，禁止方法间补偿。

## Result

- 同业：0家满足业务定义、期间、口径和置信度要求，`not_eligible`。
- DCF：OCF有3期，capex仅2期，且营运资金桥、税率、WACC、终值增长不合格，`not_eligible`。
- SOTP：三个重大业务均缺少完整独立财务量、适用方法或重叠消除，`not_eligible`。

仅保留反向与情景估值作为上下文；本轮不重算估值中枢。
