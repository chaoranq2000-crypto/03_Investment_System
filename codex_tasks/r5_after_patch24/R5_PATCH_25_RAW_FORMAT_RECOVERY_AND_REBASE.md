# R5 Patch 25 — Raw Format Recovery and Rebase

status: `TASK_CARD`

## 背景

最新 raw 视图显示多个关键 Python、pytest、YAML、Markdown artifact 仍是 1 行或 2 行文件。之前 Patch 13 的格式修复没有真正消除 raw 物理换行折叠问题，后续 smoke/readout 可能存在假阳性。

## 目标

恢复所有 R5 gate / smoke / validator / fixture / source-gapped pack 的真实物理换行，并重新生成格式修复 readout。

## 优先修复文件

至少覆盖：

```text
scripts/check_r5_artifact_format.py
scripts/r5_patch_inventory_check.py
scripts/check_r5_readout_truthfulness.py
scripts/run_r5_mvp_smoke.py
scripts/r5_readiness_gate.py
config/r5_patch_1_12_expected_artifacts.yaml
config/r5_readout_truthfulness_rules.yaml
config/r5_readiness_gate_rules.yaml
templates/r5_stock_research_pack.yaml
benchmarks/r5_report_quality_rubric.yaml
.agents/skills/stock-deep-dive/scripts/validate_r5_stock_research_pack.py
.agents/skills/stock-deep-dive/assets/r5_stock_research_pack.valid.example.yaml
reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_stock_research_pack_source_gapped.yaml
reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_source_gap_report.md
reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_evidence_plan_from_gaps.yaml
tests/test_validate_r5_stock_research_pack.py
tests/test_r5_readiness_gate.py
```

如果发现其他 R5 相关 `.py/.yaml/.yml/.md/.json/.csv` 是一行 blob，也必须纳入修复。

## 允许修改

- R5 相关 scripts / config / templates / benchmarks / tests / workflow fixture artifacts。
- 新增 `reports/p1_6/R5_PATCH_25_RAW_FORMAT_RECOVERY_READOUT.md`。

## 禁止修改

- 不重写历史 R4 报告。
- 不改变 R5 readiness 的业务语义。
- 不把 source-gapped pack 升级为 sample-quality。
- 不用自动格式化器删除 TODO。

## 全局禁止事项

- 不生成任何买入、卖出、持有、建仓、减仓、仓位建议。
- 不生成 sample-quality 个股报告。
- 不进入 P2。
- 不调用 live API。
- 不把 TODO / MISSING_DISCLOSURE / LOW_CONFIDENCE_CLUE_ONLY 写成事实。
- 不用 readout 自述替代实际命令、exit_code、stdout/stderr 和 artifact evidence。


## 验收标准

1. 所有修复文件真实多行，不能只包含字面量 `\n`。
2. Python 文件不得出现 `#!/usr/bin/env python3 ... from __future__ import ...` 同行。
3. Python 文件不得出现 `from __future__ import annotations from typing ...` 同行。
4. pytest 文件必须有真实 `def test_` 行。
5. YAML / JSON / Markdown 文件可读、可解析，且 source gaps 仍显式存在。
6. readout 必须列出 before_lines / after_lines / sha256 / commands / exit_code。

## 必跑命令

```bash
python -m py_compile scripts/check_r5_artifact_format.py scripts/r5_patch_inventory_check.py scripts/check_r5_readout_truthfulness.py scripts/run_r5_mvp_smoke.py scripts/r5_readiness_gate.py
python - <<'PY'
from pathlib import Path
paths = [
  'scripts/check_r5_artifact_format.py',
  'scripts/r5_patch_inventory_check.py',
  'scripts/check_r5_readout_truthfulness.py',
  'scripts/run_r5_mvp_smoke.py',
  'scripts/r5_readiness_gate.py',
  'templates/r5_stock_research_pack.yaml',
  'benchmarks/r5_report_quality_rubric.yaml',
  'tests/test_validate_r5_stock_research_pack.py',
  'tests/test_r5_readiness_gate.py',
]
for p in paths:
    text = Path(p).read_text(encoding='utf-8')
    lines = text.splitlines()
    assert len(lines) >= 8, (p, len(lines))
    assert not (lines and lines[0].startswith('#!') and 'from __future__' in lines[0]), p
    assert '\n' not in text[:1000] or text.count('\n') < len(lines), p
print('physical format recovery ok')
PY
python scripts/check_r5_artifact_format.py --strict --json reports/p1_6/r5_format_guard.json
```

## 输出要求

新增 readout：

```text
reports/p1_6/R5_PATCH_25_RAW_FORMAT_RECOVERY_READOUT.md
```

readout 必须说明：

- 修复文件列表；
- 每个文件修复前后 line_count；
- 每个关键文件 sha256；
- 命令和 exit_code；
- 仍未修复的文件；
- 下一步建议 Patch 26。
