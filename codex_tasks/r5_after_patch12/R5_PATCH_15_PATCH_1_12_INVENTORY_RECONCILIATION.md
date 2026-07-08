# Patch 15：Patch 1-12 实际落地清单核对

任务文件：`R5_PATCH_15_PATCH_1_12_INVENTORY_RECONCILIATION.md`


## 全局禁止事项

- 不生成任何真实个股的投资结论。
- 不输出买入、卖出、持有、建仓、清仓、目标仓位等建议。
- 不把 `TODO_*`、`MISSING_DISCLOSURE`、`source_gap` 写成事实。
- 不接入真实 API，不新增外部付费数据依赖。
- 不修改历史 workflow run 的研究结论；fixture 文件除外。
- 不把 readout 写成没有命令、没有退出码、没有测试结果的叙述。
- 不在一个 patch 中顺手实现下一张任务卡。

## 全局交付要求

每张任务卡完成后必须新增对应 readout，readout 至少包含：

```text
status
files_added
files_modified
commands_run
exit_codes
stdout_or_stderr_summary
known_todos
next_recommended_patch
```

所有新增 / 修改的 Python 文件必须能通过：

```text
python -m py_compile <file>
```

所有新增 / 修改的 YAML 文件必须能通过：

```text
python -c "import yaml, pathlib; yaml.safe_load(pathlib.Path('<file>').read_text(encoding='utf-8'))"
```



## 背景

仓库 readout 声称 Patch 1-12 完成，但 raw 文件检查发现可执行性异常。需要把“声称完成”与“实际可用”分开。

## 目标

新增一个 inventory reconciliation 工具，逐项核对 Patch 1-12 的预期交付物、实际文件、格式状态、编译状态、测试状态和 readout 状态。

## 建议新增文件

```text
scripts/r5_patch_inventory_check.py
configs/r5_patch_1_12_expected_artifacts.yaml
tests/test_r5_patch_inventory_check.py
reports/p1_6/R5_PATCH_15_INVENTORY_RECONCILIATION_READOUT.md
```

## 配置字段

```yaml
patch_id:
expected_artifacts:
  - path:
    artifact_type: markdown|yaml|python|pytest|readout
    required: true
    validation:
      - exists
      - line_count_gt_one
      - yaml_parse
      - py_compile
      - pytest_collectable
related_readout:
blocking_if_missing: true
```

## 输出

```text
reports/p1_6/r5_patch_1_12_inventory_status.yaml
```

每条 artifact 输出：

```yaml
path:
exists:
line_count:
parse_status:
compile_status:
test_collectable:
status: pass|warn|fail
notes:
```

## 验收标准

1. 能区分 `claimed_complete` 与 `validated_complete`。
2. 对缺文件、单行文件、不可编译文件给出 fail。
3. Patch 1-12 中任一 blocking artifact fail 时，总状态不得为 accepted。
4. readout 明确写出下一步修复项。

## 建议测试命令

```text
python -m py_compile scripts/r5_patch_inventory_check.py
python scripts/r5_patch_inventory_check.py --config configs/r5_patch_1_12_expected_artifacts.yaml --out reports/p1_6/r5_patch_1_12_inventory_status.yaml
pytest -q tests/test_r5_patch_inventory_check.py --tb=short
```
