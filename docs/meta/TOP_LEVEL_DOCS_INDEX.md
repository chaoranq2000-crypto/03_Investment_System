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
| `docs/plans/PLANS.md` | 计划模板 | 定义复杂任务的计划格式和验收方法 |
| `docs/plans/P0_ACCEPTANCE_CHECKLIST.md` | 验收清单 | 用于判断 P0 是否完成并暂停 |
| `docs/plans/P0_执行计划.md` | P0 执行计划 | 记录 P0 阶段的执行步骤和检查项 |
| `docs/plans/P1_执行计划.md` | P1 执行计划 | 记录单细分最小研究闭环的步骤和验收标准 |
| `docs/plans/2026-07-01_execution_plan_log.md` | 执行日志 | 汇总 P0 和 P1 两次执行计划的实际执行、验收、偏差和发布状态 |
| `docs/p0/P0_前置规划确认稿.md` | P0 记录 | 确认 P0 范围、非目标、原则、验收和暂停点 |
| `docs/p0/P0_smoke_test.md` | P0 记录 | 回答 P0 smoke test 的 13 个问题并记录阻塞项 |
| `docs/p0/P0_closeout.md` | P0 记录 | 记录 P0 完成、未做、TODO、P1 前置和暂停确认 |
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
docs/plans/PLANS.md
↓
docs/plans/P0_ACCEPTANCE_CHECKLIST.md
↓
docs/plans/P0_执行计划.md
↓
docs/p0/P0_smoke_test.md
↓
docs/p0/P0_closeout.md
↓
docs/plans/P1_执行计划.md
↓
docs/plans/2026-07-01_execution_plan_log.md
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

P0 文档骨架完成后，不要马上做复杂自动化。先用 `docs/plans/P0_ACCEPTANCE_CHECKLIST.md` 验收，再进入 P1 最小闭环。P1 执行后用 `docs/plans/2026-07-01_execution_plan_log.md` 回看计划执行、偏差修复和 GitHub 发布状态。
