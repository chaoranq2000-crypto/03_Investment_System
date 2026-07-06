# TASK — 实现文档漂移检查脚本

## 任务目标

实现一个小型校验脚本，防止后续文档重新出现 workflow 事实多处定义。

目标文件：

```text
scripts/check_doc_drift.py
```

## 范围

脚本只做静态文本检查，不解析复杂 Markdown AST，不访问网络，不读取私有凭证。

## 检查项

### 1. 非 canonical workflow_type

允许的永久 workflow_type 只包括：

```text
segment_to_stock_closed_loop
stock_first_closed_loop
segment_stock_interlock
refresh_existing_research
comparison_readiness_gate
```

检查仓库中非历史目录下出现的：

```text
workflow_type:
```

若值不在允许列表，报错。

例外：

```text
docs/plans/**
docs/logs/**
docs/codex_tasks/**
reports/workflow_runs/**
```

### 2. stock_report_production 误用

如果 `workflow_type` 字段使用 `stock_report_production`，报错。

允许：

```text
profile_id: stock_report_production
```

### 3. Gate 编号漂移

`G0` 到 `G10` 的 global gate table 只能在：

```text
docs/workflows/RESEARCH_WORKFLOW.md
```

其他文件若出现 gate table 样式并定义 `G0`-`G10`，给 warning 或 error。

高于 `G10` 的 global gate 编号默认报错，除非出现在迁移说明或历史目录中。

### 4. SKILL.md 重定义禁区

所有 `.agents/skills/*/SKILL.md` 不应出现以下完整定义段落：

```text
## 永久工作流类型
## Workflow state 最小字段
## 质量门禁列表
```

出现则报 warning。

### 5. Markdown 长行提示

对长期文档检查超长物理行，例如 > 500 字符，给 warning。

不强制失败，但提示文件需要格式化。

## 输出格式

脚本输出 JSON 或 plain text 均可，但必须包含：

```text
errors: count
warnings: count
items:
  - severity
  - path
  - line
  - rule
  - message
```

## 退出码

```text
0 = no errors
1 = errors exist
```

Warnings 不导致非零退出。

## 验收命令

```bash
python scripts/check_doc_drift.py
```

在重构完成后的仓库中应返回：

```text
errors: 0
```

允许存在少量 Markdown long-line warnings，但应尽量减少。
