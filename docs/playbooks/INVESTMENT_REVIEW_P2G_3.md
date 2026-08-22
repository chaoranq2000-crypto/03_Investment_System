# Investment Review P2G-3 操作手册

P2G-3 只消费一份已通过校验且为 `ready/verified` 的
`p2g.behavior_observation_set.v1`，以及一份已经记录到本地的严格 JSON 响应，
生成 `p2g.behavior_hypothesis_set.v1` 候选假设。所有假设的状态固定为
`proposed`；本阶段不接受、拒绝或修订假设。

## 阶段边界

- 完全离线：不调用 provider，不读取 API key，不联网。
- 不读取 portfolio/review SQLite，也不重新查询 P2F/P2G-1 来源。
- 不修改 P2G-2 artifact；失败时精确 copy-through 源观察对象。
- 不输出心理诊断、人格标签、确定性情绪因果、机械评分、数值置信度、
  交易/仓位/止损建议、结果倒推或事后最佳价格。
- 不进入 P2G-4 人工 accept/reject/correct、revision、diff/list。
- 不进入 intervention、个人长期画像、方法库、Web/UI 或数据库 migration。

## 实际命名映射

P2G-2 的最小可引用单位是 `evaluation_id`，不存在独立的
`observation_id`。因此 P2G-3 使用：

- `evaluation_refs`：支持候选假设的 P2G-2 `observed` evaluations；
- `counterevidence_evaluation_refs`：反证或不支持该候选的 evaluations；
- `evaluation_inventory`：输出中冻结的引用投影及每条源 evaluation 的 SHA-256；
- `source_observation_set.temporal_scope`：精确冻结 P2G-2 的 effective window、
  knowledge cutoff、anchor 与 filters；候选 scope 不得越过 effective window 或 cutoff；
- `temporal_perspective: retrospective`：复用现有解释时态，不把跨 episode
  归纳伪装为 decision-time 信息。

每条候选必须有支持理由、反证引用或显式搜索说明、实质替代解释、假设前提、
不确定性、可证伪条件和下一步所需证据。支持 evaluations 覆盖不足两个 episode
时，只允许受限表述，并保存 `insufficient_repeat_evidence` warning。

## 响应契约

响应必须是一个 UTF-8 JSON object，不能带 Markdown fence、自由文本前后缀、
工具调用或未知字段。完整 schema：

```text
docs/contracts/P2G_3_BEHAVIOR_HYPOTHESIS_RESPONSE.schema.json
```

最小示意：

```json
{
  "schema_version": "p2g.behavior_hypothesis_response.v1",
  "hypotheses": [
    {
      "statement": "在引用范围内，该跨周期关系可能是仍需验证的候选模式。",
      "scope": {
        "episode_ids": ["episode-a", "episode-b"],
        "start_at": "2026-01-01T00:00:00Z",
        "end_at": "2026-06-30T23:59:59Z",
        "market_contexts": []
      },
      "evaluation_refs": ["evaluation:00000000000000000000000000000000"],
      "supporting_reasons": ["引用 evaluation 记录了该有限范围内的关系。"],
      "counterevidence_evaluation_refs": [],
      "counterevidence_search": "已检查同一 source set 的其他 cutoff-visible evaluations。",
      "alternative_explanations": ["不同 episode 的计划周期可能并不可比。"],
      "assumptions": ["引用范围的上下文具有最低限度可比性。"],
      "uncertainty_notes": ["样本有限，不能推导长期人格或稳定因果。"],
      "falsification_conditions": ["后续可比样本不再出现该关系时，候选减弱。"],
      "next_observations_needed": ["补充更多 cutoff-safe episode 和计划周期证据。"],
      "temporal_perspective": "retrospective"
    }
  ]
}
```

## 离线构建

```powershell
.\.conda\investment-system\python.exe -m src.investment_review `
  behavior-hypothesis-interpret `
  --artifact data/processed/normalized/behavior_observations.local.json `
  --model-id recorded-model-v1 `
  --generated-at "2026-07-18T12:00:00Z" `
  --model-response data/processed/normalized/behavior_hypothesis_response.local.json `
  --output data/processed/normalized/behavior_hypotheses.model.local.json `
  --attempt-output data/processed/normalized/behavior_hypothesis_attempt.local.json
```

`--model-response` 只是读取已存在的本地响应。命令没有 live-provider 分支。
`--simulate-unavailable` 用于验证安全 fallback。

主输出和 attempt receipt 使用 create-only 成对写入。输入、输出和 receipt 路径
必须互不相同；任一路径已存在时拒绝覆盖。如果第二个文件创建失败，刚创建的主输出
会被单文件回滚，不留下假成功的交付对。保存前还会交叉校验 output/source/model/
response/warnings 绑定，拒绝把两次不同 attempt 的合法对象拼成一对。

## 失败语义

以下情况均不产生部分 hypotheses：

- provider unavailable；
- JSON 无法解析或超过 1 MiB；
- strict schema、引用闭合或 scope 校验失败；
- 任一候选触发 no-diagnosis/no-advice/no-score/no-hindsight 护栏；
- P2G-2 source 不是 valid/ready/verified。

失败主输出是源 P2G-2 observation artifact 的 copy-through；独立 receipt 保存
`status`、稳定 error code、模型/时间、原始响应哈希、规范化响应哈希和输出绑定，
但不保存响应全文。与 P2F-3 一致，只要 fallback 与 receipt 已安全写入，interpret
命令返回 `0`；调用方必须读取 receipt 的 `status`，不能把退出码误当成假设已生成。

## 校验与 source replay

离线结构、schema、ID/hash、引用 inventory、warning 和护栏校验：

```powershell
.\.conda\investment-system\python.exe -m src.investment_review `
  behavior-hypothesis-validate `
  data/processed/normalized/behavior_hypotheses.model.local.json
```

使用精确 P2G-2 artifact 复核 content ID、observation-set ID、evaluation 引用与
evaluation SHA-256：

```powershell
.\.conda\investment-system\python.exe -m src.investment_review `
  behavior-hypothesis-validate `
  data/processed/normalized/behavior_hypotheses.model.local.json `
  --source-replay `
  --observation-artifact data/processed/normalized/behavior_observations.local.json
```

校验 blocked 时退出码为 `2`。source replay 不重新调用模型；它只证明候选仍绑定
到同一份已验证 P2G-2 source 和同一组 evaluation 投影。

## 契约文件

```text
docs/contracts/P2G_3_BEHAVIOR_HYPOTHESIS_RESPONSE.schema.json
docs/contracts/P2G_3_BEHAVIOR_HYPOTHESIS_SET.schema.json
docs/contracts/P2G_3_BEHAVIOR_HYPOTHESIS_ATTEMPT.schema.json
```

这些 schema 与 `src/investment_review/behavior_hypotheses.py` 是 P2G-3 的实现契约；
本手册是唯一操作入口。候选假设不是事实、心理诊断、长期画像或交易建议。
