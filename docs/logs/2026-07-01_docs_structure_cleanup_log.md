# 2026-07-01 Docs Structure Cleanup Log

- date: 2026-07-01
- scope: docs_structure
- status: PASS
- log_type: cleanup_log

## 1. Summary

本次整理将计划文件、计划完成情况日志和 P0 阶段记录重新归位，目标是降低目录污染和后续误放文件的风险。

## 2. Changes

| Area | Result |
|---|---|
| `docs/plans/` | 仅保留计划模板、验收清单和计划正文 |
| `docs/logs/` | 作为与 `docs/plans/` 平行的统一日志目录 |
| `docs/logs/p0/` | 存放 P0 前置确认、smoke test 和 closeout |
| `docs/logs/README.md` | 新增日志命名规则，后续日志按 `YYYY-MM-DD_<scope>_<log_type>.md` 命名 |

## 3. Pollution Check

| Item | Finding | Handling |
|---|---|---|
| `docs/p0/` | 已不作为日志位置使用，当前路径不存在 | 无需迁移更多文件 |
| `docs/plans/logs/` | 已不作为日志位置使用，当前路径不存在 | 无需迁移更多文件 |
| `.conda/` | 本地 conda 环境目录，已被 `.gitignore` 忽略 | 保留为本地运行环境 |
| `.pytest_cache/` | pytest 本地缓存，已被 `.gitignore` 忽略 | 不纳入正式文档体系 |
| `.env.local` | 本地密钥配置，已被 `.gitignore` 忽略 | 不纳入 Git |
| `__pycache__/` | Python 缓存，已被 `.gitignore` 忽略 | 不纳入 Git |
| `project_journal/` | 用户已手动删除 | 不恢复，不纳入本轮污染风险 |

## 4. Verification

- 旧路径扫描目标：`docs/p0`、`docs/plans/logs`、旧 P0 日志文件名。
- 新路径检查目标：`docs/logs/README.md`、`docs/logs/2026-07-01_docs_structure_cleanup_log.md`、`docs/logs/p0/2026-07-01_*`。
- 日志命名检查：`docs/logs/**/*.md` 除 `README.md` 外均符合 `YYYY-MM-DD_<scope>_<log_type>.md`。
- 忽略检查：`.env.local`、`.conda/`、`.pytest_cache/`、`__pycache__/` 和本地 Tushare PDF 均被 `.gitignore` 命中。
- 测试命令：`conda run -p .\.conda\investment-system python -m pytest -q`。
- 测试结果：`23 passed`。

## 5. Open Risks

- 当前 Git 状态会显示历史文件删除与新路径新增；提交前需要确认这些是预期移动。
- Windows 大小写路径变更可能需要在暂存时额外确认。
