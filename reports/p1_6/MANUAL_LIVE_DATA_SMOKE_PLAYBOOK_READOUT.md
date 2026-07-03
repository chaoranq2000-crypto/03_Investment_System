# MANUAL_LIVE_DATA_SMOKE_PLAYBOOK_READOUT

date: 2026-07-03
status: PASS

## Output

`docs/playbooks/MANUAL_LIVE_DATA_SMOKE_PLAYBOOK.md`

## Coverage

| requirement | status |
|---|---|
| environment variables | done |
| token safety | done |
| temporary output directory | done |
| Tushare daily_basic smoke | documented |
| Tushare income / balancesheet / cashflow smoke | documented |
| Baostock K-line smoke | documented |
| Baostock financial smoke | documented |
| raw snapshot / manifest / metric candidate checks | documented |
| cleanup / isolation | documented with one-file removal only |
| git status checks | documented |
| failure handling | documented |
| outputs not to commit | documented |

## Boundary

- No real API call was executed.
- Live smoke remains manual-only.
- Live smoke output is not connected to reports.
- Token values must not be committed.
