# 2026-09-09 Tushare 快照哈希修订

本轮完成 2026-07-01 的 stock_basic、income、fina_indicator、cashflow、balancesheet 五条 Tushare 证据元数据修订。`evidence_manifest.csv` 仅修改五行的 `file_hash` 和 `content_hash`，共十个单元格；保留 evidence_id、来源、日期、业务字段和审核状态。完整旧收据、新哈希、Git 来源和 CSV 内容比较见 `data/processed/logs/2026-09-09_tushare_hash_reconciliation.json`。本轮没有重新下载或刷新财务数据。

## 前置发布状态

[PR #11](https://github.com/chaoranq2000-crypto/03_Investment_System/pull/11) 已通过 push/PR CI 和历史兼容检查，于北京时间 2026-09-09 20:28 合并为 `60f8b6e65304f7c74769550760baef67c30b2f7d`，完整保留原有十一个提交。本修订基于被该合并保留的 `37e49a519342efb6fbce74c4ac7c90d04dd381ee`，在独立工作树中验证；发布状态以 `codex/tushare-evidence-hash-reconcile-20260909` 的 Git/PR 记录及对应提交的 CI 结果为准。

原主目录仍为 `9acee9c`；同步涉及 578 个文件删除，按 AGENTS 的批量删除边界仍由用户手工完成，本轮未同步主目录。

## 根因与修订范围

五份原始 CSV 自 `e9524fd9a2ef78a519858649331639e260b7064e`（2026-07-01）首次提交后，Git 内容未改变。`c453b56aa30c6cc02646d4b930b4926c4da594cd`（2026-07-02）迁移时登记的完整哈希对应 CRLF 字节表示；`514ca09`（2026-07-07）引入显式 CSV 的 LF checkout 规则。对当前 CSV 及五份 processed Markdown 仅在内存中执行 LF→CRLF，即可逐项精确复现全部十个旧收据。CSV 的表头、字段值和行顺序完全一致。

本次将登记哈希修正为当前稳定 LF 文件的精确字节 SHA-256，并保留旧 CRLF 收据。原有 429 个已跟踪 raw/processed 文件与 `.gitattributes` 均未改变。新回归将“十个单元格变更”限定为本次修订快照，不冻结日后可合法更新的 review_status、notes 等元数据。

历史 replay 曾把当前整张 manifest 当作固定哈希输入。现将整表 anchor 和证据选行统一改为读取既有冻结基线 `f60f220ae252262a537c612ce193fc779901984b` 的 manifest；仍检查 Git OID、字节数和 SHA-256。冻结对象为 `8746bf3c66ebab3b3ad01f09458d03410d1a0597`，112378 字节，SHA-256 为 `34568fb9f31dc84c16e4b086b751a81ef8770591086c59a901ea7107510175ae`。原预期哈希、anchor 顺序和历史产物收据均保持。

## 验证

使用 `C:\Projects\03_Investment_System\.conda\investment-system\python.exe -B`：

| 检查 | 结果 |
|---|---|
| Manifest validator：113 条记录的结构与物理路径 | 通过，0 issue；这不等于全表 content_hash 已统一校验 |
| 本次五条证据 | 十个实际哈希匹配；十个旧 CRLF 收据可复现；CSV 值不变 |
| 证据、历史 replay、policy refresh、P1、活动路由、generation 和 smoke 相关测试 | 92 passed；包含显式启用的 legacy_compatibility 测试 |
| 新测试移除对可演进业务元数据的冻结后复验 | 该文件 6 passed；未重复计为额外独立覆盖 |
| 当前 policy refresh | 原有 17 件产物未变；两个新输出各 17 件，均与当前产物逐字节一致 |
| 历史 replay | 16 件产物、132529 字节，全部匹配原冻结收据，byte drift=0 |
| 原有 raw/processed 文件 | 429 件逐一比对，byte drift=0 |

首次测试尝试得到 74 passed、2 failed、16 errors，原因是测试临时目录放在仓内触发输出路径保护、TMP/TEMP 与 basetemp 不在同一目录树，以及 Windows 深路径限制。复跑使用系统 TEMP 下新的短唯一目录；没有修改输出保护或旧测试断言，也没有清理既有目录。首次与复跑日志、JUnit、完整命令及逐文件核验结果均保留在 `.codex_tmp/tushare_hash_reconciliation_20260909/`，主核验文件为 `scope_and_replay_verification.json`。

## 范围外待办

`market_data_tushare_probe_20260701_8bbf20` 的 processed table 另有可能由 CRLF/LF 解释的 `content_hash` 口径差异，未纳入本次五条 CSV 修订，也未改变该记录。Owner：`codex`；severity：`medium`；status：`open`；下一步：核对该 probe 的初始登记来源与 content_hash 口径后，再决定是否修订。该项不阻断本次五条证据的元数据修复。
