---
name: quality-review
description: Use when checking evidence traceability, claim types, stale evidence, metric definitions, counter-evidence, missing data, update logs, and investment-safety boundaries. Do not use to generate new unreviewed claims or trade instructions.
---

# Quality Review

## Goal

检查研究产物是否可追溯、口径清楚、不确定性可见、反证可见、更新有痕，并且不输出直接交易指令。

## When to use

- 交付 segment report、stock report、comparison、memo 或 refresh log 前。
- 修改 scorecard、watchlist、thesis 或 exposure 记录前后。
- 发现证据冲突、缺失或口径不一致时。

## Inputs

- 待审查文件路径。
- 关联 evidence_id、claim_id、metric_id。
- 相关 config、templates、manifest 和 decisions。

## Responsibilities

- 检查 material claim 是否有证据。
- 检查 claim_type 是否混淆。
- 检查指标口径、单位、周期和来源。
- 检查风险、反证、missing data。
- 检查报告路径和输出边界。
- 输出问题清单、严重程度和修复建议。

## Out of scope

- 不生成新的未经复核结论。
- 不替代 evidence-ingest。
- 不替代 segment 或 stock research。
- 不输出买卖建议。
- 不静默修改报告；需要修复时明确列出改动。

## Outputs

- quality review note
- evidence gap list
- stale / contradicted claim list
- required fixes
- optional follow-up tasks

## Workflow

1. 读取待审查产物和关联 evidence map。
2. 检查 material claim 引用。
3. 检查 claim_type、metric、exposure 和 scorecard。
4. 检查风险、反证和 TODO/MISSING。
5. 检查 refresh/change log 要求。
6. 检查是否存在直接交易指令。
7. 输出通过、条件通过或不通过结论。

## Guardrails

- 质量审查优先报告问题，不粉饰缺口。
- 无证据结论必须标为 TODO/MISSING/LOW_CONFIDENCE/UNVERIFIED。
- 管理层表述、券商预测和媒体叙事必须明确标签。
- 评分、memo 和 watchlist 都不是交易信号。

## Quality checklist

1. 是否所有关键结论都有 `evidence_id` 或 `claim_id`。
2. 是否混淆事实、估计、推断、观点。
3. 是否把管理层表述当成事实。
4. 是否把券商预测当成事实。
5. 是否标记缺失数据。
6. 是否列出反证和不确定性。
7. 是否说明指标口径、单位和周期。
8. 是否存在过期证据。
9. 是否有更新日志要求。
10. 是否避免买卖建议。
