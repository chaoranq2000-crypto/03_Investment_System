# R5 Patch 27 — Inventory V2 Reconciliation

status: `TASK_CARD`

## 背景

`reports/p1_6/r5_patch_1_12_inventory_status.yaml` 当前为 `claimed_complete_but_validation_failed`，并记录 34 个 artifact failures。主要原因是 Patch 1-12 的 expected artifact config 与实际落地文件命名/补丁拆法不一致，部分文件确实缺失。

## 目标

建立可信的 inventory v2：既不掩盖缺失，也不让旧命名造成虚假失败。

## 允许修改

```text
config/r5_patch_1_12_expected_artifacts.yaml
config/r5_patch_inventory_aliases.yaml  # 如需要
scripts/r5_patch_inventory_check.py
tests/test_r5_patch_inventory_check.py
reports/p1_6/r5_patch_1_12_inventory_status.yaml
reports/p1_6/R5_PATCH_27_INVENTORY_V2_READOUT.md
```

## 处理规则

1. 如果实际文件存在但命名变了，使用 alias 或更新 expected artifact。
2. 如果文件确实缺失，不要把它从 inventory 中删除；要标记为 `missing_required`，并给出补齐任务。
3. 如果某个历史 Patch 被后续 Patch 明确替代，必须在 config 中标注 `superseded_by` 和替代文件。
4. inventory 输出必须是多行 YAML。
5. accepted 只能在真实 artifact 全部通过时为 true。

## 全局禁止事项

- 不生成任何买入、卖出、持有、建仓、减仓、仓位建议。
- 不生成 sample-quality 个股报告。
- 不进入 P2。
- 不调用 live API。
- 不把 TODO / MISSING_DISCLOSURE / LOW_CONFIDENCE_CLUE_ONLY 写成事实。
- 不用 readout 自述替代实际命令、exit_code、stdout/stderr 和 artifact evidence。


## 必跑命令

```bash
python -m py_compile scripts/r5_patch_inventory_check.py
python -m pytest -q tests/test_r5_patch_inventory_check.py --tb=short
python scripts/r5_patch_inventory_check.py --config config/r5_patch_1_12_expected_artifacts.yaml --out reports/p1_6/r5_patch_1_12_inventory_status.yaml --strict
```

## 验收标准

- 如果 strict 仍失败，readout 必须列出剩余 missing_required，不得声称完成。
- 如果 strict 通过，`inventory_status` 必须是 `validated_complete`，且 artifact_failures 为 0。
- inventory YAML 必须多行可读。
- readout 必须列出旧失败数、新失败数、变更原因。
