from __future__ import annotations

import json
import re
from pathlib import Path

from src.investment_review.periodic_reports import build_recommendation


ROOT = Path(__file__).resolve().parents[1]
CHARTER_PATH = Path(
    "docs/policies/PERSONAL_HIGH_RISK_EQUITY_STRATEGY_CHARTER.md"
)
P10_PATH = Path("reports/investment_review/periodic_v1/strategy_drawdown_validation")


def _read(relative_path: Path | str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def _extreme_exposure_snapshot() -> dict[str, object]:
    return {
        "cash": {},
        "cash_weight_pct": "0",
        "top_position_weight_pct": "100",
        "top3_weight_pct": "100",
        "positions": [
            {
                "ts_code": "000001.SZ",
                "portfolio_weight_pct": "100",
                "close_cny": "10",
                "average_cost_cny": "10",
                "price_date": "2026-08-20",
                "source_refs": ["test_fixture:extreme_exposure"],
            }
        ],
    }


def _assert_observation_only_without_actions(
    recommendation: dict[str, object],
) -> None:
    assert recommendation["mode"] == "observation_only"
    assert recommendation["decision_basis"] is None
    assert recommendation["user_risk_budget"] is None
    assert recommendation["action"] is None
    assert recommendation["target_position"] is None
    assert recommendation["orders_executed"] is False


def test_charter_is_the_formal_ten_principle_human_policy() -> None:
    charter = _read(CHARTER_PATH)

    assert "- 状态：正式建立" in charter
    assert "- 生效日期：2026-08-08" in charter
    assert re.findall(r"^### (\d+)\. ", charter, flags=re.MULTILINE) == [
        str(index) for index in range(1, 11)
    ]
    assert "不是覆盖所有市场情形的机械操作手册" in charter
    assert "不得为了追求目标收益而反向确定必须承受的回撤" in charter
    assert "v0.1 不设置机械化的仓位、回撤、估值、趋势或流动性参数" in charter
    assert "生存状态不自动要求清空组合" in charter
    assert "不以单一价格跌幅或单日市场波动机械触发" in charter


def test_authority_chain_keeps_c_human_005_pending_and_non_executable() -> None:
    authority_files = [
        Path("AGENTS.md"),
        Path(".agents/skills/investment-review/SKILL.md"),
    ]
    for path in authority_files:
        text = _read(path)
        assert CHARTER_PATH.as_posix() in text
        assert "`C-HUMAN-005` remains `pending`" in text
        assert "effective machine value is `null`" in text
        assert "`proposed_not_active`" in text

    ownership = _read("docs/meta/DOC_OWNERSHIP_MATRIX.md")
    index = _read("docs/index.md")
    assert CHARTER_PATH.as_posix() in ownership
    assert CHARTER_PATH.name in index
    assert "机器 schema、固定参数、自动动作或 P10 建议阈值" in ownership


def test_historical_p10_proposal_remains_non_active_and_unselected() -> None:
    proposal = _read(P10_PATH / "personal_concentrated_strategy_principles_v0.1.md")
    summary = json.loads(_read(P10_PATH / "validation_summary.json"))

    assert "`proposed_not_active`" in proposal
    assert summary["criteria"]["C-HUMAN-005"] == "pending_user_choice"
    assert summary["conclusion"]["supports_routine_35pct_drawdown_budget"] is False
    assert summary["conclusion"]["supports_mechanical_20pct_derisk"] is False
    assert summary["conclusion"]["proves_30pct_is_optimal"] is False
    assert summary["conclusion"]["caps_drawdown_at_30_or_35pct"] is False


def test_missing_current_risk_input_blocks_advice_even_at_extreme_exposure() -> None:
    snapshot = _extreme_exposure_snapshot()
    incomplete_policies = [
        (
            {
                "risk_budget": "用户明确的定性风险预算",
                "target_position_range_pct": ["10", "20"],
            },
            "MISSING_EXPLICIT_USER_TIME_HORIZON",
        ),
        (
            {
                "time_horizon": "未来十二个月",
                "target_position_range_pct": ["10", "20"],
            },
            "MISSING_EXPLICIT_USER_RISK_BUDGET",
        ),
    ]

    for risk_policy, expected_missing_input in incomplete_policies:
        recommendation = build_recommendation(
            subject_type="instrument",
            subject_id="000001.SZ",
            snapshot=snapshot,
            report_cutoff_at="2026-08-20T15:00:00+08:00",
            review_mode="advice",
            risk_policy=risk_policy,
        )

        _assert_observation_only_without_actions(recommendation)
        assert expected_missing_input in recommendation["important_missing_inputs"]


def test_complete_risk_inputs_do_not_authorize_advice_without_explicit_request() -> None:
    recommendation = build_recommendation(
        subject_type="instrument",
        subject_id="000001.SZ",
        snapshot=_extreme_exposure_snapshot(),
        report_cutoff_at="2026-08-20T15:00:00+08:00",
        risk_policy={
            "time_horizon": "未来十二个月",
            "risk_budget": "用户明确的定性风险预算",
            "target_position_range_pct": ["10", "20"],
        },
    )

    _assert_observation_only_without_actions(recommendation)
    assert "MISSING_EXPLICIT_USER_REVIEW_MODE" in (
        recommendation["important_missing_inputs"]
    )


def test_missing_position_constraint_does_not_inject_a_default_threshold() -> None:
    recommendation = build_recommendation(
        subject_type="instrument",
        subject_id="000001.SZ",
        snapshot=_extreme_exposure_snapshot(),
        report_cutoff_at="2026-08-20T15:00:00+08:00",
        review_mode="advice",
        risk_policy={
            "time_horizon": "未来十二个月",
            "risk_budget": "用户明确的定性风险预算",
            "c_human_005": None,
            "drawdown_thresholds_pct": ["20", "25", "30", "35"],
            "source_status": "proposed_not_active",
        },
    )

    _assert_observation_only_without_actions(recommendation)
    assert "MISSING_EXPLICIT_USER_RISK_POLICY" in (
        recommendation["important_missing_inputs"]
    )
