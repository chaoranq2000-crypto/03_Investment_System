# Documentation Meta Index — 文档元索引

## 1. 文件清单

| 文件 | 性质 | 用途 |
|---|---|---|
| `AGENTS.md` | Codex 指令 | 项目级长期规则、证据纪律、文件归位和输出要求 |
| `README.md` | 项目入口 | 给人看的项目说明、阶段路线、使用方式 |
| `docs/index.md` | 文档入口 | 汇总项目、架构、政策、手册、计划和元文档 |
| `docs/project/PROJECT_CHARTER.md` | 项目章程 | 锁定目标、范围、非目标、路线图和暂停点 |
| `docs/architecture/WORKSPACE_STRUCTURE.md` | 目录规范 | 说明哪些文件放哪里，避免工作区混乱 |
| `docs/architecture/RESEARCH_OBJECT_MODEL.md` | 对象模型 | 定义 Segment、Company、Evidence、Claim、Metric 等对象 |
| `docs/policies/EVIDENCE_AND_CITATION_POLICY.md` | 证据纪律 | 定义 evidence_id、source rank、claim、freshness 和引用规则 |
| `docs/policies/QUALITY_GUARDRAILS.md` | 质量规则 | 定义质量门槛、反幻觉、反证、风险和更新检查 |
| `docs/playbooks/OPERATING_PLAYBOOK.md` | 操作手册 | 定义 P0-P3 的常用工作流和 skill 调用方式 |
| `docs/plans/plan_template.md` | 计划模板 | 定义复杂任务的计划格式和验收方法 |
| `docs/plans/p0_acceptance_checklist.md` | 验收清单 | 用于判断 P0 是否完成并暂停 |
| `docs/plans/p0_execution_plan.md` | P0 执行计划 | 记录 P0 阶段的执行步骤和检查项 |
| `docs/plans/p1_execution_plan.md` | P1 执行计划 | 记录单细分最小研究闭环的步骤和验收标准 |
| `docs/plans/p1_1_revision_plan.md` | P1.1 修正计划 | 记录 P1 修正完善计划，保留为独立计划快照 |
| `docs/logs/README.md` | 日志规则 | 定义 `docs/logs/` 的日志命名、子目录和内容要求 |
| `docs/logs/2026-07-01_plan_completion_log.md` | 计划完成情况日志 | 汇总 P0、P1 和 P1.5 执行计划的实际执行、验收、偏差、P2 边界和发布状态 |
| `docs/logs/2026-07-01_docs_structure_cleanup_log.md` | 结构整理日志 | 记录计划、日志和 P0 阶段记录的目录整理与污染检查 |
| `docs/logs/p0/2026-07-01_p0_preplanning_confirmation.md` | P0 记录 | 确认 P0 范围、非目标、原则、验收和暂停点 |
| `docs/logs/p0/2026-07-01_p0_smoke_test.md` | P0 记录 | 回答 P0 smoke test 的 13 个问题并记录阻塞项 |
| `docs/logs/p0/2026-07-01_p0_closeout.md` | P0 记录 | 记录 P0 完成、未做、TODO、P1 前置和暂停确认 |
| `.codex/config.toml` | Codex 配置 | 声明 repo skills 路径和项目配置 |

---

## 2. 推荐阅读顺序

```text
README.md
↓
docs/index.md
↓
AGENTS.md
↓
docs/project/PROJECT_CHARTER.md
↓
docs/architecture/WORKSPACE_STRUCTURE.md
↓
docs/architecture/RESEARCH_OBJECT_MODEL.md
↓
docs/policies/EVIDENCE_AND_CITATION_POLICY.md
↓
docs/policies/QUALITY_GUARDRAILS.md
↓
docs/playbooks/OPERATING_PLAYBOOK.md
↓
docs/plans/plan_template.md
↓
docs/plans/p0_acceptance_checklist.md
↓
docs/plans/p0_execution_plan.md
↓
docs/logs/p0/2026-07-01_p0_smoke_test.md
↓
docs/logs/p0/2026-07-01_p0_closeout.md
↓
docs/plans/p1_execution_plan.md
↓
docs/plans/p1_1_revision_plan.md
↓
docs/logs/README.md
↓
docs/logs/2026-07-01_plan_completion_log.md
↓
docs/logs/2026-07-01_docs_structure_cleanup_log.md
```

---

## 3. P0 使用建议

项目根目录只保留入口文件、配置文件和一级功能目录；治理类、规则类、规划类文档放入 `docs/`。然后再生成：

```text
.agents/skills/*/SKILL.md
config/*.yaml
templates/*.md
decisions/*.md
```

P0 文档骨架完成后，不要马上做复杂自动化。先用 `docs/plans/p0_acceptance_checklist.md` 验收，再进入 P1 最小闭环。P1/P1.5 执行后用 `docs/logs/2026-07-01_plan_completion_log.md` 回看计划执行、偏差修复、P2 边界和 GitHub 发布状态。
