---
name: refresh-research
description: Use when updating existing research with new evidence, stale claims, changed scorecards, reports to regenerate, and change logs. Do not use to silently rewrite reports or start unrelated new research.
---

# Refresh Research

## Goal

根据新增证据更新既有研究状态，输出变化，而不是静默重写历史报告。

## When to use

- 新增 evidence 可能影响旧 claim、scorecard、watchlist 或报告状态。
- 需要标记 stale、superseded、contradicted claims。
- 需要输出 refresh log、updated_scorecards、reports_to_regenerate。

## Inputs

- 新增 evidence_id list。
- affected_segments、affected_companies、affected_reports。
- 旧 report evidence_snapshot、claim_ids、metric_ids。

## Responsibilities

- 对比新旧 evidence snapshot。
- 标记 claim 状态变化。
- 汇总 scorecard 变化。
- 输出 reports_to_regenerate。
- 记录 watchlist 或 thesis 可能变化。

## Out of scope

- 不静默覆盖旧报告。
- 不无证据改写 score。
- 不自动批量抓取所有公告。
- 不输出交易指令。
- 不把 refresh 扩展成全市场监控。

## Outputs

- `reports/refresh/<date>_refresh_log.md`
- `reports/refresh/stale_claims.csv`
- `reports/refresh/updated_scorecards.yaml`
- `reports/refresh/reports_to_regenerate.yaml`
- decisions change note when needed

## Workflow

1. 列出新增 evidence。
2. 匹配受影响的 claims、metrics、segments、companies。
3. 标记 stale / superseded / contradicted / low_confidence。
4. 判断 scorecard 是否变化。
5. 判断哪些报告需要重跑。
6. 输出 refresh log 和人工复核项。
7. 执行 quality-review。

## Guardrails

- 旧结论变化必须有 change log。
- 不删除旧 evidence 状态。
- 冲突证据必须并列呈现。
- refresh 不是交易信号生成器。

## Quality checklist

- [ ] 新增 evidence 已登记。
- [ ] 受影响 claim 已列出。
- [ ] stale / superseded / contradicted 状态已标注。
- [ ] scorecard 变化有证据。
- [ ] reports_to_regenerate 已列出。
- [ ] watchlist 变化已写入 decisions 或 TODO。
- [ ] 未输出买卖建议。
