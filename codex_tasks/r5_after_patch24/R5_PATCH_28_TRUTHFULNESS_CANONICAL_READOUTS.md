# R5 Patch 28 — Truthfulness Canonical Readouts

status: `TASK_CARD`

## 背景

Patch 19 的 truthfulness gate 失败，因为历史 R5 readout 缺少命令证据。不能事后伪造历史执行结果。正确做法是建立 canonical / legacy 边界：

- 历史缺证据 readout 标记为 legacy_noncanonical；
- 对当前可重跑的任务生成 rerun supplement readout；
- truthfulness gate 只对 canonical readout 做 blocking 检查，对 legacy readout 做归档检查。

## 目标

让 readout truthfulness gate 既严格又诚实。

## 允许修改

```text
config/r5_readout_truthfulness_rules.yaml
config/r5_readout_canonical_index.yaml
scripts/check_r5_readout_truthfulness.py
tests/test_r5_readout_truthfulness.py
reports/p1_6/R5_READOUT_CANONICAL_INDEX.md
reports/p1_6/R5_PATCH_28_TRUTHFULNESS_CANONICAL_READOUTS.md
```

## 要求

1. 建立 `canonical_index`，字段至少包含：
   - path
   - canonical_status: canonical / legacy_noncanonical / superseded
   - reason
   - replacement_or_supplement_path
   - blocking_for_strict_smoke
2. 对 legacy_noncanonical，不要求补造 commands_run，但必须说明不能作为验收证据。
3. 对 canonical readout，必须要求：
   - files_added / files_modified
   - commands_run
   - exit_code
   - stdout_or_stderr_summary
   - known_todos
   - next_recommended_patch
   - artifact evidence: sha256 / line_count / checked count / inventory_status
4. truthfulness gate 严格模式不得被 legacy 历史读数误伤，但也不得把 legacy 当成通过证据。

## 全局禁止事项

- 不生成任何买入、卖出、持有、建仓、减仓、仓位建议。
- 不生成 sample-quality 个股报告。
- 不进入 P2。
- 不调用 live API。
- 不把 TODO / MISSING_DISCLOSURE / LOW_CONFIDENCE_CLUE_ONLY 写成事实。
- 不用 readout 自述替代实际命令、exit_code、stdout/stderr 和 artifact evidence。


## 必跑命令

```bash
python -m py_compile scripts/check_r5_readout_truthfulness.py
python -m pytest -q tests/test_r5_readout_truthfulness.py --tb=short
python scripts/check_r5_readout_truthfulness.py --rules config/r5_readout_truthfulness_rules.yaml --glob 'reports/p1_6/R5_PATCH_*_READOUT.md' --strict --json reports/p1_6/r5_readout_truthfulness_result.json
```

## 验收标准

- 不出现“历史 readout 被补写成当时已执行”的误导。
- strict truthfulness 对 canonical readout 是 blocking。
- legacy_noncanonical 在结果中可见。
- readout 明确下一步 Patch 29。
