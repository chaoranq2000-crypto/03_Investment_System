# Investment Review 产品闭环操作手册

## 1. 定位与适用范围

本阶段把已有的可追溯导入、Trade Episode、组合上下文和 P2E-3/P2F facts-only
产物串成一个本地候选产品。它是单独授权的 **product-completion 系统集成阶段**，
不是 P2H Stage 2 Slice B，也不改变任何既有 Phase 1、P2A、P2C、P2E-3、P2F、
P2G 或 P2H 的数据、验证和发布边界。

本手册只描述五个有顺序的产品门禁。后续阶段必须同时具备前一阶段 checkpoint、
验证证据和干净 tracked tree；不能因为代码存在、命令可调用或页面可打开而跳过门禁。

```text
P1 mapping provenance + fee/correction/schema contract
  -> P2 read-only sync + fee projection
  -> P3 facts-only review runner
  -> P4 local API/UI workflow
  -> P5 in-process automation + candidate acceptance
```

## 2. 全程不变的事实与写入边界

- 正式 portfolio SQLite 只能以 SQLite `mode=ro` 打开；校验时同时使用
  `query_only`、`quick_check` 和执行前后 SHA-256。禁止建表、迁移、WAL、修正费用或
  任何其他源库写入。
- 新增状态只写明确配置的候选 `investment_review.sqlite3` sidecar。不得随当前工作
  目录静默生成多个 sidecar，不得修改用户已有 sidecar，也不得把 legacy v1 库静默升级。
- schema 变化只能 additive；源事件、既有 canonical artifact 和历史修订保持不可变。
- 每个事实、快照、决策、修订和运行都保留来源、稳定身份、有效时间与知悉时间。
  `known_at` 超过 cutoff 的 future-known 数据不能进入历史上下文。
- `unknown`、`unlinked`、`missing`、`partial`、`ambiguous`、`stale`、`unpriced`、
  `blocked` 和 `failed` 必须原样显示，不能补零、隐藏或改名为 `ready`。
- 历史决策理由只能来自人工输入，不能从成交、收益或事后结果推断。

## 3. 五阶段门禁

| 阶段 | 进入条件 | 本阶段才允许的能力 | 退出证据 |
|---|---|---|---|
| P1 | 包、分支、baseline、setup commit 和源库只读证据通过 | 只读刷新 mapping provenance；定义 `actual/estimated/unknown`；增加候选 sidecar 的 additive schema、追加修订和运行元数据契约 | generated/reviewed mapping 三个 hash 匹配；严格 mapping validator、P1 tests、source hash 通过 |
| P2 | P1 checkpoint 干净，mapping 锁仍匹配 | 首次允许真实只读同步、同步状态 CLI、费用投影与追加纠正；portfolio import 后只能在原事务提交后触发 review sync | 固定 cutoff 下 `unsynced=0`；重复同步 `inserted=0`；同步失败不回滚 portfolio import |
| P3 | P2 对账完成，sidecar integrity 为 `ok` | 首次允许单笔、周度、月度 runner；串联同步、snapshot/context、episode、P2E-3/P2F facts-only 与 source replay | 真实 episode 有 facts-only 输出或明确 partial/blocked 原因；重复运行确定且可重试 |
| P4 | P3 runner service contract 稳定 | 首次允许本地 review API/Web/UI；允许“查看—补充决策—关联—纠正—保存”写入候选 sidecar | API、前端测试/build、localhost 浏览器流程、转义和路径/修订拒绝测试通过 |
| P5 | P4 checkpoint 干净，全部 targeted tests 通过 | 首次允许可关闭的进程内启动补偿、周期检查和 single/weekly/monthly 自动运行 | 并发/重试/故障测试、health、真实 smoke、全仓测试和最终候选回执通过 |

P1 禁止真实 sidecar 同步、runner、Web/API/UI 和自动运行；P2 禁止 runner、Web/UI 和
周期调度；P3 禁止 Web/UI 和周期调度；P4 禁止自动调度。只有对应 checkpoint 和验证
都通过后，下一个阶段的权限才生效。

## 4. Mapping provenance refresh

P1 必须先记录源库初始 SHA-256、`quick_check`、表结构和当前 mapping hashes，再执行：

1. 用 `doctor` 对正式 portfolio SQLite 做 `mode=ro` 扫描，重新生成
   `config/investment_review.portfolio.generated.json`；
2. 核对来源路径、`ledger_entries` 表、schema SHA-256、稳定 identity 和全部已确认字段
   语义；除已授权的旧 generated hash mismatch 外，任何漂移都停止；
3. 只更新 reviewed mapping 的 reviewer、真实审核时间、generated mapping SHA-256、
   schema manifest SHA-256、canonical reviewed-content SHA-256 和审计说明；
4. reviewer 记录为 `workspace_user`，不得把 Codex 写成用户姓名，也不得虚构身份；
5. 调用项目严格 mapping validator，并再次证明源库 SHA-256 未变。

固定字段语义如下：

- source 为 `portfolio.sqlite3/ledger_entries`；
- `record_id = account_id + "::" + external_id`；
- `occurred_at = event_date + event_time`；
- `created_at` 不是历史 `known_at`；缺失时回退到 `occurred_at` 并明确
  `known_at_fallback=true`；
- `BUY`/`SELL` 是交易；`DIVIDEND`/`CASH_FEE` 映射为 `OTHER`，同时保留原事件类型和
  `cash_amount`；
- `ts_code`、`quantity`、`price`、`gross_amount`、`cash_amount`、`fees`、
  `account_id` 按原义导入，币种为 `CNY`。

## 5. 手续费状态与追加纠正

每笔 BUY/SELL 的有效展示状态只能是：

- `actual`：来源字段明确存在且费用大于 0；
- `estimated`：`historical_median_rate_v1` 生成估算，并保存 method version、样本数、
  样本分组和计算 lineage；
- `unknown`：来源不满足 actual，且估算条件也不成立。

`historical_median_rate_v1` 先使用同一 `account_id + asset_type + side` 下已确认样本的
`fees/gross_amount` 中位数，样本不足再退化到 `asset_type + side`。有效样本少于 5、
成交额无效或品种无法识别时保持 `unknown`；估算金额四舍五入到 0.01 元。不拆税费、
不模拟最低佣金、不合并订单，也不声称估算等于正式交割费用。

来源费用为 0 或缺失时不能标为 `actual`。人工纠正必须追加一条带 reviewer、理由、
有效/知悉时间、前序 revision 和来源引用的不可变记录；不得 UPDATE 源事件、源费用或
旧修订。当前值只能从完整、无分叉且通过校验的 correction chain 投影。

## 6. CLI、API 与 UI 预期

### P2 CLI

- `review-sync` 支持 dry-run、apply 和重复 apply，报告 cutoff、source seen、sidecar seen、
  inserted、skipped、conflict 和 unsynced；
- `review-sync-status` 报告最后成功/失败、lag、mapping/schema 状态和候选 sidecar 路径；
- fee projection/correction 命令显示 `actual/estimated/unknown`、method version、样本数和
  append-only revision，不写回 portfolio。

### P3 runner CLI

`review-run --scope single|weekly|monthly`（或合同允许的等价稳定命令）返回机器可读
run receipt。receipt 必须逐步列出 sync、fee、snapshot/context、episode、P2E-3、P2F 和
source replay 的 `ready/partial/blocked/failed` 状态、artifact ID/hash、重试键与确切缺口。
重复执行不得漂移既有不可变产物。

### P4 API/UI

- GET 只通过稳定 service/query adapter 返回已校验的 review list、detail、timeline、
  context、evidence 和 health；HTTP handler 不直接拼 SQL、任意路径或未经验证的 artifact；
- POST 只接受有大小、类型、ID、双时间和 expected-parent 校验的 decision/link、fee
  correction 和 P2F correction，并写新的 sidecar 记录/修订；
- UI 明确显示来源、费用状态、snapshot 质量、decision 缺口、canonical readiness、同步
  lag 和 run failure，提供证据抽屉及“查看—补充—关联—纠正—保存”流程；
- 页面必须转义不可信文本，拒绝路径穿越、旧 revision 覆写和非法状态转换。

### P5 自动运行与 health

自动运行只能是可关闭、可测试的进程内 catch-up/周期检查，不安装 Windows 计划任务、
系统服务或开机项。任务使用确定的 single/weekly/monthly run key 去重；失败保留状态并可
安全重试，不能吞错，也不能回滚已提交的 portfolio 导入。health 同时显示 source/sidecar
计数、unsynced、最后成功/失败、费用状态与 review readiness。

## 7. Facts-only fallback

模型不是产品闭环的完成前提。没有配置模型、provider 不可用、响应失败或输出未通过
schema/时间/政策校验时：

1. 返回与输入 bundle/source replay 对应的**原样已验证 facts-only artifact**；
2. 单独记录 attempt/failure receipt，不把失败文本混入事实；
3. CLI/API/UI 显示 `facts_only` 及明确缺口或 blocker；
4. 不补造 interpretation、历史理由、alternative、置信度或 canonical readiness。

facts、interpretation、alternative explanations、uncertainty/missing evidence、当时可行的
alternative actions 和历史关联必须继续分区；缺一项时显示缺失状态。

## 8. 明确禁区

本阶段不授权 P2H Slice B，也不授权创建或更新 profile、PersonalPlaybook、
intervention/experiment、attempt/outcome。禁止心理/人格 diagnosis、行为 score、数值
confidence、买卖或仓位 advice、order execution、broker writes、broker credentials、
portfolio source DB writes、外部 provider、OS scheduler/service 和生产发布。

Product-completion API/UI/自动运行只面向本手册的交易复盘对象，不得借此开放、推进或
修改 P2H candidate、observation protocol 或后续对象。不得使用 future-known 数据，不得
隐藏 partial/blocked/failed，不得降低 P2E-3/P2F validator，不得覆盖 canonical artifact，
也不得把用户未提供的人类事实自动生成出来。

## 9. 阶段完成检查

每个阶段结束前必须：

1. 运行该阶段全部 targeted validator/tests，并记录精确结果；
2. 对照阶段 allowed/forbidden paths 审查 diff；
3. 重算正式源库 SHA-256，并确认未变；
4. 更新 checkpoint，显式列出 unknown、partial、blocker 和唯一下一安全动作；
5. 创建规定的 Git checkpoint，并在进入下一阶段前确认 tracked tree clean。

系统候选只有在五阶段 criteria、真实只读来源对账、全部测试和最终回执都通过后才可称为
`engineering_complete`/`data_ready`。这不等于 `human_context_complete`、
`production_released` 或真人产品验收；默认终点是本地 verified candidate branch。
