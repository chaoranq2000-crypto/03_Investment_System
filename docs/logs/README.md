# Logs README — 日志命名规则

## 1. 适用范围

`docs/logs/` 只存放项目建设、计划完成情况、阶段验收、closeout、结构审计和复盘日志。

不要把计划正文、模板、研究报告、证据文件或运行缓存放入 `docs/logs/`。

## 2. 命名规则

所有新增日志统一使用：

```text
YYYY-MM-DD_<scope>_<log_type>.md
```

字段说明：

| 字段 | 规则 | 示例 |
|---|---|---|
| `YYYY-MM-DD` | 日志记录日期，使用北京时间日期 | `2026-07-01` |
| `scope` | 阶段、模块或事项，英文小写 `snake_case` | `p0`, `docs_structure`, `p1_5` |
| `log_type` | 日志类型，英文小写 `snake_case` | `closeout`, `smoke_test`, `plan_completion_log`, `cleanup_log` |

示例：

```text
docs/logs/2026-07-01_plan_completion_log.md
docs/logs/2026-07-01_docs_structure_cleanup_log.md
docs/logs/p0/2026-07-01_p0_smoke_test.md
docs/logs/p0/2026-07-01_p0_closeout.md
```

## 3. 子目录规则

- 跨阶段或项目级日志放在 `docs/logs/`。
- 阶段内记录放在 `docs/logs/<stage_id>/`。
- 子目录名使用英文小写 `snake_case`。
- 不再使用 `docs/p0/` 或 `docs/plans/logs/` 存放日志。

## 4. 内容要求

日志应至少包含：

- date
- scope
- status
- changed_paths
- verification
- open_risks

如涉及研究内容，仍需遵守证据优先和不输出直接交易建议的边界。
