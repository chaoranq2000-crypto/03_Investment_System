# Docs and AGENTS Cleanup Plan — 文档与 AGENTS 去重修正计划

## 1. 背景

本计划用于修正当前工作区中的文档职责重叠、入口索引缺失、旧 skill 名称残留和 Markdown 物理行过长问题。

当前问题不是“文档数量太多”，而是：

1. `AGENTS.md` 同时承担长期纪律、目录百科、skill 路由表、输出契约等职责。
2. README 与 charter / workflow docs / plans 重复描述阶段和结构。
3. `docs/index.md` 未完整覆盖当前 `docs/` 下新增目录与文件。
4. `docs/workflows/README.md` 未列出 `STOCK_REPORT_PRODUCTION_WORKFLOW.md`。
5. `STOCK_REPORT_PRODUCTION_WORKFLOW.md` 仍引用历史拆分 skill：`stock-research-analyst` 与 `stock-report-writer`。
6. 多个 Markdown 文件被压成极少物理行，不利于人工审阅、git diff、搜索和 parser 稳定性。

## 2. 修正目标

### 2.1 AGENTS.md 瘦身

将 `AGENTS.md` 限定为：

- repo-level 规则；
- evidence-first 纪律；
- no-advice 边界；
- 文档优先级；
- 关键文件归位；
- skill routing 摘要；
- completion gates。

不再把完整 workflow 阶段表、详细目录百科和长期计划全文塞入 `AGENTS.md`。

### 2.2 文档职责边界固化

新增 `docs/meta/DOC_OWNERSHIP_MATRIX.md`，明确：

- 哪个文件是主事实源；
- 哪个文件只是入口、计划、日志或 playbook；
- 重复内容应保留在哪里；
- 旧 skill 名称如何处理。

### 2.3 索引与 workflow 入口补齐

重写：

- `README.md`
- `docs/index.md`
- `docs/workflows/README.md`

使其覆盖当前已经存在的 `docs/codex_tasks/`、`docs/reporting/`、`docs/references/` 和 `STOCK_REPORT_PRODUCTION_WORKFLOW.md`。

### 2.4 个股报告 workflow 消除旧 skill 路由冲突

重写 `docs/workflows/STOCK_REPORT_PRODUCTION_WORKFLOW.md`，将默认主路由改为：

```text
research-orchestrator
→ evidence-ingest
→ stock-deep-dive
→ segment-company-mapping
→ quality-review
→ research-orchestrator close readout
```

历史名称 `stock-research-analyst` 和 `stock-report-writer` 默认视为待合并 / 待归档参考，不再作为默认路由入口。

## 3. 本补丁包包含的直接修改

```text
AGENTS.md
README.md
docs/index.md
docs/workflows/README.md
docs/workflows/STOCK_REPORT_PRODUCTION_WORKFLOW.md
docs/meta/DOC_OWNERSHIP_MATRIX.md
docs/plans/DOCS_AND_AGENTS_CLEANUP_PLAN.md
```

## 4. 本补丁包暂不直接删除的内容

本次不直接删除以下目录或文件：

```text
.agents/skills/stock-research-analyst/
.agents/skills/stock-report-writer/
docs/codex_tasks/TASK_05_REPORT_WRITER_AND_TEMPLATE.md
```

原因：

1. 这些文件可能仍含有可迁移到 `stock-deep-dive/references/` 的分析包、报告写作和质量检查细节。
2. 删除或归档旧 skill 属于 skill merge cleanup，应由 Codex 在单独任务中搜索引用、迁移有效内容后执行。
3. 当前 `.codex/config.toml` 未启用这两个旧 skill，因此可先通过文档路由规则防止误调用。

## 5. Codex 后续执行任务

### Task A：应用 replacement files

将补丁包中的 `replacement_files/` 按相同相对路径复制到仓库根目录。

### Task B：检查 Markdown 物理行

对长期文档执行物理行检查，优先修复：

```text
AGENTS.md
README.md
docs/index.md
docs/workflows/README.md
docs/workflows/STOCK_REPORT_PRODUCTION_WORKFLOW.md
docs/project/PROJECT_CHARTER.md
docs/architecture/WORKSPACE_STRUCTURE.md
docs/architecture/RESEARCH_OBJECT_MODEL.md
docs/policies/EVIDENCE_AND_CITATION_POLICY.md
docs/policies/QUALITY_GUARDRAILS.md
docs/playbooks/OPERATING_PLAYBOOK.md
```

验收：长期文档不应再被压成极少数超长物理行。

### Task C：链接和引用检查

检查：

1. `docs/index.md` 中的文件是否存在。
2. `docs/workflows/README.md` 的文件列表是否与实际目录一致。
3. `README.md` 中的入口是否能对应到实际文档。
4. 是否还有长期文档把 `stock-research-analyst` 或 `stock-report-writer` 当作默认路由。

### Task D：旧 skill cleanup 预检查

仅生成 readout，不直接删除：

```text
reports/p1_6/STOCK_SKILL_RETIREMENT_PRECHECK.md
```

需要回答：

- 旧 skill 目录是否仍被 `.codex/config.toml` 启用？
- 是否还有工作流事实源引用旧 skill？
- 哪些内容需要迁移到 `stock-deep-dive/references/`？
- 删除、归档或保留 disabled reference 的推荐方案是什么？

## 6. 验收标准

本轮 cleanup 完成后，应满足：

1. `AGENTS.md` 可快速读取，不再承担文档百科职责。
2. `docs/index.md` 覆盖当前关键目录和文件。
3. `docs/workflows/README.md` 列出全部当前 workflow fact source。
4. `STOCK_REPORT_PRODUCTION_WORKFLOW.md` 不再默认路由到旧拆分 skill。
5. 文档职责矩阵存在，并明确重复内容的唯一主事实源。
6. 长期文档的 Markdown 物理行可读，便于 diff 和人工审阅。
7. 旧 skill 是否删除被作为单独任务处理，不和本次文档 cleanup 混在一起。
