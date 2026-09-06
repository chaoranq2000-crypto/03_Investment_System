# Research 运行依赖瘦身记录

状态：工程改造及全部验证完成；文件和工作树的物理删除待用户执行。

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

按 Git LF 字节计算，治理清单从 749,985 bytes 缩减至 64,091 bytes，下降 91.45%。原来被隔离的 89 项检查在基线中合计耗时约 170.19 秒。

## 验证证据

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

## 待用户手动删除的 5 个文件

以下文件只剩历史 Git fixture 或历史文字引用，没有当前 Python 物理消费者。精确路径、原 blob、SHA-256 和恢复提交保留在 canonical manifest 的 `manual_delete_candidates`，共 34,765 Git bytes。当前尚未删除，不能计入已释放空间。

路径均相对于本轮工作树，不能在旧的主目录或其他工作树中执行这批清理。

```text
config/r5_bundle3_expected_artifacts.yaml
config/r5_bundle4_expected_artifacts.yaml
config/r5_bundle5_expected_artifacts.yaml
config/r5_patch_1_12_expected_artifacts.yaml
config/r5_patch_49_55_expected_artifacts.yaml
```

待办：`manual_candidate_delete`；owner=user；severity=low；下一步为手动删除后由 Codex 复核文件缺失、引用和测试，并登记完成状态。

## 已完成工作树的本地清理

本轮核对时，以下四个工作树没有未提交或未跟踪变更，也未发现其他进程的命令行引用这些目录。被忽略的文件为 Python/测试缓存、Node 依赖和历史测试产物；`5646` 的临时数据库位于测试目录，账务库仅含 1–4 条测试记录，未把它们当作正式账本。

| 完整工作树目录 | 文件逻辑大小 |
|---|---:|
| `C:/Users/Q/.codex/worktrees/5646/03_Investment_System` | 160,083,168 bytes |
| `C:/Users/Q/.codex/worktrees/8632/03_Investment_System` | 62,837,592 bytes |
| `C:/Users/Q/.codex/worktrees/bc43/03_Investment_System` | 119,289,275 bytes |
| `C:/Users/Q/.codex/worktrees/df8c/03_Investment_System` | 104,098,313 bytes |

合计约 425.63 MiB，实际释放量受文件系统分配影响。未跟踪的临时测试产物不由 Git 恢复；如需保留它们，应先自行保留。

用户可在确认目录后逐个手动运行以下命令；它们保留 Git 分支。本任务未执行这些目录删除命令。

```powershell
git worktree remove 'C:/Users/Q/.codex/worktrees/5646/03_Investment_System'
git worktree remove 'C:/Users/Q/.codex/worktrees/8632/03_Investment_System'
git worktree remove 'C:/Users/Q/.codex/worktrees/bc43/03_Investment_System'
git worktree remove 'C:/Users/Q/.codex/worktrees/df8c/03_Investment_System'
```

待办：`completed_worktree_cleanup`；owner=user；severity=low；下一步为手动移除后核对 worktree 注册信息和实际磁盘占用。当前主目录、Portfolio/Review 长期工作树和本轮工作树不在此范围。

## 其他剩余事项

- 发布状态：尚未推送、建 PR 或合并；owner=user；severity=low；本地变更完成验收后再决定发布。
- 其他旧生成器、模板、readout 和样例仍按实际依赖保留；本轮没有把 R5 命名当作可删除证据。
- 根目录历史 ZIP 继续保留，不纳入这批五文件清单。
- 本轮没有执行目录删除、Git GC、历史重写或跨工作树私有配置迁移。
