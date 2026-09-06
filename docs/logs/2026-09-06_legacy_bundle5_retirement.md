# 旧 Bundle 5 工具链退役

状态：本组 17 个文件的退役改造、验证及用户手动删除均已完成。开始于 2026-09-06，验证与物理删除核验完成于 2026-09-07（Asia/Shanghai）。

## 范围与依据

- 用户本轮要求：继续执行瘦身清理，并沿用将零散文件集中后手动删除的方式。
- 清理前提交：`bd57ff31ed57c141f306b8b95d3d102dd23040f7`。
- 工作树：`C:/Users/Q/.codex/worktrees/slim20260906/03_Investment_System`。
- 精确范围为 17 个文件：7 个旧生成／执行脚本、1 份专用规则和 9 个配套测试文件。
- 文件原始内容共 261,401 bytes；经 Git 换行归一化后为 260,947 bytes。两种哈希分别留存，移动不改变文件字节。
- 对当前受 Git 管理的文字文件核对完整路径、文件名和模块名，外部引用仅来自 retention manifest、路由退役检查和 Bundle 6 的历史命令说明；动态读取与完整回归另行验证。

## 精确文件清单

```text
config/r5_bundle5_pilot_gate_rules.yaml
scripts/build_r5_bundle5_benchmark_coverage_precheck.py
scripts/build_r5_bundle5_forecast_valuation_onboarding.py
scripts/build_r5_bundle5_market_peer_onboarding.py
scripts/build_r5_bundle5_official_disclosure_onboarding.py
scripts/build_r5_bundle5_real_input_inventory.py
scripts/run_r5_bundle5_real_registry_promotion.py
scripts/run_r5_bundle5_research_draft_quality_gate.py
tests/test_r5_bundle5_benchmark_coverage_precheck.py
tests/test_r5_bundle5_close.py
tests/test_r5_bundle5_forecast_valuation_onboarding.py
tests/test_r5_bundle5_market_peer_onboarding.py
tests/test_r5_bundle5_official_disclosure_onboarding.py
tests/test_r5_bundle5_real_input_inventory.py
tests/test_r5_bundle5_real_pilot_gate.py
tests/test_r5_bundle5_real_registry_promotion.py
tests/test_r5_bundle5_status_baseline.py
```

## 依赖和检查的去向

旧脚本主要把固定的英维克历史披露、市场数据、模型情景和运行结果转换为 Bundle 5 产物。上述配置只供该组使用；没有发现需要连同删除的独占模板。共享模板、研究校验器、注册写入组件以及所有证据和正式运行继续保留。

- 保留真实输入来源检查：将旧收尾测试中对保留输入的审核人与原始证据检查转入 `tests/test_reviewed_input_evidence_provenance.py`，同时核对原始文件的登记哈希。该测试直接读取受管理的已审核输入，不再导入旧生成器，也不将旧 workflow 设为默认入口。
- 文本原始快照的登记哈希对应 Git 保存的 LF 字节。现场确认市场 JSON 的 Windows 工作副本仅有 121 处 LF→CRLF 转换；测试在原始哈希不符时，只对文本文件核对其内容与 Git 版本仅差换行，再验证登记哈希。二进制证据仍按实际文件字节检查，原始证据未被重写。
- 共享功能继续由当前测试覆盖：`tests/test_structured_metric_unit_normalization.py`、`tests/test_tushare_adapter_contract.py`、`tests/test_validate_r5_reviewed_input_dropzone.py`、`tests/test_r5_bundle4_registry_promotion.py`、`tests/test_r5_bundle4_registry_idempotency.py`，以及当前研究包、预测、估值与人审契约检查。
- 该组原有 62 项测试随对应旧能力退役，其中 52 项原属默认套件、10 项原属历史兼容套件。清理前全部通过；源代码、专用测试与冻结结果仍可从清理前 Git 提交恢复。
- 路由检查移除已退役脚本的 CLI 存在性要求，并继续对全部已登记路径检查当前物理读取。历史保护测试允许已登记的读者退出，禁止新增旧路由读者或改变原有保护语义。
- Bundle 6 生成器的历史命令说明改为引用恢复提交，不再输出要求当前工作树运行已退役测试文件的命令。

## 验证记录

本轮日志、JUnit、依赖图和移动收据位于 `.codex_tmp/legacy_bundle5_slimming_20260906/`。

| 检查 | 结果 |
|---|---|
| 清理前 Bundle 5 专用测试 | 62 passed，9.42 秒 |
| 清理前当前研究离线重放 | 17 个产物，byte drift 0，无网络请求，无历史运行目录读取 |
| 移动和恢复哈希 | 17 个文件的移动前后原始 SHA-256、Git 归一化内容、恢复 blob 全部通过 |
| 当前依赖与共享功能回归 | 相关回归 30 passed；Research smoke 8 步通过；全部受管理文本扫描无现行代码引用；499 个 Python 文件语法检查通过 |
| 默认全套 | 2248 passed、2 skipped、88 deselected；593.37 秒 |
| 历史兼容全套 | 88 passed、2250 deselected；192.50 秒 |
| 清理前后当前研究产物 | 17 个产物 SHA-256 全部一致，无新增正式运行或指针变更 |
| 最终修改范围 | 精确 24 个路径：17 个原文件移出，5 个控制或记录文件更新，2 个文件新增；证据、账本、产品代码、当前运行与人审契约无改动 |

## 用户手动清理完成

待删文件夹：`C:/Users/Q/.codex/worktrees/slim20260906/03_Investment_System/.codex_tmp/manual_delete_legacy_bundle5_20260906/`。

2026-09-07 用户反馈已删除；现场核验 17 个原路径与待删副本均不存在，`scripts/`、`tests/`、`config/` 子目录已移除。当时剩余的说明和清单两份辅助记录已在第三轮集中到新待删目录；旧目录目前为空，可手动删除。另一份最新恢复与删除收据保存在上述本轮日志目录中。

精确路径、Git blob、SHA-256 和恢复提交另见 canonical manifest 的 `completed_manual_deletions`。`AGENTS.md` 第 60–61 行要求多个文件或目录的删除由用户手动执行；本轮只移动文件，不自动删除目录。

完成项：`bundle5_manual_delete`；actor=user；17 份文件的物理删除已核验，Git 恢复 blob 仍全部可用。canonical manifest 的完成索引保留删除核验依据和恢复哈希；后续索引整理见 [6–10 收尾记录](2026-09-07_legacy_bundle6_10_retirement.md)。发布仍待决定，未推送或合并。
