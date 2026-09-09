# Bundle 6–10 旧工具链退役与收尾

状态：本组代码退役、依赖解耦、恢复验证、全套回归及用户手动物理删除均已完成。本轮开始于 2026-09-07（Asia/Shanghai）。

## 范围与依据

- 用户要求执行 6–10 系列瘦身及收尾，沿用集中到待删文件夹后由用户手动删除的方式。
- 清理前提交：`4121360c4583a95a9d889ee4604bf0893f92a294`；工作树：`C:/Users/Q/.codex/worktrees/slim20260906/03_Investment_System`。
- 本组共 56 个文件：33 个旧脚本、21 个专用测试、1 份固定样例模板、1 份历史补丁 ZIP。
- 原始内容共 582,914 bytes；Git 换行归一化内容共 581,587 bytes。文件逐项记录两种哈希、Git blob 和固定恢复提交。
- 默认研究、Portfolio、Investment Review、账本、证据、现行运行、人审契约与当前指针保持原状。

## 退役与保留的边界

Bundle 6 的 Reader 基线、补救与收尾工具；Bundle 7 的冻结收尾测试；Bundle 8／8b 的计划和收尾工具；8r 的固定试点构建与重启入口；9／9r 的固定模型生成与阶段状态入口；10／10r 的旧构建、状态同步和阶段收尾入口随其专用测试一并退役。

保留仍可独立使用的共享能力及回归：

- `src/research/r5_analysis_engine.py`、`src/research/r5_evidence_coverage.py`，对应 Bundle 8 配置和 18 项分析、证据覆盖测试。
- `src/research/r5_bundle9r_contracts.py` 及模型契约、生成锁与代际绑定测试；模型算术、重复计入、管理层口径、不充分一致预期、过期输入仍受检查。
- Reader v4／v5 writer、payload、traceability、generation 与质量门，共享配置及相关测试继续保留。
- `scripts/run_r5_bundle10_cross_industry_writer_regression.py` 是跨公司合成回归工具；`scripts/validate_r5_bundle10r_human_review.py` 独立核验人工审阅与输入哈希。两者有实际通用校验行为，保留对应正反例测试。
- 8r 适配器测试和来源 fixture、`config/r5_bundle8r_generation_inputs.yaml` 继续服务独立证据生成锁与采集组件。
- 当前最终报告人审继续由 `tests/test_r5_final_report_review_semantics.py` 检查真实审阅者、报告哈希失效、旧人审事件复用和自动检查失败时的边界。

旧 8b 收尾检查中的 46 份证据文件存在性，提升为 `tests/test_reviewed_input_evidence_provenance.py` 对全部 113 条现存 evidence manifest 记录的唯一 ID 与实体路径检查。原有 22 条已审核输入的来源、审阅与原始哈希检查继续保留。历史 peer 数值、事件日期和阶段状态属于已冻结结果，连同原测试可从 Git 恢复，不再作为当前运行默认约束。

预审另发现 5 条早期 Tushare CSV 登记哈希与现有内容不符，原始或仅换行归一化后均不匹配；它们在清理前已存在，本轮未修改证据或登记哈希。这 5 个文件均与清理前 Git 内容一致；详情见 `.codex_tmp/legacy_bundle6_10_slimming_20260907/preexisting_evidence_hash_audit.json`。此问题不影响路径检查通过，也不代表全部 113 条证据已通过内容哈希审计。

## 完成索引与恢复保护

前两轮用户已删除的 22 条记录从 `manual_delete_candidates` 迁入 `completed_manual_deletions`，状态为 `DELETED_BY_USER`，保留全部恢复提交、blob、字节数和 SHA-256。现场再次核验其原路径和两处旧待删副本均不存在。

待删与已完成索引均参与当前引用扫描、模块导入检查和 Git 恢复内容验证；已完成记录另外禁止原路径重新出现，不能变成无人维护的归档。原有 476 个退役路径、保护目录、人审与账本不变量保持不变。

旧两处待删文件夹仅余的 4 份辅助说明／清单合并到本轮待删文件夹的 `previous_cleanup_receipts/`，另存移动前哈希。历轮验证日志和原外部收据保留。

## 验证记录

验证与移动收据：`.codex_tmp/legacy_bundle6_10_slimming_20260907/`。

| 检查 | 结果 |
|---|---|
| 清理前 38 个相关测试文件 | 145 passed，18.03 秒 |
| 随旧阶段能力退役的测试 | 53 项（原默认 24、历史兼容 29）；全部在清理前通过 |
| 清理前当前研究离线重放 | 17 个产物；byte drift 0；无网络访问、无历史运行目录读取 |
| 移动、恢复哈希及依赖检查 | 56 个旧文件及 4 份旧辅助记录移动哈希一致；78 条待删／完成记录均可按登记哈希从 Git 恢复；无现行物理调用 |
| 共享能力与当前保护回归 | 198 passed；最终清单回归 17 passed；445 个受管理 Python 文件语法检查通过 |
| Research smoke | 8 步全部通过，含当前状态、来源路由、保护检查及研究包契约 |
| 默认全套 | 2232 passed、2 skipped、59 deselected；579.25 秒 |
| 历史兼容全套 | 59 passed、2234 deselected；187.34 秒 |
| 当前研究产物前后比较 | 17 个产物的 SHA-256 全部一致；没有新建正式运行或改变指针 |

## 精确移出清单

```text
r5_after_patch12_patch_package.zip
scripts/build_r5_bundle10_human_review_handoff.py
scripts/build_r5_bundle10_reader_pack.py
scripts/build_r5_bundle10r_human_review_handoff.py
scripts/build_r5_bundle10r_reader_generation_lock.py
scripts/build_r5_bundle10r_reader_pack.py
scripts/build_r5_bundle6_close_readout.py
scripts/build_r5_bundle6_human_review_handoff.py
scripts/build_r5_bundle6_reader_baseline.py
scripts/build_r5_bundle6_research_remediation.py
scripts/build_r5_bundle8_research_depth_plan.py
scripts/build_r5_bundle8r_pilot_artifacts.py
scripts/build_r5_bundle9_forecast.py
scripts/build_r5_bundle9_valuation.py
scripts/build_r5_bundle9r_forecast_valuation.py
scripts/build_r5_bundle9r_model_generation_lock.py
scripts/check_r5_bundle10r_model_freshness.py
scripts/close_r5_bundle8b.py
scripts/close_r5_bundle9.py
scripts/finalize_r5_bundle10_after_human_review.py
scripts/run_r5_bundle10r_reader_quality_gate.py
scripts/run_r5_bundle8_research_depth_gate.py
scripts/run_r5_bundle9r_model_quality_gate.py
scripts/start_r5_bundle10r_reader_rebuild.py
scripts/start_r5_bundle8r_forward_requalification.py
scripts/start_r5_bundle9r_forecast_valuation_rebuild.py
scripts/sync_r5_bundle10_external_review_pending.py
scripts/validate_r5_bundle10_close.py
scripts/validate_r5_bundle10_human_review_submission.py
scripts/validate_r5_bundle10r_close.py
scripts/validate_r5_bundle10r_generation_binding.py
scripts/validate_r5_bundle8b_close.py
scripts/validate_r5_bundle9_close.py
scripts/validate_r5_bundle9r_generation_binding.py
templates/r5_bundle8r_research_request.example.yaml
tests/test_bundle8r_forward_requalification.py
tests/test_r5_bundle10_close.py
tests/test_r5_bundle10_human_review_finalize.py
tests/test_r5_bundle10_human_review_handoff.py
tests/test_r5_bundle10_human_review_submission.py
tests/test_r5_bundle10_state_sync.py
tests/test_r5_bundle10r_forward_state.py
tests/test_r5_bundle10r_model_freshness.py
tests/test_r5_bundle10r_v5_artifacts.py
tests/test_r5_bundle6_close.py
tests/test_r5_bundle6_human_review_handoff.py
tests/test_r5_bundle6_reader_baseline.py
tests/test_r5_bundle6_research_remediation.py
tests/test_r5_bundle7_close.py
tests/test_r5_bundle8_plan.py
tests/test_r5_bundle8b_close.py
tests/test_r5_bundle8b_local_close.py
tests/test_r5_bundle9_close.py
tests/test_r5_bundle9_forecast.py
tests/test_r5_bundle9_valuation.py
tests/test_r5_bundle9r_forward_state.py
```

## 用户删除核验（2026-09-07）

用户反馈“已删除”后，现场核验本组 56 份旧文件的原路径和待删副本均不存在，前两轮移入的 4 份辅助记录也已删除。待删目录仅剩本轮 `README.md` 和 `cleanup_manifest.json` 两份辅助记录，可保留或手动删除。

本组 56 条记录已转入 `completed_manual_deletions`，保留恢复提交、blob、字节数、SHA-256 及引用证据，并登记 `deletion_actor=user`。当前 `manual_delete_candidates` 为空，完成索引共 78 条；其他 manifest 字段保持不变。

删除后的完成索引与保护检查：Doc drift 通过，相关回归 32 passed（14.31 秒）；全部 78 条完成记录的 Git 恢复内容校验通过。此前完整回归结果仍作为代码版本的验证依据；本次只调整清单与删除记录，没有改动运行代码或证据。

## 其他手动清理与发布

原待删文件夹：`C:/Users/Q/.codex/worktrees/slim20260906/03_Investment_System/.codex_tmp/manual_delete_legacy_bundle6_10_20260907/`。本组旧文件已由用户物理删除；目录中剩余两份辅助记录，其他工作树与 Git 登记尚待用户手动收尾。依据 `AGENTS.md` 第 60–61 行：“Do not remove directories automatically. If the requested scope contains multiple files or any directory, stop and ask the user to perform the deletion manually.”

旧只读工作树 `C:/Users/Q/.codex/worktrees/c02d/03_Investment_System` 已复核为 Git 干净、无忽略文件，1,927 个文件共 98,404,478 bytes（约 93.85 MiB）。本轮未观察到命令行指向该路径的其他进程；这不证明旧任务以后不会再使用它。用户确认不再需要旧工作树时，可手动执行：

```powershell
git -C C:/Projects/03_Investment_System worktree remove C:/Users/Q/.codex/worktrees/c02d/03_Investment_System
git -C C:/Projects/03_Investment_System worktree prune --verbose
```

其中 prune 用于清除用户此前已删除的 5646、8632、bc43、df8c 四处失效登记。本轮只核验目录不存在和可清理登记，不自动删除 Git 管理目录。旧两处待删目录可能留为空目录，可与上述目录一起手动收尾。

本轮保存本地提交；未推送或合并，原主工作树的既有未跟踪图片未改动。发布时须保留本分支前序提交的可达性，尤其是 `4121360c4583a95a9d889ee4604bf0893f92a294` 与 `bd57ff31ed57c141f306b8b95d3d102dd23040f7`；仅复制最终文件或丢失恢复提交会使 Git 恢复校验失败。

| 剩余事项 | owner | severity | 下一步 |
|---|---|---|---|
| 旧 c02d 工作树及四处失效登记 | user | low | 不再使用时执行上述手动清理 |
| 瘦身分支发布 | user | medium | 确认发布范围后再推送或合入主线 |
| 5 条既有 Tushare CSV 哈希差异 | codex | medium | 独立核对源版本及登记依据，不在清理中重写原证据 |
