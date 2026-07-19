# BF2 Local Input Handoff

## 背景

真实 BF2 运行产物位于源工作区的未跟踪路径，包括：

```text
C:\Projects\03_Investment_System_bf2\.local\
C:\Projects\03_Investment_System_bf2\reports\p1_6\r5_bundle17r_bf2*
```

隔离 worktree 不会自动包含这些文件，因此必须显式建立只读输入交接。

## 正确做法

1. 在源工作区枚举相关文件；
2. 对每个文件记录：绝对路径、相对逻辑路径、大小、mtime、SHA-256；
3. 只复制 Mission 实际需要的文件到：

```text
<isolated_worktree>\.local\night_shift\inputs\<input_set_sha>\
```

4. 在 `.local/night_shift/input_manifest.json` 记录来源和目标；
5. 后续 BF2 seed adapter 只消费该 immutable input set；
6. 所有 `.local/` 文件保持 untracked/ignored。

## 禁止做法

- 不把源工作区未跟踪文件直接 `git add -f`；
- 不将真实运行产物复制到 `tests/fixtures/` 作为长期 fixture；
- 不在导入时改写原 work order 或 result；
- 不通过删除重复 blocker 改变 63 的真实 occurrence 计数；
- 不因为 suite 级任务共享一个 `case_id=__suite__` 就丢失其身份。

## 输入完整性门

导入前必须满足：

```yaml
work_orders_total: 6
work_orders_pending: 6
blocker_occurrences_total: 63
blocker_occurrences_resolved: 0
failed_results: 0
orphan_results: 0
rejected_artifacts: 0
```

任何一项不匹配都需要：

- 停止 seed；
- 生成 `bf2_input_mismatch` failure packet；
- 在晨报说明实际读数与预期差异；
- 不自动“兼容”到新计数。

## 分类规则

导入后每个 blocker occurrence 至少被分类为：

- `engineering_local`：仅依赖仓库内代码/测试/已存在工件，可自动执行；
- `evidence_required`：必须获取或审核新外部证据；
- `analysis_required`：证据可能存在，但需要研究因果或经济模型判断；
- `human_gate`：需要人工审核、映射接受或 exact-hash 决定；
- `dependency_blocked`：依赖另一个未完成 blocker。

分类不是解决；只有完整 acceptance + receipt 才能减少 resolved blocker 数。
