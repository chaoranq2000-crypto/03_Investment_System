# Stock Report Production Workflow — Compatibility Pointer

本文件仅为兼容性指针。个股报告生产细节已迁移到 `stock-deep-dive` 的 skill reference：

```text
.agents/skills/stock-deep-dive/references/report_production_profile.md
```

当前定位：

```yaml
status: migrated_to_skill_profile
profile_id: stock_report_production
parent_workflow_type: stock_first_closed_loop
active_owner: stock-deep-dive
```

不要把 `stock_report_production` 作为平级 workflow 使用。

全局 workflow type、stage 和 gate 以以下文件为准：

```text
docs/workflows/RESEARCH_WORKFLOW.md
```

当前主路径仍是：

```text
research-orchestrator
→ evidence-ingest
→ stock-deep-dive
→ segment-company-mapping
→ quality-review
→ research-orchestrator close readout
```
