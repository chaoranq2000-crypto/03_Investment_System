# Company Valuation Subagent Integration Readout

status: accepted

## Scope

本次只完成 `company-valuation` sub-skill 与 `stock-deep-dive` 的集成契约收口；未重写 `.agents/skills/company-valuation/` 下已新增文件，未修改全局 workflow gate。

## Checks

- `.codex/config.toml` already enables `.agents/skills/company-valuation`.
- `stock-deep-dive/SKILL.md` includes `SDD-2.5 Valuation subagent handoff`, requires `valuation_request.yaml`, calls `company-valuation`, and collects the seven valuation artifacts.
- `report_production_profile.md` keeps RP6 inside the existing workflow while splitting ownership: `stock-deep-dive` prepares forecast/request, `company-valuation` produces valuation artifacts, and RP8 consumes them.
- `forecast_valuation_contract.md` now exposes the required company-valuation handoff fields and keeps prohibited outputs.
- `analysis_pack_contract.md` and `stock_analysis_pack_template.yaml` now include valuation artifact paths, quality handoff fields, open gaps, and no-advice boundary fields.
- `quality-review/SKILL.md` already contains local `QR-VAL-*` checks and does not introduce new global G IDs.

## Boundary

Valuation conclusions remain `estimate`, `inference`, or `analyst_view`; they are not facts, not business exposure proof, and not buy / sell / hold, target-price, or position-sizing instructions.
