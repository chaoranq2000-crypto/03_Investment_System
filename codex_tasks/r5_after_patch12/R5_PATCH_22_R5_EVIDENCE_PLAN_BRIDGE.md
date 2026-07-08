# Patch 22：R5 evidence plan bridge

任务文件：`R5_PATCH_22_R5_EVIDENCE_PLAN_BRIDGE.md`


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

R5 sample-quality 的瓶颈不是 writer，而是 evidence density。需要把 R5 source gaps 反向转成 evidence-ingest 任务。

## 目标

新增 R5 evidence plan bridge，把 R5 pack 的缺口转成 evidence-ingest plan。

## 建议新增文件

```text
.agents/skills/evidence-ingest/references/r5_stock_evidence_plan_contract.md
.agents/skills/evidence-ingest/assets/r5_stock_evidence_plan.example.yaml
scripts/build_r5_evidence_plan_from_gaps.py
tests/test_build_r5_evidence_plan_from_gaps.py
reports/p1_6/R5_PATCH_22_EVIDENCE_PLAN_BRIDGE_READOUT.md
```

## 输出字段

```yaml
stock_code:
workflow_id:
official_filings_needed:
structured_financial_data_needed:
market_snapshot_needed:
peer_snapshot_needed:
industry_data_needed:
analyst_consensus_needed:
news_and_event_sources_needed:
priority:
blocking_for_r5:
```

## 验收标准

1. 能从 Patch 21 的 source gap report 生成 evidence plan。
2. 每个 evidence need 有 priority 和 blocking flag。
3. 不做真实下载。
4. 不新增 API 依赖。

## 建议测试命令

```text
python -m py_compile scripts/build_r5_evidence_plan_from_gaps.py
pytest -q tests/test_build_r5_evidence_plan_from_gaps.py --tb=short
```
