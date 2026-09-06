# Research 运行依赖瘦身记录

状态：两轮瘦身改造、验证及目标文件的用户手动删除完成。第一轮 5 份旧配置和 4 个旧工作树目录、第二轮 17 份 Bundle 5 文件均已核验缺失，见专项记录。共享 R5 能力继续保留。

## 范围与基线

- 基线：`457c7ee0ed3db7565320709f0b8b2cdeedf05aff`。
- 分支：`codex/research-runtime-slimming-20260906`。
- 工作树：`C:/Users/Q/.codex/worktrees/slim20260906/03_Investment_System`。
- 本轮使用 diagnostic 方式核对现有 Research 运行，没有创建新的正式研究运行。
- 当前运行仍由 `config/r5_readout_canonical_index.yaml.current_runs` 选择。
- 原始证据、正式研究运行、Portfolio/Review 产品代码、20 个 Review 合同、个人章程及 `C-HUMAN-005` 均不在修改范围。

## 已实施的收缩

1. 将 89 项只核对历史结果的检查标记为 `legacy_compatibility`。包含当前算法调用的混合测试文件只标记对应历史函数，当前功能回归保留在默认套件。
2. 手动兼容工作流按 marker 收集全部历史检查，包含原先保留的重放；没有删除测试用例。
3. 同一路径的 retention manifest 升为 v2，只保留当前保护、476 个已退役路径、现存引用、路由边界、恢复指针和本轮手动清理候选。
4. 两轮历史清理的完整 v1 收据固定在上述基线提交；历史检查从 Git 读取并校验，不再把过去的修改范围当作当前工作区限制。
5. Research smoke 从 current-run pointer 读取所有当前 state，临时源路由证明写入 `.codex_tmp/`，不覆盖 tracked 质量快照。

首次工程提交 `0ce7806` 中，按 Git LF 字节计算，治理清单从 749,985 bytes 缩减至 64,091 bytes，下降 91.45%。原来被隔离的 89 项检查在基线中合计耗时约 170.19 秒。

## 工程改造验证证据（移动旧配置前）

详细命令输出、JUnit XML、调用/文件读写轨迹位于本工作树的 `.codex_tmp/runtime_slimming_20260906/`，不提交生成日志。

| 检查 | 结果 |
|---|---|
| 修改前默认全套 | 2373 passed、2 skipped、8 deselected；770.50 秒 |
| 文档、current pointer、state | 通过；最终 Research smoke 的 8 个步骤全部通过 |
| 数据源路由及 adapter import | 17 项通过，0 阻断；没有发起网络请求 |
| 英维克独立离线重放 | 17 个产物，byte drift 0，未读取历史 workflow 目录 |
| 修改后默认全套 | 2299 passed、2 skipped、98 deselected；596.23 秒，较基线减少 174.27 秒（22.62%） |
| 历史兼容全套 | 最终 98 passed、2301 deselected；276.30 秒 |
| 改造前后研究产物比较 | 独立临时目录中的 17 个产物 SHA-256 全部一致，byte drift 0 |
| 最终变更范围与本地提交 | 精确 31 文件，无文件删除；暂存后相关回归 49 passed；本地提交以 Git 历史为准 |

测试耗时是同机、同一 Conda 环境的单次前后测量，缓存和机器负载会影响绝对耗时。

## 已由用户删除的 5 份旧配置

按用户“将其它需要清理的零散文件放入一个文件夹”的要求，以下 5 份配置先从当前工作树逐个移入同一待删文件夹，保留原 `config/` 结构，移动前后的长度和 SHA-256 全部一致，合计 34,765 bytes。用户随后反馈已删除；2026-09-06 现场核对原路径和待删副本均不存在，五文件清理完成。

待删文件夹：`C:/Users/Q/.codex/worktrees/slim20260906/03_Investment_System/.codex_tmp/manual_delete_research_runtime_20260906/`。该文件夹目前只剩 `README.md` 与 `cleanup_manifest.json` 两份辅助文件，用户可一并手动删除。原配置内容已不存在。

以下路径为移动前的原始相对路径；此次未移动旧主目录或其他工作树中的同名文件。

```text
config/r5_bundle3_expected_artifacts.yaml
config/r5_bundle4_expected_artifacts.yaml
config/r5_bundle5_expected_artifacts.yaml
config/r5_patch_1_12_expected_artifacts.yaml
config/r5_patch_49_55_expected_artifacts.yaml
```

精确路径、原 blob、SHA-256 和恢复提交仍保留在 canonical manifest 的 `manual_delete_candidates`；恢复提交为 `457c7ee0ed3db7565320709f0b8b2cdeedf05aff`。本地移动收据另外保存在 `.codex_tmp/runtime_slimming_20260906/quarantine_receipt.json`，删除待删文件夹不会删除这份收据。

同步移除 canonical manifest 中以这 5 份配置为来源的 5 条现存引用记录（共 64 条历史引用关系），保留全部退役登记、保护规则、待删候选和恢复信息。首次移动后检查发现这些来源已经缺失，修正的是清单内容，未放宽验证器。

移动后验证：Research smoke 的 8 个步骤全部通过；治理清单与相关历史配置回归 59 passed（143.71 秒）；5 个原路径缺失、待删内容哈希、Git 恢复字节与精确变更范围全部通过。当前清单为 59,229 Git LF bytes。本次只记录 5 个原路径移出和清单、日志两项更新；未修改验证器、测试或产品代码。

完成项：`manual_candidate_delete`；actor=user；五份旧配置的物理删除已核验。canonical manifest 的候选条目继续保存就绪依据与恢复哈希，最新本地删除状态记录在上述移动收据中；它们不代表待删副本仍存在。

## 已完成工作树的本地清理

本轮核对时，以下四个工作树没有未提交或未跟踪变更，也未发现其他进程的命令行引用这些目录。被忽略的文件为 Python/测试缓存、Node 依赖和历史测试产物；`5646` 的临时数据库位于测试目录，账务库仅含 1–4 条测试记录，未把它们当作正式账本。

| 完整工作树目录 | 文件逻辑大小 |
|---|---:|
| `C:/Users/Q/.codex/worktrees/5646/03_Investment_System` | 160,083,168 bytes |
| `C:/Users/Q/.codex/worktrees/8632/03_Investment_System` | 62,837,592 bytes |
| `C:/Users/Q/.codex/worktrees/bc43/03_Investment_System` | 119,289,275 bytes |
| `C:/Users/Q/.codex/worktrees/df8c/03_Investment_System` | 104,098,313 bytes |

以上为删除前文件逻辑大小，合计约 425.63 MiB，不能直接等同于实际磁盘释放量。2026-09-06 用户反馈已删除；本次现场核对四个目录均已不存在，长期工作树和本轮工作树仍在。

Git 中仍有这四个已失效的 worktree 登记。只读预演 `git worktree prune --dry-run --verbose` 确认待清理的仅为这四条；分支仍保留。用户可手动执行以下命令清理登记元数据：

```powershell
git -C 'C:/Projects/03_Investment_System' worktree prune --verbose
```

待办：`completed_worktree_registration_cleanup`；owner=user；severity=low；实际目录已删除，下一步仅清理上述失效登记。项目 `AGENTS.md` 禁止自动删除目录，因此 Codex 没有执行实际 prune。当前主目录、Portfolio/Review 长期工作树和本轮工作树不在清理范围。

## 后续旧 R5 依赖退役

第一轮完成的是默认测试负担收缩、治理清单压缩和五份无当前消费者配置的移出。其余旧工具仍须继续核查，测试引用本身不是永久保留理由。

- 当前共用契约继续保留：`docs/workflows/RESEARCH_WORKFLOW.md` 仍以 `schemas/r5_final_report_review.schema.json` 定义新运行的人审结构；当前 Research smoke 仍调用研究包、预测与估值校验器。文件名中的 R5 不代表功能已失效。
- 优先核查 Bundle 5 的披露、市场同业、预测估值三类旧 onboarding 生成器：静态引用显示其专用测试仍直接加载当前物理脚本，retirement guard 也声明了旧路由的显式调用。这一组需要连同专用测试、模板和配置核对后退役，不能仅移动脚本。
- `.agents/skills/stock-deep-dive/SKILL.md` 将 R5 研究包列为显式请求才启用的能力，普通个股流程不加载 Bundle generation 或旧报告状态。后续应区分只服务旧生成器的资产和仍被保留能力共用的资产。

进展：本轮 Bundle 5 依赖组已完成退役，详见 [第二轮专项记录](2026-09-06_legacy_bundle5_retirement.md)。7 个脚本、1 份规则、9 个专用测试文件已由用户删除并核验，真实输入来源检查独立保留；默认全套 2248 passed、历史兼容 88 passed，当前 17 个研究产物逐字节一致。共享校验器和正式研究证据继续保留。`bundle5_manual_delete` 已完成；Git 恢复依据继续保留。

## 其他剩余事项

- 发布状态：尚未推送、建 PR 或合并；owner=user；severity=low；本地变更完成验收后再决定发布。
- 其他旧生成器、模板、readout 和样例仍按实际依赖保留；本轮没有把 R5 命名当作可删除证据。
- 根目录历史 ZIP 继续保留，不纳入这批五文件清单。
- 本轮没有执行目录删除、Git GC、历史重写或跨工作树私有配置迁移。
