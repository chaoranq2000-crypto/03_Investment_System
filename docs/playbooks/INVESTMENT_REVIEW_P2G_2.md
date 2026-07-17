# Investment Review P2G-2 操作手册

P2G-2 只消费一份已通过校验且状态为 `ready/verified` 的
`p2g.behavior_cohort.v1`，生成确定性的
`p2g.behavior_observation_set.v1`。它记录跨 episode 的可证明观察，
不生成心理诊断、动机解释、评分、排名、干预或交易建议。

## 阶段边界

- 唯一业务输入是 P2G-1 cohort 对象。
- 不直接读取 P2F artifact、portfolio SQLite、review sidecar、网络或当前时间。
- 不调用模型，不写入任何数据库。
- 输入路径、环境变量、随机值和墙上时钟不进入 artifact identity。
- `insufficient_evidence`、`not_comparable` 和 `not_applicable` 是正常事实状态，
  不会被删除或补猜。
- 本阶段止于 P2G-2；不进入 P2G-3 narrative、干预或行为评分。

## 四个 detector

| detector_id | subject | 观察内容 |
|---|---|---|
| `adjacent_episode_cadence` | 同一 account 的相邻 episode | open-anchor 间隔、闭合后间隔与 overlap |
| `same_instrument_reentry_gap` | episode 与首个后续同 account、同 instrument episode | close-to-next-open gap 是否不超过配置阈值 |
| `episode_scale_transition` | 同一 account 的相邻 episode | 可比规模指标是否达到增减阈值 |
| `holding_duration_transition` | 同一 account 的相邻 episode | 已闭合周期的持有时长是否达到变化阈值 |

相邻关系先按 account 分区，再按 timezone-aware `opened_at` 排序。相同 open
时间不能靠 ID 猜先后，必须返回 `insufficient_evidence / ambiguous_temporal_order`。
重叠周期会显式记录，负 re-entry gap 不会被当作普通观察。

## 结果状态

每个 detector subject 都进入完整 evaluation ledger：

- `observed`：事实和可比性充分，且观察条件成立；
- `not_observed`：事实和可比性充分，但阈值条件不成立；
- `insufficient_evidence`：顺序、事实或时间证明不足；
- `not_comparable`：单位、币种、口径、分母或来源状态不可比较；
- `not_applicable`：subject 不在 detector 适用域，例如 open episode 的
  re-entry gap 或没有后续同标的 episode。

除 `observed` 外的状态必须带受控 `reason_code`。所有状态都会进入 counts，
不会只保留“命中”结果。

## 规模可比性

默认优先级为：

1. `target_position_weight`
2. `target_position_value`
3. `maximum_absolute_quantity`

规则是 fail-closed：

- 两个 episode 必须使用同一 metric family；
- method、unit 与适用的 currency 必须一致；
- 目标权重不能混用不同 denominator 定义；
- `partial`、`ambiguous`、`stale` 或 `unpriced` 不得当作精确值；
- 已出现但不可比较的高优先级 metric 会阻止向低优先级回退；
- quantity fallback 只适用于同 instrument；
- 值和阈值使用十进制字符串，禁止 binary float；
- 负规模和零分母显式返回 `not_comparable`。

阈值边界采用 inclusive 语义：`ratio >= material_increase_ratio` 或
`ratio <= material_decrease_ratio` 视为 material transition。

## 构建

```powershell
.\.conda\investment-system\python.exe -m src.investment_review `
  behavior-observation-build `
  --cohort data/processed/normalized/behavior_cohort.local.json `
  --output data/processed/normalized/behavior_observations.local.json
```

可用 `--detector` 限定 detector，可重复传入：

```powershell
.\.conda\investment-system\python.exe -m src.investment_review `
  behavior-observation-build `
  --cohort data/processed/normalized/behavior_cohort.local.json `
  --detector same_instrument_reentry_gap `
  --detector episode_scale_transition `
  --output data/processed/normalized/behavior_observations.local.json
```

自定义 detector 配置通过 `--detector-config` 传入 JSON 对象。允许局部覆盖，
构建器会补齐并持久化全部 detector 版本、enabled 状态和参数；展开后的完整配置
参与 `observation_set_id`、`evaluation_id` 和 `content_id`。

示例：

```json
{
  "schema_version": "p2g.behavior_detector_config.v1",
  "contract_version": "p2g.behavior_detector.v1",
  "detectors": [
    {
      "detector_id": "same_instrument_reentry_gap",
      "detector_version": "1",
      "enabled": true,
      "parameters": {
        "maximum_gap_seconds": "86400"
      }
    }
  ]
}
```

未知 detector、未知版本、未知参数、float、非法阈值或全部 disabled 会 fail-closed。
输出使用原子 create-only I/O；目标文件已存在时退出码为 `2`，不会覆盖。

## 查询

```powershell
.\.conda\investment-system\python.exe -m src.investment_review `
  behavior-observation-show `
  data/processed/normalized/behavior_observations.local.json `
  --detector-id episode_scale_transition `
  --status not_comparable `
  --account-id acct-1 `
  --reason-code partial_or_ambiguous_source
```

支持以下过滤器，组合时为 AND 语义：

- `evaluation_id`
- `detector_id`
- `status`
- `episode_id`
- `review_id`
- `account_id`
- `instrument_id`
- `reason_code`
- `content_id`

查询只返回深拷贝，不修改 artifact，也不重新推导事实。

## 校验与 source replay

离线结构、hash、配置、registry、ledger、counts 与禁止字段校验：

```powershell
.\.conda\investment-system\python.exe -m src.investment_review `
  behavior-observation-validate `
  data/processed/normalized/behavior_observations.local.json
```

使用精确 P2G-1 cohort 重建并比较 canonical bytes：

```powershell
.\.conda\investment-system\python.exe -m src.investment_review `
  behavior-observation-validate `
  data/processed/normalized/behavior_observations.local.json `
  --source-replay `
  --cohort data/processed/normalized/behavior_cohort.local.json
```

replay 要求 cohort 的 exact `content_id` 与 artifact 冻结引用一致。源 cohort
漂移、结构无效、非 `ready/verified`、配置漂移或 canonical bytes 不一致均返回
`blocked`，命令退出码为 `2`。

## 追溯性

每个 evaluation 保存：

- detector ID、版本、完整参数；
- subject 的 episode/review IDs；
- account 与 instrument dimensions；
- 状态、受控 reason codes 与派生事实；
- P2G-1 `facts_content_id`、section、fact ID、kind 和原始 source refs。

这些字段只证明“观察来自哪些冻结事实”。它们不证明因果关系，也不把结果好坏、
市场走势或事后信息解释为决策质量。
