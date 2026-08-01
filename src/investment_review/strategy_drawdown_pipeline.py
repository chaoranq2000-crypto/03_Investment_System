"""P10 real-account drawdown validation pipeline.

The pipeline keeps the formal portfolio SQLite read-only.  It reconstructs
labelled account scenarios, runs the preregistered portfolio-level overlays,
and emits machine-readable evidence for a separately edited reader report.
It does not place orders or claim that the counterfactual fills really
occurred.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable, Mapping
from xml.sax.saxutils import escape

from .drawdown_validation import (
    DEFENSE_30_RULE,
    DailyBaseline,
    DrawdownRule,
    OverlayConfig,
    run_pre_registered_strategies,
    run_strategy,
)
from .strategy_account_reconstruction import (
    CashAnchor,
    ledger_cash_delta,
    open_formal_portfolio_read_only,
    reconstruct_account_history,
)


SCHEMA_VERSION = "investment_review.strategy_drawdown_pipeline.v1"


def _sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json_ready(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    return value


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_json_ready(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _account_reconstruction_summary(reconstruction: Any) -> dict[str, Any]:
    """Keep the committed evidence compact while preserving audit boundaries."""

    scenarios: list[dict[str, Any]] = []
    for scenario in reconstruction.scenarios:
        gap_counts = Counter(gap.code for row in scenario.daily for gap in row.gaps)
        fee_status_counts = Counter(row.fee_evidence_status for row in scenario.daily)

        def endpoint(row: Any) -> dict[str, Any]:
            return {
                "trade_date": row.trade_date,
                "cash": row.cash,
                "market_value": row.market_value,
                "nav": row.nav,
                "equity_exposure": row.equity_exposure,
            }

        scenarios.append(
            {
                "name": scenario.name,
                "epistemic_status": scenario.epistemic_status,
                "assumptions": scenario.assumptions,
                "cash_shift": scenario.cash_shift,
                "period": {
                    "start": scenario.daily[0].trade_date,
                    "end": scenario.daily[-1].trade_date,
                    "observation_count": len(scenario.daily),
                    "complete_nav_observation_count": sum(
                        row.nav is not None for row in scenario.daily
                    ),
                },
                "start_observation": endpoint(scenario.daily[0]),
                "end_observation": endpoint(scenario.daily[-1]),
                "gap_counts": dict(sorted(gap_counts.items())),
                "fee_status_counts": dict(sorted(fee_status_counts.items())),
                "diagnostics": asdict(scenario.diagnostics),
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_scope": (
            "compact_audit_and_scenario_summary; full daily marks are reproducible "
            "from the read-only source database and pipeline"
        ),
        "account_id": reconstruction.account_id,
        "cash_anchor": asdict(reconstruction.cash_anchor),
        "audit": asdict(reconstruction.audit),
        "scenarios": scenarios,
    }


def _scenario_observations(scenario: Any) -> tuple[list[DailyBaseline], float]:
    complete = [row for row in scenario.daily if row.nav is not None]
    if len(complete) < 2:
        raise ValueError("reconstruction scenario has fewer than two complete NAV observations")
    initial_nav = float(complete[0].nav)
    observations = [
        DailyBaseline(
            trade_date=row.trade_date,
            gross_return=float(row.daily_return),
            # Recorded ledger fees are already reflected in reconstructed NAV.
            # Only overlay turnover receives the simulated extra cost below.
            turnover=0.0,
        )
        for row in complete[1:]
        if row.daily_return is not None
    ]
    return observations, initial_nav


def _fee_profile(
    database_path: str | Path,
    account_id: str,
    cutoff_date: date,
) -> dict[str, float]:
    with open_formal_portfolio_read_only(database_path) as connection:
        row = connection.execute(
            """
            SELECT
                SUM(CASE WHEN event_type IN ('BUY','SELL')
                         THEN CAST(gross_amount AS REAL) ELSE 0 END) AS gross_turnover,
                SUM(CASE WHEN event_type IN ('BUY','SELL')
                         THEN CAST(fees AS REAL) ELSE 0 END) AS trade_fees,
                SUM(CASE WHEN event_type = 'CASH_FEE'
                         THEN CAST(cash_amount AS REAL) ELSE 0 END) AS cash_fees
            FROM ledger_entries WHERE account_id = ? AND event_date <= ?
            """,
            (account_id, cutoff_date.isoformat()),
        ).fetchone()
    gross = float(row["gross_turnover"] or 0.0)
    trade_fees = float(row["trade_fees"] or 0.0)
    cash_fees = float(row["cash_fees"] or 0.0)
    return {
        "gross_turnover": gross,
        "trade_fees": trade_fees,
        "cash_fees": cash_fees,
        "all_recorded_or_backfilled_fees": trade_fees + cash_fees,
        "observed_trade_fee_rate": trade_fees / gross if gross else 0.0,
    }


def _metric_row(result: Any) -> dict[str, Any]:
    metrics = asdict(result.metrics)
    metrics["worst_day"] = result.metrics.worst_day.isoformat()
    return {"strategy": result.rule.name, **metrics}


def _run_sensitivity(
    observations: list[DailyBaseline],
    *,
    initial_nav: float,
    fee_rate: float,
    shifted_observations: list[DailyBaseline],
    shifted_initial_nav: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def append_result(dimension: str, value: str, result: Any) -> None:
        rows.append({"dimension": dimension, "value": value, **_metric_row(result)})

    for slippage in (0.0, 10.0, 20.0):
        config = OverlayConfig(
            initial_nav=initial_nav,
            fee_rate=fee_rate,
            slippage_bps=slippage,
            execution_delay_days=2,
            cooldown_days=10,
            no_new_low_days=5,
            recovery_points=0.03,
        )
        append_result(
            "slippage_bps",
            format(slippage, ".0f"),
            run_strategy(observations, DEFENSE_30_RULE, config),
        )
    for delay in (1, 2, 3):
        config = OverlayConfig(
            initial_nav=initial_nav,
            fee_rate=fee_rate,
            slippage_bps=10.0,
            execution_delay_days=delay,
            cooldown_days=10,
            no_new_low_days=5,
            recovery_points=0.03,
        )
        append_result(
            "execution_delay_trading_days",
            str(delay),
            run_strategy(observations, DEFENSE_30_RULE, config),
        )
    for cooldown in (5, 10, 20):
        config = OverlayConfig(
            initial_nav=initial_nav,
            fee_rate=fee_rate,
            slippage_bps=10.0,
            execution_delay_days=2,
            cooldown_days=cooldown,
            no_new_low_days=5,
            recovery_points=0.03,
        )
        append_result(
            "cooldown_trading_days",
            str(cooldown),
            run_strategy(observations, DEFENSE_30_RULE, config),
        )
    for recovery in (0.02, 0.03, 0.05):
        config = OverlayConfig(
            initial_nav=initial_nav,
            fee_rate=fee_rate,
            slippage_bps=10.0,
            execution_delay_days=2,
            cooldown_days=10,
            no_new_low_days=5,
            recovery_points=recovery,
        )
        append_result(
            "recovery_points",
            format(recovery, ".2f"),
            run_strategy(observations, DEFENSE_30_RULE, config),
        )
    for shift in (-0.025, 0.0, 0.025):
        rule = DrawdownRule(
            f"defense_threshold_shift_{shift:+.3f}",
            tuple(value + shift for value in (0.20, 0.25, 0.30)),
            (1.0, 0.75, 0.50, 0.25),
        )
        config = OverlayConfig(
            initial_nav=initial_nav,
            fee_rate=fee_rate,
            slippage_bps=10.0,
            execution_delay_days=2,
            cooldown_days=10,
            no_new_low_days=5,
            recovery_points=0.03,
        )
        append_result(
            "threshold_shift_points",
            format(shift, "+.3f"),
            run_strategy(observations, rule, config),
        )
    shifted_config = OverlayConfig(
        initial_nav=shifted_initial_nav,
        fee_rate=fee_rate,
        slippage_bps=10.0,
        execution_delay_days=2,
        cooldown_days=10,
        no_new_low_days=5,
        recovery_points=0.03,
    )
    append_result(
        "cash_scenario",
        "minimum_nonnegative_constant_shift_not_fact",
        run_strategy(shifted_observations, DEFENSE_30_RULE, shifted_config),
    )
    return rows


def _drawdown_window(scenario: Any) -> dict[str, Any]:
    peak_nav = Decimal("0")
    peak_date: date | None = None
    worst_drawdown = Decimal("0")
    trough_date: date | None = None
    trough_nav: Decimal | None = None
    selected_peak: date | None = None
    for row in scenario.daily:
        if row.nav is None:
            continue
        if row.nav > peak_nav:
            peak_nav = row.nav
            peak_date = row.trade_date
        drawdown = Decimal("1") - row.nav / peak_nav
        if drawdown > worst_drawdown:
            worst_drawdown = drawdown
            trough_date = row.trade_date
            trough_nav = row.nav
            selected_peak = peak_date
    if selected_peak is None or trough_date is None or trough_nav is None:
        raise ValueError("unable to identify drawdown window")
    return {
        "peak_date": selected_peak,
        "peak_nav": peak_nav,
        "trough_date": trough_date,
        "trough_nav": trough_nav,
        "max_drawdown": worst_drawdown,
    }


def _drawdown_attribution(
    database_path: str | Path,
    *,
    account_id: str,
    start_exclusive: date,
    end_inclusive: date,
) -> list[dict[str, Any]]:
    with open_formal_portfolio_read_only(database_path) as connection:
        ledger = [
            dict(row)
            for row in connection.execute(
                """
                SELECT l.*, i.name AS instrument_name
                FROM ledger_entries AS l LEFT JOIN instruments AS i USING(ts_code)
                WHERE l.account_id = ? AND l.event_date <= ?
                ORDER BY l.event_date,
                         CASE WHEN l.event_time='' THEN '99:99:99' ELSE l.event_time END,
                         l.entry_id
                """,
                (account_id, end_inclusive.isoformat()),
            )
        ]
        prices = [
            dict(row)
            for row in connection.execute(
                """
                SELECT ts_code, trade_date, close
                FROM close_prices WHERE trade_date <= ?
                ORDER BY trade_date, fetched_at, observation_id
                """,
                (end_inclusive.isoformat(),),
            )
        ]
    events: dict[str, list[dict[str, Any]]] = defaultdict(list)
    marks: dict[str, dict[str, Decimal]] = defaultdict(dict)
    names: dict[str, str] = {}
    for row in ledger:
        events[str(row["event_date"])].append(row)
        names[str(row["ts_code"])] = str(row.get("instrument_name") or row["ts_code"])
    for row in prices:
        marks[str(row["trade_date"])][str(row["ts_code"])] = Decimal(str(row["close"]))
    calendar = sorted(set(events) | set(marks))
    holdings: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    last_prices: dict[str, Decimal] = {}
    contributions: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for raw_day in calendar:
        day = date.fromisoformat(raw_day)
        prior_values = {
            code: quantity * last_prices[code]
            for code, quantity in holdings.items()
            if quantity and code in last_prices
        }
        last_prices.update(marks.get(raw_day, {}))
        cash_by_code: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        for row in events.get(raw_day, []):
            code = str(row["ts_code"])
            event_type = str(row["event_type"]).upper()
            quantity = Decimal(str(row["quantity"] or "0"))
            if event_type in {"OPENING", "BUY"}:
                holdings[code] += quantity
            elif event_type == "SELL":
                holdings[code] -= quantity
            cash_by_code[code] += ledger_cash_delta(
                event_type,
                gross_amount=row.get("gross_amount"),
                fees=row.get("fees"),
                cash_amount=row.get("cash_amount"),
            )
            if code not in last_prices and Decimal(str(row.get("price") or "0")) > 0:
                last_prices[code] = Decimal(str(row["price"]))
        end_values = {
            code: quantity * last_prices[code]
            for code, quantity in holdings.items()
            if quantity and code in last_prices
        }
        if start_exclusive < day <= end_inclusive:
            for code in set(prior_values) | set(end_values) | set(cash_by_code):
                contributions[code] += (
                    end_values.get(code, Decimal("0"))
                    - prior_values.get(code, Decimal("0"))
                    + cash_by_code.get(code, Decimal("0"))
                )
        if day >= end_inclusive:
            break
    return [
        {
            "ts_code": code,
            "instrument_name": names.get(code, code),
            "nav_contribution_cny": value,
        }
        for code, value in sorted(contributions.items(), key=lambda item: item[1])
    ]


def _concentration_snapshot(scenario: Any, target: date) -> dict[str, Any]:
    row = next(item for item in scenario.daily if item.trade_date == target)
    if row.nav is None:
        raise ValueError(f"NAV is unavailable on {target}")
    positions = sorted(
        (
            {
                "ts_code": mark.ts_code,
                "instrument_name": mark.instrument_name,
                "market_value": mark.market_value,
                "weight": mark.market_value / row.nav,
            }
            for mark in row.price_marks
            if mark.market_value is not None and mark.quantity > 0
        ),
        key=lambda item: item["market_value"],
        reverse=True,
    )
    return {
        "trade_date": target,
        "nav": row.nav,
        "cash": row.cash,
        "cash_weight": row.cash / row.nav,
        "position_count": len(positions),
        "positions_over_5pct": sum(item["weight"] >= Decimal("0.05") for item in positions),
        "top1_weight": positions[0]["weight"] if positions else Decimal("0"),
        "top3_weight": sum((item["weight"] for item in positions[:3]), Decimal("0")),
        "top_positions": positions[:8],
    }


def _load_market_context(
    artifact_path: str | Path | None,
    *,
    dates: Iterable[date],
) -> dict[str, Any]:
    if artifact_path is None:
        return {"status": "not_supplied", "indices": [], "instrument_gaps": []}
    artifact_file = Path(artifact_path)
    payload = json.loads(artifact_file.read_text(encoding="utf-8"))
    wanted = {item.isoformat() for item in dates}
    indices: list[dict[str, Any]] = []
    for item in payload.get("indices", []):
        bars = {str(row["trade_date"]): row for row in item.get("bars", [])}
        selected = {key: bars[key]["close"] for key in sorted(wanted & set(bars))}
        indices.append(
            {
                "index": item.get("index"),
                "status": item.get("status"),
                "selected_closes": selected,
                "attempts": item.get("attempts", []),
            }
        )
    gap_codes = {"551550.SH", "127113.SZ"}
    gaps: list[dict[str, Any]] = []
    for item in payload.get("instruments", []):
        instrument = item.get("instrument") or {}
        if instrument.get("ts_code") not in gap_codes:
            continue
        bars = item.get("bars", [])
        gaps.append(
            {
                "instrument": instrument,
                "status": item.get("status"),
                "first_market_date": bars[0]["trade_date"] if bars else None,
                "selected_bars": [
                    row
                    for row in bars
                    if row.get("trade_date")
                    in {"2025-07-21", "2025-07-22", "2026-03-30", "2026-03-31"}
                ],
                "attempts": item.get("attempts", []),
            }
        )
    return {
        "status": "loaded",
        "artifact_path": str(artifact_file),
        "artifact_sha256": _sha256_file(artifact_file),
        "payload_sha256": payload.get("payload_sha256"),
        "coverage": payload.get("coverage"),
        "indices": indices,
        "instrument_gaps": gaps,
    }


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(_json_ready(row))


def _write_nav_path_svg(path: Path, results: Iterable[Any]) -> None:
    """Write a dependency-free comparison chart for the three NAV paths."""

    strategies = list(results)
    if not strategies or not strategies[0].daily:
        raise ValueError("strategy results are empty")
    dates = [row.trade_date for row in strategies[0].daily]
    if any([row.trade_date for row in result.daily] != dates for result in strategies):
        raise ValueError("strategy date grids differ")

    values = [row.nav for result in strategies for row in result.daily]
    low = min(values)
    high = max(values)
    padding = max((high - low) * 0.08, 1.0)
    low -= padding
    high += padding

    width, height = 1200, 640
    left, right, top, bottom = 92, 38, 74, 72
    plot_width = width - left - right
    plot_height = height - top - bottom

    def x_at(index: int) -> float:
        return left + plot_width * index / max(len(dates) - 1, 1)

    def y_at(value: float) -> float:
        return top + plot_height * (high - value) / (high - low)

    colors = {
        "baseline": "#111827",
        "defense_30": "#d97706",
        "elastic_35": "#2563eb",
    }
    dashes = {"baseline": "", "defense_30": "", "elastic_35": "8 6"}
    labels = {
        "baseline": "实际基线",
        "defense_30": "20%-25%防御 / 30%红区",
        "elastic_35": "25%防御 / 35%失效",
    }
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="92" y="38" font-family="Microsoft YaHei, sans-serif" '
        'font-size="22" font-weight="700" fill="#111827">P10 条件净值路径比较</text>',
        '<text x="92" y="60" font-family="Microsoft YaHei, sans-serif" '
        'font-size="12" fill="#6b7280">收盘信号在下一交易日收盘执行；基线已含账本手续费，覆盖层另计模拟成本</text>',
    ]
    for tick in range(6):
        value = low + (high - low) * tick / 5
        y = y_at(value)
        parts.append(
            f'<line x1="{left}" y1="{y:.2f}" x2="{width - right}" y2="{y:.2f}" '
            'stroke="#e5e7eb" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{left - 10}" y="{y + 4:.2f}" text-anchor="end" '
            'font-family="Arial, sans-serif" font-size="11" fill="#6b7280">'
            f"{value / 10000:.1f}万</text>"
        )
    tick_indices = sorted(
        {0, len(dates) // 4, len(dates) // 2, 3 * len(dates) // 4, len(dates) - 1}
    )
    for index in tick_indices:
        x = x_at(index)
        parts.append(
            f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{height - bottom}" '
            'stroke="#f3f4f6" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{x:.2f}" y="{height - bottom + 24}" text-anchor="middle" '
            'font-family="Arial, sans-serif" font-size="11" fill="#6b7280">'
            f"{dates[index].isoformat()}</text>"
        )

    for result in strategies:
        name = result.rule.name
        points = " ".join(
            f"{x_at(index):.2f},{y_at(row.nav):.2f}" for index, row in enumerate(result.daily)
        )
        dash = f' stroke-dasharray="{dashes.get(name, "")}"' if dashes.get(name) else ""
        parts.append(
            f'<polyline points="{points}" fill="none" stroke="{colors.get(name, "#6b7280")}" '
            f'stroke-width="2.2" stroke-linejoin="round" stroke-linecap="round"{dash}/>'
        )

    for label_index, (signal_date, text_label) in enumerate(
        (
            (date(2026, 6, 8), "减仓信号 6/8 → 6/9 收盘执行"),
            (date(2026, 6, 23), "恢复信号 6/23 → 6/24 收盘执行"),
        )
    ):
        if signal_date not in dates:
            continue
        x = x_at(dates.index(signal_date))
        parts.append(
            f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{height - bottom}" '
            'stroke="#dc2626" stroke-width="1.2" stroke-dasharray="4 4"/>'
        )
        parts.append(
            f'<text x="{x - 5:.2f}" y="{top + 18 + label_index * 18}" text-anchor="end" '
            'font-family="Microsoft YaHei, sans-serif" '
            f'font-size="11" fill="#b91c1c">{escape(text_label)}</text>'
        )

    legend_x = left
    legend_y = height - 22
    for index, result in enumerate(strategies):
        name = result.rule.name
        x = legend_x + index * 300
        dash = f' stroke-dasharray="{dashes.get(name, "")}"' if dashes.get(name) else ""
        parts.append(
            f'<line x1="{x}" y1="{legend_y}" x2="{x + 34}" y2="{legend_y}" '
            f'stroke="{colors.get(name, "#6b7280")}" stroke-width="3"{dash}/>'
        )
        parts.append(
            f'<text x="{x + 44}" y="{legend_y + 4}" font-family="Microsoft YaHei, sans-serif" '
            f'font-size="12" fill="#374151">{escape(labels.get(name, name))}</text>'
        )
    parts.append("</svg>")
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def run_pipeline(
    *,
    database_path: str | Path,
    output_dir: str | Path,
    market_artifact: str | Path | None = None,
    account_id: str = "default",
    end_date: date = date(2026, 7, 16),
) -> dict[str, Any]:
    database = Path(database_path).resolve(strict=True)
    destination = Path(output_dir).resolve()
    before_hash = _sha256_file(database)
    anchor = CashAnchor(
        date(2026, 7, 14),
        Decimal("11357"),
        source_ref="portfolio.sqlite3#cash_balance_snapshots:2026-07-14_user_provided",
    )
    reconstruction = reconstruct_account_history(
        database,
        account_id=account_id,
        cash_anchor=anchor,
        constant_cash_shift=Decimal("6736.29"),
        trusted_window_start=date(2026, 7, 14),
        trusted_window_end=end_date,
        end_date=end_date,
        allow_subscription_cost_proxy=True,
    )
    anchored = reconstruction.by_name("anchored_raw")
    shifted = reconstruction.by_name("constant_cash_shift")
    observations, initial_nav = _scenario_observations(anchored)
    shifted_observations, shifted_initial_nav = _scenario_observations(shifted)
    fee_profile = _fee_profile(database, account_id, end_date)
    config = OverlayConfig(
        initial_nav=initial_nav,
        # A close-only baseline cannot separate the overnight return from the
        # next session's open-to-close return.  Applying the exposure from the
        # following close-to-close interval is the strict causal proxy: signal
        # after t close, execute at t+1 close, effect from t+1 to t+2.
        execution_delay_days=2,
        fee_rate=fee_profile["observed_trade_fee_rate"],
        slippage_bps=10.0,
        cooldown_days=10,
        no_new_low_days=5,
        recovery_points=0.03,
    )
    comparison = run_pre_registered_strategies(observations, config)
    comparison_rows = [_metric_row(result) for result in comparison.results]
    sensitivity = _run_sensitivity(
        observations,
        initial_nav=initial_nav,
        fee_rate=fee_profile["observed_trade_fee_rate"],
        shifted_observations=shifted_observations,
        shifted_initial_nav=shifted_initial_nav,
    )
    window = _drawdown_window(anchored)
    attribution = _drawdown_attribution(
        database,
        account_id=account_id,
        start_exclusive=window["peak_date"],
        end_inclusive=window["trough_date"],
    )
    concentration = {
        "peak": _concentration_snapshot(anchored, window["peak_date"]),
        "trough": _concentration_snapshot(anchored, window["trough_date"]),
    }
    market_context = _load_market_context(
        market_artifact,
        dates=(
            window["peak_date"],
            window["trough_date"],
            date(2026, 6, 23),
            end_date,
        ),
    )
    after_hash = _sha256_file(database)
    if before_hash != after_hash:
        raise RuntimeError("formal portfolio database changed during P10 pipeline")

    destination.mkdir(parents=True, exist_ok=True)
    _write_json(
        destination / "account_reconstruction_summary.json",
        _account_reconstruction_summary(reconstruction),
    )
    _write_json(
        destination / "strategy_comparison.json",
        {
            "schema_version": SCHEMA_VERSION,
            "epistemic_status": "conditional_counterfactual_not_actual_trade_history",
            "execution_assumption": (
                "signal_after_t_close_execute_at_t_plus_1_close_"
                "exposure_affects_t_plus_2_close_to_close_return"
            ),
            "config": asdict(config),
            "fee_profile": fee_profile,
            "results": [result.to_dict() for result in comparison.results],
        },
    )
    _write_json(destination / "sensitivity_analysis.json", sensitivity)
    _write_json(destination / "market_context.json", market_context)
    _write_json(
        destination / "drawdown_diagnostics.json",
        {
            "window": window,
            "concentration": concentration,
            "attribution_total_cny": sum(
                (item["nav_contribution_cny"] for item in attribution), Decimal("0")
            ),
            "attribution": attribution,
        },
    )

    baseline_rows = []
    for row in anchored.daily:
        baseline_rows.append(
            {
                "trade_date": row.trade_date,
                "cash": row.cash,
                "market_value": row.market_value,
                "nav": row.nav,
                "daily_return": row.daily_return,
                "equity_exposure": row.equity_exposure,
                "gross_trade_amount": row.gross_trade_amount,
                "ledger_fees_used_in_cash": row.ledger_fees_used_in_cash,
                "fee_evidence_status": row.fee_evidence_status,
                "gap_codes": ";".join(sorted({gap.code for gap in row.gaps})),
            }
        )
    _write_csv(
        destination / "baseline_daily.csv",
        baseline_rows,
        [
            "trade_date",
            "cash",
            "market_value",
            "nav",
            "daily_return",
            "equity_exposure",
            "gross_trade_amount",
            "ledger_fees_used_in_cash",
            "fee_evidence_status",
            "gap_codes",
        ],
    )
    _write_csv(
        destination / "strategy_comparison.csv",
        comparison_rows,
        [
            "strategy",
            "initial_nav",
            "final_nav",
            "net_total_return",
            "net_cagr",
            "max_drawdown",
            "calmar",
            "longest_underwater_days",
            "longest_completed_recovery_days",
            "current_underwater_days",
            "unrecovered",
            "upside_participation",
            "overlay_turnover",
            "total_transaction_cost",
            "trigger_count",
            "de_risk_trigger_count",
            "re_risk_trigger_count",
            "average_exposure",
            "worst_daily_return",
            "worst_day",
        ],
    )
    signal_rows: list[dict[str, Any]] = []
    path_by_date: dict[str, dict[str, Any]] = {}
    for result in comparison.results:
        for row_index, row in enumerate(result.daily):
            date_key = row.trade_date.isoformat()
            path_by_date.setdefault(date_key, {"trade_date": date_key})[
                f"{result.rule.name}_nav"
            ] = row.nav
            if row.signal_event:
                first_return_effect_date = next(
                    (
                        future.trade_date
                        for future in result.daily[row_index + 1 :]
                        if abs(future.applied_exposure - row.signal_exposure) < 1e-12
                    ),
                    None,
                )
                next_trading_day = (
                    result.daily[row_index + 1].trade_date
                    if row_index + 1 < len(result.daily)
                    else None
                )
                signal_rows.append(
                    {
                        "strategy": result.rule.name,
                        "signal_date": row.trade_date,
                        "signal_event": row.signal_event,
                        "signal_exposure": row.signal_exposure,
                        "applied_exposure_same_day": row.applied_exposure,
                        "next_trading_day_execution_proxy": next_trading_day,
                        "first_return_effect_date": first_return_effect_date,
                        "drawdown_at_signal": row.drawdown,
                    }
                )
    _write_csv(
        destination / "signal_ledger.csv",
        signal_rows,
        [
            "strategy",
            "signal_date",
            "signal_event",
            "signal_exposure",
            "applied_exposure_same_day",
            "next_trading_day_execution_proxy",
            "first_return_effect_date",
            "drawdown_at_signal",
        ],
    )
    _write_csv(
        destination / "nav_paths.csv",
        [path_by_date[key] for key in sorted(path_by_date)],
        ["trade_date", "baseline_nav", "defense_30_nav", "elastic_35_nav"],
    )
    _write_nav_path_svg(destination / "nav_paths.svg", comparison.results)
    _write_csv(
        destination / "drawdown_attribution.csv",
        attribution,
        ["ts_code", "instrument_name", "nav_contribution_cny"],
    )
    _write_csv(
        destination / "sensitivity_analysis.csv",
        sensitivity,
        [
            "dimension",
            "value",
            "strategy",
            "final_nav",
            "net_cagr",
            "max_drawdown",
            "calmar",
            "upside_participation",
            "overlay_turnover",
            "total_transaction_cost",
            "trigger_count",
            "average_exposure",
        ],
    )
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "formal_portfolio_db": {
            "path": str(database),
            "sha256_before": before_hash,
            "sha256_after": after_hash,
            "unchanged": before_hash == after_hash,
            "access": reconstruction.audit.source_access,
        },
        "account_id": account_id,
        "period": {
            "start": anchored.daily[0].trade_date,
            "end": anchored.daily[-1].trade_date,
            "performance_status": "conditional_due_to_cash_and_price_gaps",
        },
        "time_boundary": {
            "signal_information": "trade_date close and earlier only",
            "execution_proxy": "next trading day close",
            "first_affected_return": "subsequent close-to-close interval",
            "one_day_delay_variant": "reported only as an optimistic sensitivity",
        },
        "cash_anchor": asdict(anchor),
        "market_cache": market_context,
        "outputs": sorted(path.name for path in destination.iterdir() if path.is_file()),
        "orders_executed": False,
        "guaranteed_return_claims": False,
    }
    _write_json(destination / "input_manifest.json", manifest)
    return {
        "output_dir": str(destination),
        "formal_db_sha256": before_hash,
        "comparison": comparison_rows,
        "drawdown_window": _json_ready(window),
        "attribution": _json_ready(attribution),
        "concentration": _json_ready(concentration),
        "market_context": market_context,
        "sensitivity": sensitivity,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run P10 conditional drawdown validation")
    parser.add_argument("--database", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--market-artifact")
    parser.add_argument("--account-id", default="default")
    parser.add_argument("--end-date", default="2026-07-16")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = run_pipeline(
        database_path=args.database,
        output_dir=args.output_dir,
        market_artifact=args.market_artifact,
        account_id=args.account_id,
        end_date=date.fromisoformat(args.end_date),
    )
    print(json.dumps(_json_ready(result), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
