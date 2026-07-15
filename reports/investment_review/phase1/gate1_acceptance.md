# 投资复盘 Phase 1 现场验收

## 结论

`status: accepted_with_todos`

Gate 1 的数据契约、只读来源扫描、人工 mapping 审核锁、真实数据 dry-run、正式导入、
三次幂等复跑、完整性与显式 event-run 追溯均已完成。当前工作快照没有未解决的
critical / high 问题；独立终审已确认当前四次 run 快照。历史知悉时间、
决策上下文、raw payload 的保守冲突边界和 Gate 2 范围仍以显式 TODO 保留。

本次仅完成 Gate 1。未进入 Trade Episode、组合快照重构、分析引擎、AI 复盘、Web UI、P2 或交易执行。

## 补丁与基线

- 补丁：`investment_review_phase1_patch_a12cbb8.zip`
- 外层 SHA-256：`2E08B87F60C70F232D31969CE397239DFDB1D3698DFF71539603A4C8E5BFED2A`
- 包内校验：23 / 23 通过
- 基线提交：`a12cbb8a9b90e348c117f8eff3087a5a89c5c1b3`
- 原补丁范围：新增 14 个文件，0 删除
- 现场策略：保留当前 worktree 中更晚的 portfolio 改动，仅对新增复盘模块做兼容适配

## 正式来源

- 正式台账：`C:\Projects\03_Investment_System\data\db\portfolio.sqlite3`
- 来源表：`ledger_entries`
- 行数：961
- 分布：BUY 489、SELL 404、DIVIDEND 39、CASH_FEE 29
- doctor 模式：SQLite `mode=ro`
- doctor 结果：`ledger_entries` 为首选候选，`trade_score=5/5`
- schema manifest：`reports/investment_review/phase1/schema_manifest.json`

源库在 doctor、dry-run、四次正式导入前后的 SHA-256 均为：

`B625D58AC54514A77620269F6D3CEB7214BA1446A2697257522D11B6F493645E`

大小均为 757760 bytes，mtime 均为 `2026-07-14T19:08:22.4373993Z`，因此 `source_unchanged=true`。

## Mapping 审核与适配

机器建议保存在 `config/investment_review.portfolio.generated.json`，正式导入使用人工审核后的 `config/investment_review.portfolio.reviewed.json`。
generated mapping 只能 dry-run，formal import 已实测拒绝。reviewed mapping 同时锁定 schema
manifest、generated mapping 与完整审核文档：

- reviewed mapping 文件 SHA-256：`9db2934e2e965a0c7b38c1008bf50c6273ab393a7239b5e7b1571625f6d1a562`
- `review.mapping_content_sha256`：`a3a89c8c728ab37b08f32fc394120dd34318f037f00f4be968a916909b69cb46`
- hash 范围：完整 reviewed mapping 文档，仅排除自引用字段 `review.mapping_content_sha256`
- schema manifest SHA-256：`a4e23bf8d6bfe8b0cd15d2241e65fca1fe0305b7ffb3495fd57abaee9c4b34f0`
- generated mapping SHA-256：`a707064ba00cc8795e7e6164b5b7240b4c86a55f7a9aaa4433af3b26cd498b9e`
- `ledger_entries` table schema SHA-256：`26a979d503a276afa0e42957c90878eb479ab63bcd7d59374366525c959c79bf`

| canonical field | reviewed source |
|---|---|
| `record_id` | `account_id + "::" + external_id` |
| `occurred_at` | `event_date + event_time` |
| `known_at` | `null`，由 importer 回退到 `occurred_at` |
| `symbol` | `ts_code` |
| `side` | `event_type` |
| `quantity` | `quantity` |
| `price` | `price` |
| `gross_amount` | `gross_amount` |
| `cash_amount` | `cash_amount` |
| `event_type` | `event_type` |

`record_id` 使用账户内稳定的 `external_id`，不会把内容型 `dedupe_key` 当成源记录身份；
`dedupe_key` 仍保留在 raw payload 中用于内容漂移检查。DIVIDEND / CASH_FEE 保留真实
`event_type`，仅将方向映射为 `OTHER`，并把 6465.15 / 369.49 的来源现金金额写入独立
`cash_amount`，没有误标成 fill 或混入 `gross_amount`。

formal SQLite import 不只校验文件哈希，还要求实际来源与 `source.uri`、
`generated_from.database` 指向同一文件，并锁定 `sqlite.table`、`generated_from.table`
与实时表结构 SHA-256。CSV import 则要求稳定的 `source.identity_key` 与必填
`record_id`，复制或重命名 CSV 不会因此创建新的 source identity。

正式台账的 `created_at` 全部是 2026-07-14 的重建时间，不能当作历史真实知悉时间。reviewed mapping 因此不映射该字段；961 条事件均保存 `known_at_fallback=true`，明确表示当前 `known_at=occurred_at` 是受限回退，不是已验证的历史决策时间。

## Dry-run 与导入

- dry-run：`status=DRY_RUN`，`seen=961`
- 代表性预览：BUY、SELL、DIVIDEND、CASH_FEE 各有可见样本，事件时间、代码、方向、数量、价格、成交额、现金额和费用与源表一致
- 首次导入：`seen=961, inserted=961, skipped=0`
- 首次 run：`run_17f51358aee04c2388e204c7cf39d69d`
- 幂等复跑：`seen=961, inserted=0, skipped=961`
- 第二次 run：`run_343100a5b35e415bb2bbe3292fb122e4`
- 审核锁修复后复跑：`seen=961, inserted=0, skipped=961`
- 第三次 run：`run_e781fadf03714777a870cfdca1a73990`
- 来源路径 / 表 / schema 锁修复后复跑：`seen=961, inserted=0, skipped=961`
- 第四次 run：`run_d4aeac0e8c82487ebc5fcac6d312deca`
- `source_config_versions=3`：各次审核锁版本均保留，不静默覆盖

## 完整性与来源追溯

- schema / user version：2 / 2
- SQLite `application_id`：`1230132823`（`0x49525657`，`IRVW`）
- source / review `quick_check`：ok / ok
- `integrity_check=ok`
- foreign-key issues：0
- trade events：961
- ingest runs / explicit run-event links：4 / 3844
- distinct event IDs：961
- distinct source record IDs：961
- missing source record / raw payload / SHA-256：0 / 0 / 0
- orphan source：0
- `known_at < occurred_at`：0
- 缺失首次 INSERTED run link：0
- run-event payload SHA 不一致：0
- `first_ingest_run_id` 不一致：0

每条事件均保留 source、稳定 source record、原始 payload、payload SHA-256、
`first_ingest_run_id`，并通过 `ingest_run_events` 显式关联四次导入的 INSERTED / SKIPPED
结果。event-run 追溯问题已解决，不再是 TODO。

把正式 portfolio SQLite 误传给复盘 `--db` 的安全检查实测以 exit code 2 拒绝，
源库没有新增 review schema、WAL 或 SHM；非 review 非空数据库也会在初始化前被拒绝。
legacy v1 旁路库同样不会自动升级，因为旧 schema 无法重建完整 event-run lineage；
正确路径是新建 v2 sidecar 并从只读来源重新导入。

## 验证

- conda 环境：`C:\Projects\03_Investment_System\.conda\investment-system`
- `python -m compileall -q src tests`：通过
- `python -m unittest tests.test_investment_review_phase1 -v`：14 / 14 通过
- `git diff --check`：通过
- `scripts/start_investment_review.ps1 status`：通过
- 启动脚本已兼容 linked worktree，会优先解析主工作树 conda 环境

## 质量与未决项

质量结论见 `quality_gate_report.md`，结构化问题见 `quality_issues.csv`。当前 outcome 为 `accepted_with_todos`：

1. `payload_sha256` 基于完整 `source_row`；台账仅技术字段重建也可能产生保守的安全性假冲突，应人工核查，不能自动放行。
2. 当前所有 source 默认采用全量 snapshot removal；月度增量 CSV 必须等待显式 `snapshot_mode=full|append` 契约。
3. 历史真实 `known_at` 缺失，961 条均保持 fallback；后续需增加 `known_at_quality` / precision，不得声称真实当时知悉边界。
4. 决策笔记为 0，不得反推或编造历史动机；后续只录入用户确认的上下文。
5. Gate 2 的精确 adapter / Episode / snapshot 未启动；启用 `position_snapshot_items` 前必须处理 nullable `market` 复合主键。

当前结构化结果为 open critical=0、open high=0、resolved high=16、accepted medium
TODO=4、accepted low TODO=1；独立终审已确认本验收可以按上述 TODO 边界关闭。

## 边界

- 没有删除任何文件或目录。
- 没有修改正式 portfolio SQLite。
- 没有改动 `src/portfolio` 中用户现有实现。
- 没有生成买入、卖出、持有、仓位或收益保证建议。
- 没有把缺失的决策上下文、心理动机或真实知悉时间补造为事实。
