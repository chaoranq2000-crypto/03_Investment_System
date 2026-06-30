---
name: evidence-ingest
description: Use when importing, registering, extracting, hashing, or deduplicating evidence into data/raw, data/processed, and data/manifests. Do not use for investment conclusions, scoring, watchlist decisions, or narrative reports.
---

# Evidence Ingest

## Goal

把公告、年报、行业报告、纪要、数据表等证据放入正确目录，并登记为可追溯的 `evidence_id` 记录。

## When to use

- 用户提供 PDF、公告、CSV、网页截图、纪要或数据源，需要归档和登记。
- 需要从原始证据抽取文本或表格。
- 需要去重、生成 hash、更新 `data/manifests/evidence_manifest.csv`。

## Inputs

- 原始文件或来源路径。
- source_type、publisher、publish_date、title 等元数据。
- 关联的 segment_id、company_id、stock_code 或 research question。

## Responsibilities

- 将原始证据放入 `data/raw/<category>/`。
- 将加工文本放入 `data/processed/text/`，表格放入 `data/processed/tables/`。
- 生成或校验 `evidence_id`。
- 登记 manifest 字段：路径、hash、来源等级、状态、license_note。
- 标记缺失字段为 `TODO`、`MISSING` 或 `UNVERIFIED`。

## Out of scope

- 不输出投资结论。
- 不给 segment 或 company 打分。
- 不纳入或移出 watchlist。
- 不把证据摘要写成最终研报。
- 不覆盖 `data/raw/` 中已有原始文件。

## Outputs

- `data/raw/<category>/<file>`
- `data/processed/text/<file>`
- `data/processed/tables/<file>`
- `data/manifests/evidence_manifest.csv`
- 证据卡或 evidence map 草稿。

## Workflow

1. 判断 source_type 和目标 raw 子目录。
2. 检查同名文件和 hash，避免重复导入。
3. 保存原始文件；如已存在，新增版本或停止请求人工确认。
4. 抽取文本或表格到 processed 目录。
5. 生成 `evidence_id` 并更新 manifest。
6. 标记 reliability_rank、status、license_note。
7. 输出本次新增、跳过和待补字段清单。

## Guardrails

- `data/raw/` 原始证据只新增，不覆盖、不编辑。
- 不编造来源、标题、发布日期、页码、路径或 hash。
- D 级来源只能作为线索，不能单独支撑 material claim。
- 证据登记不是结论生成；任何结论必须交给后续 research 或 review skill。

## Quality checklist

- [ ] raw 文件路径正确。
- [ ] processed 文件没有写回 raw。
- [ ] `evidence_id` 稳定且可读。
- [ ] manifest 字段完整或显式标记 TODO/MISSING。
- [ ] reliability_rank 和 status 已标注。
- [ ] license_note 已记录。
- [ ] 未输出买卖建议。
