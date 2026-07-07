# R5-MVP Patch 1 Plan — foundation hardening + stock-deep-dive B5-lite

## 1. Patch 目标

本 patch 是 R5-MVP 的第二步，合并一个相邻目标簇：

```text
1. 修复 Patch 0 文档与 YAML 的多行格式问题；
2. 为 stock-deep-dive 新增 R5 B5-lite 契约；
3. 新增 financial_history_pack 与 business_breakdown_pack 契约；
4. 新增 R5 research pack 输出契约；
5. 新增 R5 research pack 示例；
6. 新增轻量校验脚本和 pytest；
7. 新增下一阶段 Codex 任务卡。
```

## 2. 不做什么

```text
不修改 reports/workflow_runs/ 历史产物；
不生成任何个股报告正文；
不计算真实 forecast；
不计算真实 valuation；
不新增真实 API 调用；
不改 evidence-ingest 执行逻辑；
不改 quality-review 执行逻辑；
不输出直接交易指令或仓位建议；
不声称 R5 已完成。
```

## 3. 允许文件范围

```text
docs/workflows/R5_MVP_RESTRUCTURE_PLAN.md
docs/workflows/R5_SAMPLE_QUALITY_STOCK_REPORT_SPEC.md
templates/r5_stock_research_pack.yaml
templates/r5_stock_research_note.md
benchmarks/r5_report_quality_rubric.yaml
reports/p1_6/R5_MVP_PATCH_0_PLAN.md
codex_tasks/R5_PATCH_0_TASK_CARD.md
.agents/skills/stock-deep-dive/references/r5_stock_deep_dive_contract.md
.agents/skills/stock-deep-dive/references/r5_financial_history_contract.md
.agents/skills/stock-deep-dive/references/r5_business_breakdown_contract.md
.agents/skills/stock-deep-dive/references/r5_research_pack_output_contract.md
.agents/skills/stock-deep-dive/assets/r5_stock_research_pack.example.yaml
.agents/skills/stock-deep-dive/scripts/validate_r5_stock_research_pack.py
tests/test_validate_r5_stock_research_pack.py
reports/p1_6/R5_MVP_PATCH_1_PLAN.md
codex_tasks/R5_PATCH_1_TASK_CARD.md
```

## 4. 验收标准

```text
1. Patch 0 Markdown 文件恢复多行标题结构；
2. Patch 0 YAML 文件可被 yaml.safe_load 解析；
3. R5 B5-lite contract 明确输入、输出、步骤、降级规则和禁止事项；
4. financial_history_pack 和 business_breakdown_pack 字段可支撑样例质量报告；
5. 示例 r5_stock_research_pack.example.yaml 可通过校验；
6. validator 能发现缺顶层字段、缺 missing_reason、sample-quality 越权等问题；
7. pytest 通过；
8. 不修改历史 workflow run。
```

## 5. 建议测试命令

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

## 6. 下一步建议

```text
Patch 2：evidence-ingest R5 data plan + manifest bridge
```

Patch 2 不做真实下载器，而是定义 R5 所需 evidence plan、manifest bridge、data handoff 和 missing source reporting，使 R5 research pack 能知道自己缺哪些证据。
