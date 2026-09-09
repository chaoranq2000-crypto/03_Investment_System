# 测试夹具收尾与 Bundle 4 外壳合并

状态：实现、依赖解耦、文件隔离、恢复验证及全套回归均已完成；实际文件删除待用户执行。

## 范围与恢复依据

用户于 2026-09-09 要求执行上一轮建议的收尾。工作树为 `C:/Users/Q/.codex/worktrees/slim20260906/03_Investment_System`，修改前提交为 `412e1d985454f374e9e0127523b33b44ff89675a`。

本轮移出下列两个已无生产调用者的 fixture smoke 文件，原始及 Git 内容均为 21,665 bytes。需要保留的验证迁入已有测试，所以该数字是移出文件总量，不是净代码节省量。

```text
scripts/run_r5_bundle4_reviewed_input_smoke.py
tests/test_r5_bundle4_reviewed_input_smoke.py
```

每项在 canonical retention manifest 保留固定恢复提交、Git blob、字节数、SHA-256 与当前引用依据。原有 476 条退役路径、100 条用户已删除记录、保护范围、历史快照和不变量保持不变。本轮 2 条仅进入 `manual_delete_candidates`，尚未标记物理删除完成。

## 实现与覆盖边界

`tests/conftest.py` 移除 Night03 专用夹具、读取器、常量及其独占 import，共 104 个完整源码行、4,487 bytes（不计空白分隔行）。它们在当前测试中没有消费者；不将删除闲置代码计作运行耗时收益。仍在使用的 `HISTORICAL_BASELINE` 保留。

通用 `historical_blob_bytes` 与回放测试的历史对象读取复用已有 `GIT_HISTORY`；取消重复字节缓存，并在回放树恢复检查前批量预取精确的 16 个固定对象。完整 commit、字面路径、类型、OID、长度和 SHA-256 继续校验。共享 HistoricalGit 与临时物化夹具没有变更；8 个回放测试的 93 条断言 AST 保持不变，真实两次 materialize、源隔离、validator、完整产物树及幂等检查继续执行。生产回放脚本不依赖测试 helper，也未在本轮修改。

Bundle 4 保留 promoter、registry IO、dry-run builder 及原 fixture 文件。独有的 mixed 状态完整链、无网络、当前 pointer／产物保护、仓库状态向量不变和跨临时根重复运行检查合并到 `tests/test_r5_bundle4_post_promotion_dry_run.py`。新检查直接消费底层返回值，避免旧 smoke 汇总字段硬编码 false 或对已退役占位路径做 None→None 比较。原 CLI JSON 包装及其独立入口随旧文件退役。

旧 smoke 的 8 项测试逐项映射到新增或现存核心检查，详见证据目录中的 `coverage_migration.json`。新增 mixed 检查 1 项和六场景管线检查 6 项，原核心测试保留，因此默认测试总数比基线净少 1 项。旧 `empty_or_pending` 分支实际只构造空 dropzone；真正 pending 输入仍由原 `tests/test_r5_reviewed_input_registry_promotion.py` 独立覆盖。

历史合同和文档归属纠正覆盖四公司回归合同、归属矩阵、两份 17R 链说明，以及报告 profile 的同一条过期可调用说明。它们明确区分现有 Bundle 11–13 能力与已退役的 14–17 链；四公司案例、历史 JSON／阈值／字段、17R 的冻结结果及当前最终报告人审条件保持。当前状态仍由 canonical pointer 和 workflow kernel 决定。

## 验证记录

证据目录：`.codex_tmp/test_fixture_bundle4_slimming_20260909/`。

| 检查 | 结果 |
|---|---|
| 修改前相关测试 | 75 passed，36.62 秒，含旧 smoke 8 项 |
| 修改前当前研究离线重放 | 17 个产物，byte drift 0，无网络或历史运行目录读取 |
| 历史读取定向验证 | 40 passed，15.38 秒；与 75 项基线不是同组计时，不混比 |
| Bundle 4 核心与既有 pending 验证 | 31 passed，6.68 秒 |
| 清单、路由、完成语义与策略保护 | 48 passed，16.37 秒 |
| 文件隔离与恢复 | 2 个原路径均移出，副本长度／SHA-256 一致；102 条待删／完成记录的恢复完整性检查通过 |
| Python 语法 | 427 个受管理文件通过 |
| Research smoke | 8 步全部通过 |
| 默认全套 | 2233 passed、2 skipped、59 deselected；548.47 秒 |
| 历史兼容全套 | 59 passed、2235 deselected；26.84 秒 |
| 当前研究产物前后比较 | 17 个产物的 SHA-256 全部一致 |

独立审查确认历史读取身份／哈希边界、8 个回放测试的断言及 B4 原子性／幂等／离线／当前产物保护均保留。所有运行和测试代码在完整回归前冻结；之后仅补充本记录。按 Git diff 的 Python 文件统计，新增 132 行、删除 770 行，净减少 638 行；计入新增审计记录后，受管理文件净减少 1 个。

当前研究数据、原始证据、已审核输入、正式 Portfolio 数据库、Investment Review、当前运行与指针不在本轮修改范围内。没有删除目录、变更工作树登记、推送或合并。

## 手动删除与剩余事项

待删目录：`C:/Users/Q/.codex/worktrees/slim20260906/03_Investment_System/.codex_tmp/manual_delete_test_fixture_bundle4_20260909/`。该目录保存两份旧文件及 README／恢复收据；证据目录另有收据副本。

`AGENTS.md` 第 60–61 行要求："Do not remove directories automatically. If the requested scope contains multiple files or any directory, stop and ask the user to perform the deletion manually." 因此文件仅移入隔离目录，用户删除后再核验并更新完成记录。

本轮只保存本地提交。后续发布须保留前序提交及恢复对象的可达性。

| 剩余事项 | owner | severity | 下一步 |
|---|---|---|---|
| 本轮 2 个旧文件的物理删除 | user | low | 手动删除本轮待删目录后核验 |
| 瘦身分支发布 | user | medium | 确认发布范围后推送或合入主线，并保留恢复提交 |
