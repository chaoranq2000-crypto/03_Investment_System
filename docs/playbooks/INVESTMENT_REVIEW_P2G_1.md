# Investment Review P2G-1 操作手册

P2G-1 把一个或多个 P2F review 修订链冻结为 `p2g.behavior_cohort.v1`。
它只保留事实投影，不生成行为标签、心理诊断、交易建议或模型解释。

## 输入要求

每个逻辑 review chain 必须同时提供：

- cutoff 内的全部 predecessor revisions；
- 对应的 P2F review input bundle；
- 唯一、可验证的 current leaf。

同一 JSON 文件也可以是对象数组；CLI 会把每个 `--episode-review` /
`--input-bundle` 文件展开为显式对象集合。文件路径不会进入 artifact identity。

## 构建

```powershell
python -m src.investment_review behavior-cohort-build `
  --episode-review data/processed/reviews/review.rev1.local.json `
  --episode-review data/processed/reviews/review.rev2.local.json `
  --input-bundle data/processed/reviews/review_input.local.json `
  --effective-from "2026-01-01T00:00:00Z" `
  --effective-to "2026-07-01T00:00:00Z" `
  --knowledge-cutoff "2026-07-01T00:00:00Z" `
  --effective-anchor episode_opened_at `
  --output data/processed/reviews/behavior_cohort.local.json
```

可重复 `--account` 和 `--instrument`。instrument 会规范为大写；filters 在 artifact
内排序去重。

有效锚点：

- `episode_opened_at`
- `episode_closed_at`（open episode 会以 `missing_effective_anchor` 排除）

输出文件已存在时命令失败，不覆盖原 artifact。若 cohort 结构合法但 release blocked，
文件仍会创建，命令退出码为 `2`。

## 查询

```powershell
python -m src.investment_review behavior-cohort-show `
  data/processed/reviews/behavior_cohort.local.json

python -m src.investment_review behavior-cohort-show `
  data/processed/reviews/behavior_cohort.local.json `
  --episode-id EPISODE_ID

python -m src.investment_review behavior-cohort-show `
  data/processed/reviews/behavior_cohort.local.json `
  --reason-code ambiguous_current_revision
```

`episode_id`、`review_id` 和 `reason_code` 三种过滤互斥。查询不重新推导事实，也不修改
artifact。

## 验证与 source replay

离线结构验证：

```powershell
python -m src.investment_review behavior-cohort-validate `
  data/processed/reviews/behavior_cohort.local.json
```

显式 P2F source replay：

```powershell
python -m src.investment_review behavior-cohort-validate `
  data/processed/reviews/behavior_cohort.local.json `
  --source-replay `
  --episode-review data/processed/reviews/review.rev1.local.json `
  --episode-review data/processed/reviews/review.rev2.local.json `
  --input-bundle data/processed/reviews/review_input.local.json
```

replay 会按 artifact 内冻结的 selection spec 重建 cohort，并比较 canonical bytes。
缺 source、多余未引用 source、revision ambiguity、P2F replay mismatch 或 content drift
均 fail-closed。

## 排除原因 registry

| reason_code | blocking | 含义 |
|---|---:|---|
| `outside_effective_window` | 否 | effective anchor 不在 `[from,to)` |
| `knowledge_after_cutoff` | 否 | 该 chain 在 cutoff 内没有 revision |
| `missing_effective_anchor` | 否 | 指定 anchor 不存在，例如 open episode 的 close |
| `filter_mismatch` | 否 | 不满足冻结 account/instrument filter |
| `human_rejected` | 否 | 保留给未来 artifact-level rejection |
| `missing_knowledge_time` | 是 | 无法证明 revision 的 knowledge time |
| `schema_invalid` | 是 | P2F source schema/semantic validation 失败 |
| `content_id_mismatch` | 是 | 声明 content ID 与 canonical bytes 不符 |
| `missing_required_fact_section` | 是 | P2F 六个 facts section 不完整 |
| `release_not_ready` | 是 | input bundle 未 release-ready |
| `source_not_verified` | 是 | input bundle source verification 非 verified |
| `source_replay_mismatch` | 是 | review facts 与 bundle 重建不一致 |
| `revision_chain_invalid` | 是 | 断链、缺 predecessor、循环或 transition 非法 |
| `ambiguous_current_revision` | 是 | cutoff 内有多个 current leaf |
| `duplicate_logical_episode` | 是 | 同一 episode 出现多个不可证明关系的 chain |
| `missing_source` | 是 | 缺少 review 绑定的 input bundle |
| `extra_source` | 是 | 传入未被任何 review 引用的 bundle |
| `interpretation_contamination` | 是 | facts projection 无法保持 P2F facts-only 契约 |

## 解释边界

P2F 的人工 `reject` 是 finding-level 解释治理，不是整份 facts artifact 的拒绝。
P2G 会丢弃所有 interpretation sections，同时保留该修订的不可变 facts projection。
禁止把 rejected finding、模型 narrative 或 outcome 文本重新解释为行为事实。
