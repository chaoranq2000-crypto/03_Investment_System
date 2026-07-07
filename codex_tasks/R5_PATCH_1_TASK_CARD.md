# Codex Task Card — R5 Patch 1：foundation hardening + stock-deep-dive B5-lite

## 任务名称

R5-MVP Patch 1：修复 R5 基础文件格式，并补强 `stock-deep-dive` 的 R5 B5-lite research pack 契约。

## 背景

最新工作区已经合入 Patch 0，但部分 R5 Markdown / YAML 文件在远端 raw 视图中呈单行压缩状态，影响阅读和 YAML 解析。下一步应先让 R5 基础文件可读、可解析，并让 `stock-deep-dive` 能稳定输出 R5 research pack 骨架。

本任务粒度为“中等”：格式修复 + B5-lite 契约 + 示例 + 校验脚本 + pytest。不要继续进入 forecast、valuation、report composer 或 quality-review 实现。

## 目标

```text
1. 修复 Patch 0 R5 文件格式；
2. 新增 r5_stock_deep_dive_contract.md；
3. 新增 r5_financial_history_contract.md；
4. 新增 r5_business_breakdown_contract.md；
5. 新增 r5_research_pack_output_contract.md；
6. 新增 r5_stock_research_pack.example.yaml；
7. 新增 validate_r5_stock_research_pack.py；
8. 新增 pytest；
9. 新增 Patch 1 plan / readout。
```

## 禁止事项

```text
不修改 reports/workflow_runs/ 历史 run；
不生成任何股票研究报告；
不计算真实 forecast；
不计算真实 valuation；
不接入真实 API；
不修改 evidence-ingest 执行逻辑；
不修改 quality-review 执行逻辑；
不把 TODO / MISSING_DISCLOSURE 写成事实；
不输出直接交易指令、仓位建议或保证收益表达；
不声称 R5 已完成。
```

## 测试命令

```bash
python - <<'PY'
import yaml
for p in [
    "templates/r5_stock_research_pack.yaml",
    "benchmarks/r5_report_quality_rubric.yaml",
    ".agents/skills/stock-deep-dive/assets/r5_stock_research_pack.example.yaml",
]:
    with open(p, "r", encoding="utf-8") as f:
        yaml.safe_load(f)
    print(f"yaml ok: {p}")
PY

python .agents/skills/stock-deep-dive/scripts/validate_r5_stock_research_pack.py \
  .agents/skills/stock-deep-dive/assets/r5_stock_research_pack.example.yaml

python -m pytest tests/test_validate_r5_stock_research_pack.py
```

## 输出要求

完成后输出：修改文件列表、新增文件列表、测试结果、diff summary、未完成项和下一步建议。不要继续执行 Patch 2。
