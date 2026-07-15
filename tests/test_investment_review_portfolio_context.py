from __future__ import annotations

import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from src.investment_review.models import DecisionRecord, ModelValidationError, SourceDefinition
from src.investment_review.portfolio_context import (
    PortfolioContext,
    PortfolioSnapshot,
    calculate_portfolio_metrics,
    deterministic_context_json,
    render_portfolio_context_markdown,
    snapshot_document,
)
from src.investment_review.store import DataConflictError, ReviewStore


class PortfolioContextTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = SourceDefinition(
            name="synthetic-reviewed-portfolio",
            kind="json_snapshot",
            uri="tests/fixtures/synthetic-portfolio.json",
            identity_key="synthetic-account-A",
            read_only=True,
        )

    def _snapshot(
        self,
        *,
        observed_at: str = "2026-07-15 09:59:00",
        known_at: str = "2026-07-15 09:59:30",
        cash: str = "1000",
        total_assets: str = "1000",
        nav: str = "1000",
        financing: str = "0",
        positions: list[dict] | None = None,
        snapshot_id: str | None = None,
    ) -> PortfolioSnapshot:
        return PortfolioSnapshot.from_dict(
            {
                "snapshot_id": snapshot_id,
                "source_path": "tests/fixtures/synthetic-portfolio.json#row=1",
                "observed_at": observed_at,
                "known_at": known_at,
                "cash": cash,
                "total_assets": total_assets,
                "net_asset_value": nav,
                "financing": financing,
                "base_currency": "CNY",
                "positions": positions or [],
            },
            default_source_id=self.source.source_id,
        )

    def test_empty_and_all_cash_portfolios_are_defined(self) -> None:
        metrics = calculate_portfolio_metrics(self._snapshot())
        self.assertEqual(metrics["cash_ratio"], "1")
        self.assertEqual(metrics["gross_exposure"], "0")
        self.assertEqual(metrics["net_exposure"], "0")
        self.assertEqual(metrics["top1_concentration"], "0")
        self.assertEqual(metrics["top5_concentration"], "0")
        self.assertEqual(metrics["hhi_concentration"], "0")
        self.assertEqual(metrics["data_quality_flags"], [])

    def test_single_and_multiple_positions_have_stable_concentration(self) -> None:
        single = self._snapshot(
            cash="0",
            positions=[
                {"symbol": "600000.SH", "quantity": "100", "price": "10", "industry": "银行"}
            ],
        )
        single_metrics = calculate_portfolio_metrics(single)
        self.assertEqual(single_metrics["top1_concentration"], "1")
        self.assertEqual(single_metrics["hhi_concentration"], "1")

        multiple = self._snapshot(
            cash="0",
            positions=[
                {"symbol": "A", "quantity": "5", "price": "100", "industry": "I1"},
                {"symbol": "B", "quantity": "3", "price": "100", "industry": "I1"},
                {"symbol": "C", "quantity": "2", "price": "100", "industry": "I2"},
            ],
        )
        metrics = calculate_portfolio_metrics(multiple)
        self.assertEqual(metrics["top1_concentration"], "0.5")
        self.assertEqual(metrics["top5_concentration"], "1")
        self.assertEqual(metrics["hhi_concentration"], "0.38")
        self.assertEqual(metrics["industry_exposure"]["I1"]["net_ratio"], "0.8")

    def test_long_short_gross_and_net_exposure_are_separate(self) -> None:
        snapshot = self._snapshot(
            cash="600",
            positions=[
                {"symbol": "LONG", "quantity": "6", "price": "100", "industry": "I1"},
                {"symbol": "SHORT", "quantity": "-2", "price": "100", "industry": "I2"},
            ],
        )
        metrics = calculate_portfolio_metrics(snapshot)
        self.assertEqual(metrics["gross_exposure"], "0.8")
        self.assertEqual(metrics["net_exposure"], "0.4")
        self.assertEqual(metrics["position_weights"]["SHORT|"], "-0.2")
        codes = {item["code"] for item in metrics["data_quality_flags"]}
        self.assertIn("NEGATIVE_QUANTITY_INTERPRETED_AS_SHORT", codes)

    def test_zero_price_missing_industry_and_currency_gap_remain_visible(self) -> None:
        snapshot = self._snapshot(
            cash="1000",
            total_assets="950",
            nav="950",
            positions=[
                {"symbol": "ZERO", "quantity": "10", "price": "0"},
                {"symbol": "SHORT", "quantity": "-5", "price": "10", "industry": "I2"},
                {
                    "symbol": "HK",
                    "quantity": "1",
                    "price": "100",
                    "currency": "HKD",
                    "industry": "I3",
                },
            ],
        )
        metrics = calculate_portfolio_metrics(snapshot)
        codes = {item["code"] for item in metrics["data_quality_flags"]}
        self.assertTrue(
            {
                "ZERO_PRICE",
                "UNKNOWN_INDUSTRY",
                "NEGATIVE_QUANTITY_INTERPRETED_AS_SHORT",
                "CURRENCY_NOT_CONVERTED",
            }.issubset(codes)
        )
        self.assertEqual(metrics["excluded_position_keys"], ["HK|"])

    def test_snapshot_document_requires_read_only_traceable_source(self) -> None:
        source, snapshot = snapshot_document(
            {
                "source": {
                    "name": self.source.name,
                    "kind": self.source.kind,
                    "uri": self.source.uri,
                    "identity_key": self.source.identity_key,
                    "read_only": True,
                },
                "snapshot": {
                    "source_path": "synthetic.json#1",
                    "observed_at": "2026-07-15 09:00:00",
                    "known_at": "2026-07-15 09:01:00",
                    "cash": "1",
                    "total_assets": "1",
                    "net_asset_value": "1",
                    "financing": "0",
                    "positions": [],
                },
            }
        )
        self.assertEqual(snapshot.source_id, source.source_id)
        with self.assertRaisesRegex(ModelValidationError, "read-only"):
            snapshot_document(
                {
                    "source": {
                        "name": "unsafe",
                        "kind": "sqlite",
                        "uri": "unsafe.sqlite3",
                        "read_only": False,
                    },
                    "snapshot": snapshot.to_dict(),
                }
            )

    def test_pre_decision_snapshot_blocks_future_information(self) -> None:
        future_observed = self._snapshot(
            observed_at="2026-07-15 10:01:00",
            known_at="2026-07-15 10:01:00",
        )
        context = PortfolioContext(
            reference_type="decision",
            reference_id="dec-1",
            reference_symbol="A",
            reference_occurred_at="2026-07-15T02:00:00Z",
            before_snapshot=future_observed,
        )
        with self.assertRaisesRegex(ModelValidationError, "occurred after"):
            context.to_dict()

        future_known = self._snapshot(
            observed_at="2026-07-15 09:00:00",
            known_at="2026-07-15 10:01:00",
        )
        context = PortfolioContext(
            reference_type="decision",
            reference_id="dec-2",
            reference_symbol="A",
            reference_occurred_at="2026-07-15T02:00:00Z",
            before_snapshot=future_known,
        )
        with self.assertRaisesRegex(ModelValidationError, "not known"):
            context.to_dict()

    def test_context_is_deterministic_and_separates_post_event_observation(self) -> None:
        before = self._snapshot(
            positions=[
                {"symbol": "A", "quantity": "10", "price": "10", "industry": "I1"}
            ],
            cash="900",
        )
        after = self._snapshot(
            observed_at="2026-07-15 10:01:00",
            known_at="2026-07-15 10:01:30",
            positions=[
                {"symbol": "A", "quantity": "15", "price": "10", "industry": "I1"}
            ],
            cash="850",
        )
        context = PortfolioContext(
            reference_type="trade_episode",
            reference_id="episode-1",
            reference_symbol="A",
            reference_occurred_at="2026-07-15T02:00:00Z",
            before_snapshot=before,
            after_snapshot=after,
        )
        first = deterministic_context_json(context)
        second = deterministic_context_json(context)
        self.assertEqual(first, second)
        payload = json.loads(first)
        self.assertEqual(
            payload["post_event_observation"]["target_position_change"]["quantity_change"],
            "5",
        )
        self.assertEqual(
            payload["post_event_observation"]["hindsight_boundary"],
            "not_available_at_reference_time",
        )
        markdown = render_portfolio_context_markdown(payload)
        self.assertIn("组合事实（决策时点可见）", markdown)
        self.assertIn("事后快照明确隔离", markdown)

    def test_store_is_idempotent_and_builds_decision_context(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            store = ReviewStore(Path(root) / "review.sqlite3")
            store.initialize()
            before = self._snapshot()
            after = self._snapshot(
                observed_at="2026-07-15 10:01:00",
                known_at="2026-07-15 10:01:30",
            )
            self.assertEqual(store.save_portfolio_snapshot(self.source, before)["status"], "INSERTED")
            self.assertEqual(store.save_portfolio_snapshot(self.source, before)["status"], "SKIPPED")
            store.save_portfolio_snapshot(self.source, after)
            decision = DecisionRecord.build(
                symbol="A",
                occurred_at="2026-07-15 10:00:00",
                known_at="2026-07-15 10:00:00",
                thesis="synthetic test decision",
            )
            store.add_decision(decision)
            context = store.build_decision_portfolio_context(
                decision_id=decision.decision_id,
                before_snapshot_id=before.resolved_snapshot_id,
                after_snapshot_id=after.resolved_snapshot_id,
            )
            self.assertEqual(context.reference_symbol, "A")
            self.assertEqual(
                store.load_portfolio_snapshot(before.resolved_snapshot_id).payload_sha256,
                before.payload_sha256,
            )
            self.assertEqual(store.status()["counts"]["position_snapshot_items"], 0)

    def test_same_explicit_snapshot_id_with_changed_content_is_a_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            store = ReviewStore(Path(root) / "review.sqlite3")
            store.initialize()
            original = self._snapshot(snapshot_id="snap_fixed")
            changed = self._snapshot(
                snapshot_id="snap_fixed",
                cash="999",
                total_assets="999",
                nav="999",
            )
            store.save_portfolio_snapshot(self.source, original)
            with self.assertRaises(DataConflictError):
                store.save_portfolio_snapshot(self.source, changed)


if __name__ == "__main__":
    unittest.main()
