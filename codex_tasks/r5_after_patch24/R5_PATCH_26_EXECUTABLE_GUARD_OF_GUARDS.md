# R5 Patch 26 — Executable Guard of Guards

status: `TASK_CARD`

## 背景

当前 `py_compile` 不能识别 shebang 注释吞掉代码的文件，因为一整行以 `#` 开头时，后面的代码会被视为注释而导致空模块假阳性通过。需要让 format guard 保护自身和所有 gate-of-gates。

## 目标

强化 `scripts/check_r5_artifact_format.py`，使其能检测：

- guard 脚本自身是否多行；
- module AST 是否非空；
- 是否存在 shebang/comment 吞代码；
- 是否存在一行 import/def/class blob；
- CLI gate 是否 `--help` 可执行；
- pytest 文件是否真实可 collect。

## 允许修改

```text
scripts/check_r5_artifact_format.py
tests/test_check_r5_artifact_format.py
config/r5_artifact_format_guard_rules.yaml  # 如需要
reports/p1_6/R5_PATCH_26_EXECUTABLE_GUARD_READOUT.md
```

## 需要纳入默认检查的 gate-of-gates

```text
scripts/check_r5_artifact_format.py
scripts/r5_patch_inventory_check.py
scripts/check_r5_readout_truthfulness.py
scripts/run_r5_mvp_smoke.py
scripts/r5_readiness_gate.py
```

## 必须新增测试场景

1. 一行 shebang blob：`#!/usr/bin/env python3 from __future__ import annotations` 必须 fail。
2. 一行普通 syntax blob：`from __future__ import annotations from pathlib import Path` 必须 fail。
3. comment-only module 必须 fail。
4. empty AST module 必须 fail。
5. 正常多行 CLI 脚本必须 pass。
6. `--help` exit_code 非 0 必须 fail。

## 全局禁止事项

- 不生成任何买入、卖出、持有、建仓、减仓、仓位建议。
- 不生成 sample-quality 个股报告。
- 不进入 P2。
- 不调用 live API。
- 不把 TODO / MISSING_DISCLOSURE / LOW_CONFIDENCE_CLUE_ONLY 写成事实。
- 不用 readout 自述替代实际命令、exit_code、stdout/stderr 和 artifact evidence。


## 必跑命令

```bash
python -m py_compile scripts/check_r5_artifact_format.py
python -m pytest -q tests/test_check_r5_artifact_format.py --tb=short
python scripts/check_r5_artifact_format.py --strict --json reports/p1_6/r5_format_guard.json
```

## 验收标准

- 新 guard 不再只依赖 `py_compile`。
- 任何 gate-of-gates 一行化都会 fail。
- `r5_format_guard.json` 为多行 JSON，包含 `checked`、`failed`、每个 artifact 的 issues。
- readout 记录所有命令、exit_code、stdout/stderr 摘要、line_count evidence。
