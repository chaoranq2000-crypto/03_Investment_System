# R5 Patch 2：segment-company-mapping validator 与 examples

## 背景

个股研究不能退化成孤立报告。R5 research pack 中的 `segment_exposure_pack` 必须能被 `segment-company-mapping` 接住。本 patch 做最小 exposure schema、example 和 validator。

## 目标

1. 明确 `segment_exposure.yaml` / `segment_company_exposure.csv` 字段契约。
2. 新增 exposure example。
3. 新增 `validate_segment_exposure.py`。
4. 新增 pytest，覆盖 exposure_type、score 证据、MISSING 规则、backflow decision。
5. 输出 readout。

## 允许修改文件

- `.agents/skills/segment-company-mapping/SKILL.md`
- `.agents/skills/segment-company-mapping/references/exposure_schema.md`
- `.agents/skills/segment-company-mapping/references/backflow_decision_rules.md`
- `.agents/skills/segment-company-mapping/assets/segment_exposure.example.yaml`
- `.agents/skills/segment-company-mapping/assets/segment_company_exposure.example.csv`
- `.agents/skills/segment-company-mapping/scripts/validate_segment_exposure.py`
- `tests/test_validate_segment_exposure.py`
- `reports/p1_6/R5_PATCH_2_SEGMENT_MAPPING_READOUT.md`

## 禁止事项

- 不更新真实 global exposure registry。
- 不把 product clue 升级为 revenue exposure。
- 不把公司整体收入/利润直接归因到某细分业务。
- 不生成个股报告。
- 不接真实 API。

## 交付物

- exposure schema。
- backflow decision rules。
- example YAML / CSV。
- validator。
- tests。
- readout。

## 验收标准

1. `exposure_type` 只允许：`revenue`、`profit`、`product_line_clue`、`customer_clue`、`order_clue`、`capacity_clue`、`technology_reserve`、`project_clue`、`narrative_only`。
2. `exposure_score` 必须为 0-5 整数。
3. score > 0 时必须有 `evidence_ids`、`claim_ids` 或 `missing_reason`。
4. `revenue_pct` / `profit_pct` 缺失时必须显式写 `MISSING_DISCLOSURE` 或 `NOT_DISCLOSED`。
5. 只存在 product clue 时，backflow decision 不得为 `update_revenue_exposure`。
6. backflow decision 枚举至少包括：`update_exposure`、`create_segment_candidate`、`no_backflow_needed`、`needs_review`、`blocked`。
7. pytest 通过。

## 测试命令

```bash
python .agents/skills/segment-company-mapping/scripts/validate_segment_exposure.py .agents/skills/segment-company-mapping/assets/segment_exposure.example.yaml
pytest tests/test_validate_segment_exposure.py
```

## 输出要求

1. 列出修改文件。
2. 粘贴测试结果。
3. 标出任何保留 TODO。
4. 输出 readout 文件。
