# Quality Gate Report

final_status: accepted
high_issues: 0
medium_issues: 0

| gate | status | evidence |
|---|---|---|
| G-DL1 Source Permission | pass | `data_layer_quality_report.md` |
| G-DL2 Raw Archive | pass | `raw/` snapshots and `evidence_manifest.csv` |
| G-DL3 Reproducibility | pass | `api_params_hash` present in manifest |
| G-DL4 Field Schema | pass | `normalized/` tables |
| G-DL5 Metric-only Boundary | pass | no claim candidates generated |
| G-DL6 Freshness | pass | valuation snapshot has as_of_date |
| G-DL7 License / Token | pass | no token value detected |
| G-DL8 Pack Completeness | pass | financial, valuation, technical and source gap packs present |
