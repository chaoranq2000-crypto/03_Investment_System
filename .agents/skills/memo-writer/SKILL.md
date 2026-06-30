---
name: memo-writer
description: Use when turning grounded research into an observation memo, thesis note, watchlist rationale, or follow-up checklist. Do not use for ungrounded conviction statements, direct trade instructions, or replacing evidence review.
---

# Memo Writer

## Goal

将已有证据和研究结论整理成观察备忘录、thesis note 或 watchlist rationale，同时保留证据、反证和不确定性。

## When to use

- 用户要求写投资备忘录、观察清单、假设记录或研究摘要。
- 需要把 segment / stock research 转成 thesis 或 watch item。
- 需要记录 watchlist 变更理由。

## Inputs

- 已有报告、evidence_map、claim_ids、metric_ids。
- 研究问题、观察对象和需要跟踪的指标。
- 风险、反证、TODO 和 next_review_date。

## Responsibilities

- 写清 observation、thesis、supporting evidence、counter-evidence。
- 标注 fact、estimate、inference、opinion。
- 记录 watchlist impact 和后续验证指标。
- 保持研究边界声明。

## Out of scope

- 不生成无证据 conviction statement。
- 不输出买入、卖出、持有建议。
- 不把 watchlist 写成推荐名单。
- 不替代 quality-review。
- 不静默修改 thesis_log 或 watchlist_changes。

## Outputs

- `reports/memos/<date>_<topic>_memo.md`
- `decisions/thesis_log.md` update when requested
- `decisions/watchlist_changes.md` update when requested
- follow-up checklist

## Workflow

1. 读取已有 evidence 和 research outputs。
2. 明确 memo 目标和对象。
3. 写 facts、estimates、inferences、opinion。
4. 写 supporting 和 contradicting evidence。
5. 写 watchlist impact 和 next review。
6. 执行 quality-review 或列出待审查项。

## Guardrails

- memo 只能承接已有证据或显式 TODO。
- 不用情绪化措辞替代证据。
- thesis 必须可被证据支持或证伪。
- watchlist 是研究优先级，不是交易建议。

## Quality checklist

- [ ] memo 有 evidence_snapshot。
- [ ] thesis 有 supporting_claim_ids 或 TODO。
- [ ] counter_evidence 或风险已列出。
- [ ] TODO/MISSING 明确。
- [ ] next_review_date 或 follow-up task 已记录。
- [ ] 未输出买卖建议。
