# Investment Review P2H Stage 1 操作手册

## 边界

P2H Stage 1 保存“行为假设候选”和不可变人工复核事件。候选必须绑定到明确的 P2G/P2F
artifact、保留替代解释，并至少提供反证或显式 source gap。它不从事实自动推导心理原因，
不调用模型，不输出买卖、仓位或收益建议，不计算机械分数，也不写个人画像、
`PersonalPlaybook`、干预方案或 UI。

`accepted_for_observation` 只表示现有证据足以支持继续观察；它不表示原因已被证明，
不构成心理诊断或交易建议。

## 数据流

```text
显式 P2G/P2F artifact
  -> candidate draft
  -> canonical build / offline validate / source replay
  -> create-only sidecar candidate
  -> immutable human review events
  -> as_of + knowledge_cutoff projected state
```

P2G/P2F source artifact 始终只读。P2H 写入既有 investment-review sidecar 的独立表；
初始化是 v2 sidecar 上的幂等加表，不修改 portfolio SQLite。

## 合成示例

仓库提供只含虚构标识的 fixture：

```text
tests/fixtures/investment_review_p2h_stage1/synthetic_observation_source.json
tests/fixtures/investment_review_p2h_stage1/candidate_draft.json
```

构建候选（输出路径必须尚不存在）：

```powershell
python -m src.investment_review behavior-candidate-build `
  --input tests/fixtures/investment_review_p2h_stage1/candidate_draft.json `
  --output .codex_tmp/p2h_candidate.json
```

离线校验与 exact source replay：

```powershell
python -m src.investment_review behavior-candidate-validate `
  .codex_tmp/p2h_candidate.json `
  --source-replay `
  --source-artifact tests/fixtures/investment_review_p2h_stage1/synthetic_observation_source.json
```

初始化单独 sidecar 并 create-only 导入：

```powershell
python -m src.investment_review `
  --db .codex_tmp/p2h_review.sqlite3 `
  init

python -m src.investment_review `
  --db .codex_tmp/p2h_review.sqlite3 `
  behavior-candidate-ingest .codex_tmp/p2h_candidate.json `
  --source-artifact tests/fixtures/investment_review_p2h_stage1/synthetic_observation_source.json
```

完全相同的候选再次导入返回 `SKIPPED`；同 ID 不同 payload 返回冲突，不能覆盖历史。

## 人工复核事件

先从构建结果取得精确 `candidate_id`，再准备一个显式事件 JSON。示例字段如下：

```json
{
  "candidate_id": "candidate:<exact-content-derived-id>",
  "event_type": "submitted",
  "reviewed_at": "2026-07-20T13:00:00Z",
  "effective_at": "2026-07-20T13:00:00Z",
  "knowledge_at": "2026-07-20T13:00:00Z",
  "reviewer_ref": "synthetic-human-reviewer",
  "rationale": "The candidate is submitted for bounded human review.",
  "evidence_cutoff": "2026-07-20T12:00:00Z",
  "supersedes_event_id": null,
  "supersedes_candidate_id": null,
  "provenance": {
    "submitter_kind": "human",
    "source_locator": "synthetic/submitted.json",
    "tool_version": "p2h.behavior_hypothesis_review_event.builder.v1"
  }
}
```

记录事件：

```powershell
python -m src.investment_review `
  --db .codex_tmp/p2h_review.sqlite3 `
  behavior-review-event-record `
  --input .codex_tmp/p2h_submitted_event.json
```

支持 `submitted`、`accepted_for_observation`、`revision_requested`、`rejected`、
`superseded` 和不改变状态的 `note_added`。事件只新增，不更新、不删除；修订通过新 candidate
和 supersession 关系表达。

## 查询、投影与重放

```powershell
python -m src.investment_review --db .codex_tmp/p2h_review.sqlite3 `
  behavior-candidate-list --status accepted_for_observation --scope-kind cohort

python -m src.investment_review --db .codex_tmp/p2h_review.sqlite3 `
  behavior-candidate-show candidate:<exact-content-derived-id>

python -m src.investment_review --db .codex_tmp/p2h_review.sqlite3 `
  behavior-candidate-status candidate:<exact-content-derived-id> `
  --as-of 2026-07-20T14:00:00Z `
  --knowledge-cutoff 2026-07-20T14:00:00Z

python -m src.investment_review --db .codex_tmp/p2h_review.sqlite3 `
  behavior-candidate-replay candidate:<exact-content-derived-id> `
  --source-artifact tests/fixtures/investment_review_p2h_stage1/synthetic_observation_source.json
```

`as_of` 控制业务有效时间，`knowledge_cutoff` 控制当时可知范围。投影按
`effective_at -> knowledge_at -> reviewed_at -> review_event_id` 排序；同一前三项上出现多个
状态变更事件会显式冲突，不能靠 ID tie-break 静默选择。

## 常见失败码

| code | 含义 |
|---|---|
| `CANDIDATE_SCHEMA_INVALID` | candidate 不符合封闭 schema |
| `CANDIDATE_ID_MISMATCH` / `CANDIDATE_HASH_MISMATCH` | 内容与确定性身份不一致 |
| `SOURCE_HASH_MISMATCH` / `SOURCE_REF_MISSING` | exact source replay 失败 |
| `SOURCE_REF_AMBIGUOUS` | source 内引用不是唯一标识 |
| `P2G_SOURCE_INVALID` / `P2G_SOURCE_UNVERIFIED` | P2G source 自身未通过门禁 |
| `INVALID_REVIEW_TRANSITION` | 人工事件状态跃迁非法 |
| `CONCURRENT_STATE_EVENTS` | 同一语义时点存在冲突状态事件 |
| `REVIEW_EVENT_ID_CONFLICT` | 同事件 ID 出现不同 payload |
| `POLICY_PSYCHOLOGY_DIAGNOSIS` / `POLICY_DIRECT_ADVICE` | 越过无诊断或无建议边界 |

CLI 成功返回退出码 `0`；验证 blocked、冲突或其他契约失败返回退出码 `2`。错误输出只包含
稳定类型、错误码和必要标识，不回显完整候选 payload。

## 暂停点

完成候选、人工事件、查询和 source replay 后停止。P2H Stage 2 的 intervention/experiment、
个人画像或方法库写入、UI/Web/API 和自动模型生成均不在本阶段范围内。
