from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from src.investment_review.ingest import (
    MappingError,
    ingest_csv,
    ingest_sqlite,
    reviewed_mapping_content_sha256,
)
from src.investment_review.introspection import inspect_sqlite, suggest_trade_mapping
from src.investment_review.models import (
    CanonicalTradeEvent,
    DecisionRecord,
    ModelValidationError,
    SourceDefinition,
)
from src.investment_review.store import (
    APPLICATION_ID,
    DataConflictError,
    ReviewStore,
    ReviewStoreError,
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


class InvestmentReviewPhase1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.review_db = self.root / "review.sqlite3"
        self.store = ReviewStore(self.review_db)
        self.store.initialize()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_initialize_is_idempotent(self) -> None:
        first = self.store.initialize()
        second = self.store.initialize()
        self.assertEqual(first["schema_version"], 2)
        self.assertEqual(second["schema_version"], 2)
        status = self.store.status()
        self.assertEqual(status["integrity_check"], "ok")
        self.assertEqual(status["counts"]["trade_events"], 0)

    def _csv_mapping(self, csv_path: Path) -> Path:
        mapping = {
            "mapping_version": 1,
            "source": {
                "name": "unit-test-csv",
                "kind": "broker_csv",
                "uri": str(csv_path),
                "identity_key": "unit-test-broker-account",
                "timezone": "Asia/Shanghai",
                "read_only": True,
            },
            "mapping": {
                "record_id": "id",
                "occurred_at": {"join": ["date", "time"], "separator": " "},
                "known_at": None,
                "symbol": "symbol",
                "side": "side",
                "quantity": "qty",
                "price": "price",
                "gross_amount": None,
                "fees": ["commission", "tax"],
                "account": {"constant": "default"},
                "market": {"constant": "CN"},
                "currency": {"constant": "CNY"},
                "event_type": {"constant": "fill"},
            },
            "values": {"side": {"买入": "BUY", "卖出": "SELL"}},
        }
        path = self.root / "mapping.json"
        path.write_text(json.dumps(mapping, ensure_ascii=False), encoding="utf-8")
        return path

    def _write_reviewed_mapping(
        self, mapping: dict[str, object], *, stem: str = "portfolio"
    ) -> Path:
        generated_path = self.root / f"{stem}.generated.json"
        generated_path.write_text(json.dumps(mapping, ensure_ascii=False), encoding="utf-8")
        schema_path = self.root / f"{stem}.schema.json"
        schema_path.write_text(json.dumps({"schema": stem}), encoding="utf-8")

        reviewed = json.loads(json.dumps(mapping))
        reviewed["review"] = {
            "status": "reviewed",
            "reviewed_at": "2026-07-15T04:00:00+08:00",
            "reviewed_by": "unit-test",
            "generated_mapping_path": str(generated_path),
            "generated_mapping_sha256": sha256_file(generated_path),
            "schema_manifest_path": str(schema_path),
            "schema_manifest_sha256": sha256_file(schema_path),
        }
        reviewed["review"]["mapping_content_sha256"] = reviewed_mapping_content_sha256(
            reviewed
        )
        reviewed_path = self.root / f"{stem}.reviewed.json"
        reviewed_path.write_text(json.dumps(reviewed, ensure_ascii=False), encoding="utf-8")
        return reviewed_path

    def test_csv_import_is_idempotent_and_preserves_dual_time(self) -> None:
        csv_path = self.root / "fills.csv"
        csv_path.write_text(
            "id,date,time,symbol,side,qty,price,commission,tax\n"
            "A-1,2026-07-14,10:05:00,600000.SH,买入,100,10.25,5,0\n",
            encoding="utf-8",
        )
        mapping_path = self._csv_mapping(csv_path)

        first = ingest_csv(csv_path, mapping_path, self.store)
        second = ingest_csv(csv_path, mapping_path, self.store)
        self.assertEqual(first["inserted"], 1)
        self.assertEqual(second["inserted"], 0)
        self.assertEqual(second["skipped"], 1)
        self.assertEqual(self.store.status()["counts"]["ingest_run_events"], 2)

        events = self.store.list_events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["side"], "BUY")
        self.assertEqual(events[0]["gross_amount"], "1025.00")
        self.assertEqual(events[0]["fees"], "5")
        self.assertEqual(events[0]["occurred_at"], "2026-07-14T02:05:00Z")
        self.assertEqual(events[0]["known_at"], events[0]["occurred_at"])

    def test_csv_copy_uses_stable_source_identity(self) -> None:
        csv_path = self.root / "fills.csv"
        csv_path.write_text(
            "id,date,time,symbol,side,qty,price,commission,tax\n"
            "A-1,2026-07-14,10:05:00,600000.SH,买入,100,10.25,5,0\n",
            encoding="utf-8",
        )
        mapping_path = self._csv_mapping(csv_path)
        first = ingest_csv(csv_path, mapping_path, self.store)

        copied_path = self.root / "renamed-export.csv"
        shutil.copyfile(csv_path, copied_path)
        second = ingest_csv(copied_path, mapping_path, self.store)

        self.assertEqual(first["source_id"], second["source_id"])
        self.assertEqual(second["inserted"], 0)
        self.assertEqual(second["skipped"], 1)
        self.assertEqual(self.store.status()["counts"]["trade_events"], 1)

    def test_csv_row_order_change_remains_idempotent(self) -> None:
        csv_path = self.root / "fills.csv"
        csv_path.write_text(
            "id,date,time,symbol,side,qty,price,commission,tax\n"
            "A-1,2026-07-14,10:05:00,600000.SH,买入,100,10.25,5,0\n"
            "A-2,2026-07-14,10:06:00,000001.SZ,卖出,200,12.30,3,1\n",
            encoding="utf-8",
        )
        mapping_path = self._csv_mapping(csv_path)
        first = ingest_csv(csv_path, mapping_path, self.store)
        self.assertEqual(first["inserted"], 2)

        csv_path.write_text(
            "id,date,time,symbol,side,qty,price,commission,tax\n"
            "A-2,2026-07-14,10:06:00,000001.SZ,卖出,200,12.30,3,1\n"
            "A-1,2026-07-14,10:05:00,600000.SH,买入,100,10.25,5,0\n",
            encoding="utf-8",
        )
        second = ingest_csv(csv_path, mapping_path, self.store)
        self.assertEqual(second["inserted"], 0)
        self.assertEqual(second["skipped"], 2)

    def test_source_snapshot_removal_fails_atomically(self) -> None:
        csv_path = self.root / "fills.csv"
        csv_path.write_text(
            "id,date,time,symbol,side,qty,price,commission,tax\n"
            "A-1,2026-07-14,10:05:00,600000.SH,买入,100,10.25,5,0\n"
            "A-2,2026-07-14,10:06:00,000001.SZ,卖出,200,12.30,3,1\n",
            encoding="utf-8",
        )
        mapping_path = self._csv_mapping(csv_path)
        ingest_csv(csv_path, mapping_path, self.store)

        csv_path.write_text(
            "id,date,time,symbol,side,qty,price,commission,tax\n"
            "A-1,2026-07-14,10:05:00,600000.SH,买入,100,10.25,5,0\n",
            encoding="utf-8",
        )
        with self.assertRaises(DataConflictError):
            ingest_csv(csv_path, mapping_path, self.store)
        self.assertEqual(self.store.status()["counts"]["trade_events"], 2)

    def test_changed_source_record_fails_atomically(self) -> None:
        csv_path = self.root / "fills.csv"
        csv_path.write_text(
            "id,date,time,symbol,side,qty,price,commission,tax\n"
            "A-1,2026-07-14,10:05:00,600000.SH,买入,100,10.25,5,0\n",
            encoding="utf-8",
        )
        mapping_path = self._csv_mapping(csv_path)
        ingest_csv(csv_path, mapping_path, self.store)

        csv_path.write_text(
            "id,date,time,symbol,side,qty,price,commission,tax\n"
            "A-1,2026-07-14,10:05:00,600000.SH,买入,100,10.55,5,0\n",
            encoding="utf-8",
        )
        with self.assertRaises(DataConflictError):
            ingest_csv(csv_path, mapping_path, self.store)
        self.assertEqual(self.store.status()["counts"]["trade_events"], 1)

    def test_sqlite_doctor_and_ingest_are_read_only(self) -> None:
        portfolio_db = self.root / "portfolio.sqlite3"
        conn = sqlite3.connect(portfolio_db)
        conn.execute(
            """
            CREATE TABLE fills (
                trade_id TEXT PRIMARY KEY,
                trade_time TEXT NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                quantity TEXT NOT NULL,
                price TEXT NOT NULL,
                commission TEXT
            )
            """
        )
        conn.execute(
            "INSERT INTO fills VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("T-1", "2026-07-14 10:05:00", "000001.SZ", "BUY", "200", "12.3", "3"),
        )
        conn.commit()
        conn.close()
        before = sha256_file(portfolio_db)

        report = inspect_sqlite(portfolio_db, include_counts=True)
        after_doctor = sha256_file(portfolio_db)
        self.assertEqual(before, after_doctor)
        self.assertEqual(report["candidates"][0]["table"], "fills")
        mapping = suggest_trade_mapping(report)
        generated_path = self.root / "sqlite_mapping.generated.json"
        generated_path.write_text(json.dumps(mapping, ensure_ascii=False), encoding="utf-8")

        with self.assertRaises(MappingError):
            ingest_sqlite(portfolio_db, generated_path, self.store)
        self.assertEqual(ingest_sqlite(portfolio_db, generated_path, self.store, dry_run=True)["seen"], 1)

        mapping_path = self._write_reviewed_mapping(mapping, stem="sqlite_mapping")

        copied_db = self.root / "unreviewed-copy.sqlite3"
        shutil.copyfile(portfolio_db, copied_db)
        with self.assertRaisesRegex(MappingError, "reviewed source.uri"):
            ingest_sqlite(copied_db, mapping_path, self.store)

        result = ingest_sqlite(portfolio_db, mapping_path, self.store)
        after_ingest = sha256_file(portfolio_db)
        self.assertEqual(before, after_ingest)
        self.assertEqual(result["inserted"], 1)
        self.assertEqual(self.store.list_events()[0]["symbol"], "000001.SZ")
        self.assertNotIn("raw_payload_json", self.store.list_events()[0])
        self.assertIn("raw_payload_json", self.store.list_events(include_raw=True)[0])

        conn = sqlite3.connect(self.review_db)
        manifest = json.loads(
            conn.execute(
                "SELECT manifest_json FROM ingest_runs WHERE status='COMPLETED'"
            ).fetchone()[0]
        )
        conn.close()
        self.assertEqual(len(manifest["mapping_sha256"]), 64)
        self.assertEqual(len(manifest["source_sha256"]), 64)
        self.assertEqual(manifest["mapping_snapshot"]["review"]["status"], "reviewed")

        reviewed = json.loads(mapping_path.read_text(encoding="utf-8"))
        reviewed["mapping"]["price"] = "commission"
        mapping_path.write_text(json.dumps(reviewed, ensure_ascii=False), encoding="utf-8")
        with self.assertRaises(MappingError):
            ingest_sqlite(portfolio_db, mapping_path, self.store)

        reviewed["mapping"]["price"] = "price"
        mapping_path.write_text(json.dumps(reviewed, ensure_ascii=False), encoding="utf-8")
        Path(reviewed["review"]["schema_manifest_path"]).write_text(
            '{"schema":"tampered"}', encoding="utf-8"
        )
        with self.assertRaises(MappingError):
            ingest_sqlite(portfolio_db, mapping_path, self.store)

        Path(reviewed["review"]["schema_manifest_path"]).write_text(
            json.dumps({"schema": "sqlite_mapping"}), encoding="utf-8"
        )
        conn = sqlite3.connect(portfolio_db)
        conn.execute("ALTER TABLE fills ADD COLUMN post_review_drift TEXT")
        conn.commit()
        conn.close()
        with self.assertRaisesRegex(MappingError, "table schema hash mismatch"):
            ingest_sqlite(portfolio_db, mapping_path, self.store)

    def test_current_portfolio_ledger_schema_is_detected_and_previewable(self) -> None:
        portfolio_db = self.root / "portfolio.sqlite3"
        conn = sqlite3.connect(portfolio_db)
        conn.execute(
            """
            CREATE TABLE ledger_entries (
                entry_id INTEGER PRIMARY KEY,
                dedupe_key TEXT NOT NULL UNIQUE,
                external_id TEXT NOT NULL,
                event_date TEXT NOT NULL,
                event_time TEXT NOT NULL,
                event_type TEXT NOT NULL,
                ts_code TEXT NOT NULL,
                quantity TEXT NOT NULL,
                price TEXT NOT NULL,
                gross_amount TEXT NOT NULL,
                cash_amount TEXT NOT NULL,
                fees TEXT NOT NULL,
                account_id TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.executemany(
            "INSERT INTO ledger_entries VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    1,
                    "stable-buy",
                    "external-buy",
                    "2026-07-14",
                    "10:05:00",
                    "BUY",
                    "000001.SZ",
                    "200",
                    "12.3",
                    "2460",
                    "0",
                    "3",
                    "default",
                    "2026-07-14T17:42:14+00:00",
                ),
                (
                    2,
                    "stable-dividend",
                    "external-dividend",
                    "2026-07-14",
                    "",
                    "DIVIDEND",
                    "000001.SZ",
                    "0",
                    "0",
                    "0",
                    "15.25",
                    "0",
                    "default",
                    "2026-07-14T17:42:14+00:00",
                ),
            ],
        )
        conn.commit()
        conn.close()

        report = inspect_sqlite(portfolio_db)
        self.assertEqual(report["candidates"][0]["table"], "ledger_entries")
        mapping = suggest_trade_mapping(report)
        self.assertEqual(
            mapping["mapping"]["record_id"],
            {"join": ["account_id", "external_id"], "separator": "::"},
        )
        self.assertEqual(
            mapping["mapping"]["occurred_at"],
            {"join": ["event_date", "event_time"], "separator": " "},
        )
        self.assertEqual(mapping["mapping"]["side"], "event_type")
        self.assertEqual(mapping["mapping"]["event_type"], "event_type")
        self.assertEqual(mapping["mapping"]["cash_amount"], "cash_amount")
        self.assertTrue(mapping["generated_from"]["review_required"])
        self.assertEqual(mapping["generated_from"]["missing_required_fields"], [])

        # Simulate the required human review: the rebuild timestamp is not a
        # historical knowledge timestamp, so preserve the explicit fallback.
        mapping["mapping"]["known_at"] = None
        mapping_path = self._write_reviewed_mapping(mapping, stem="portfolio_mapping")

        dry_run = ingest_sqlite(portfolio_db, mapping_path, self.store, dry_run=True)
        self.assertEqual(dry_run["seen"], 2)
        self.assertEqual(dry_run["preview"][0]["symbol"], "000001.SZ")
        self.assertEqual(dry_run["preview"][0]["side"], "BUY")
        self.assertEqual(dry_run["preview"][0]["quantity"], "200")
        self.assertEqual(dry_run["preview"][0]["price"], "12.3")
        self.assertTrue(dry_run["preview"][0]["known_at_fallback"])
        self.assertEqual(dry_run["preview"][1]["event_type"], "dividend")
        self.assertEqual(dry_run["preview"][1]["side"], "OTHER")
        self.assertEqual(dry_run["preview"][1]["cash_amount"], "15.25")

        first = ingest_sqlite(portfolio_db, mapping_path, self.store)
        self.assertEqual(first["inserted"], 2)

        conn = sqlite3.connect(portfolio_db)
        conn.execute(
            "UPDATE ledger_entries SET price='12.4' WHERE external_id='external-buy'"
        )
        conn.commit()
        conn.close()
        with self.assertRaises(DataConflictError):
            ingest_sqlite(portfolio_db, mapping_path, self.store)
        self.assertEqual(self.store.status()["counts"]["trade_events"], 2)

    def test_failed_mapping_drift_preserves_active_source_config(self) -> None:
        source_v1 = SourceDefinition(
            name="stable-source",
            kind="manual",
            uri="manual://stable-source",
            config={"mapping": "v1"},
        )
        event_v1 = CanonicalTradeEvent.build(
            source_id=source_v1.source_id,
            source_record_id="record-1",
            event_type="fill",
            occurred_at="2026-07-14 10:05:00",
            known_at="2026-07-14 10:05:01",
            symbol="600000.SH",
            account="account-a",
            market="CN",
            side="BUY",
            quantity="100",
            price="10",
            timezone="Asia/Shanghai",
            raw_payload={"source_row": {"id": "record-1", "price": "10"}},
        )
        self.store.import_events(source_v1, [event_v1], manifest={"mapping": "v1"})

        source_v2 = SourceDefinition(
            name="stable-source",
            kind="manual",
            uri="manual://stable-source",
            config={"mapping": "v2"},
        )
        event_v2 = CanonicalTradeEvent.build(
            source_id=source_v2.source_id,
            source_record_id="record-1",
            event_type="fill",
            occurred_at="2026-07-14 10:05:00",
            known_at="2026-07-14 10:05:01",
            symbol="600000.SH",
            account="account-b",
            market="HK",
            side="BUY",
            quantity="100",
            price="10",
            timezone="Asia/Shanghai",
            raw_payload={"source_row": {"id": "record-1", "price": "10"}},
        )
        with self.assertRaises(DataConflictError):
            self.store.import_events(source_v2, [event_v2], manifest={"mapping": "v2"})

        conn = sqlite3.connect(self.review_db)
        active = conn.execute(
            "SELECT fingerprint, config_json FROM data_sources WHERE source_id=?",
            (source_v1.source_id,),
        ).fetchone()
        failed = conn.execute(
            "SELECT source_fingerprint, status FROM ingest_runs WHERE status='FAILED' LIMIT 1"
        ).fetchone()
        version_count = conn.execute(
            "SELECT COUNT(*) FROM source_config_versions WHERE source_id=?",
            (source_v1.source_id,),
        ).fetchone()[0]
        conn.close()
        self.assertEqual(active[0], source_v1.fingerprint)
        self.assertEqual(json.loads(active[1])["mapping"], "v1")
        self.assertEqual(failed, (source_v2.fingerprint, "FAILED"))
        self.assertEqual(version_count, 2)

    def test_non_review_database_is_never_initialized_or_mutated(self) -> None:
        portfolio_db = self.root / "not-a-review.sqlite3"
        conn = sqlite3.connect(portfolio_db)
        conn.execute("CREATE TABLE portfolio_marker(value TEXT NOT NULL)")
        conn.execute("INSERT INTO portfolio_marker VALUES ('unchanged')")
        conn.commit()
        conn.close()
        before = sha256_file(portfolio_db)

        wrong_store = ReviewStore(portfolio_db)
        with self.assertRaises(ReviewStoreError):
            wrong_store.initialize()
        with self.assertRaises(ReviewStoreError):
            wrong_store.status()

        self.assertEqual(before, sha256_file(portfolio_db))
        self.assertFalse(Path(str(portfolio_db) + "-wal").exists())
        self.assertFalse(Path(str(portfolio_db) + "-shm").exists())

    def test_legacy_review_database_requires_reimport_and_is_not_mutated(self) -> None:
        legacy_db = self.root / "legacy-review.sqlite3"
        conn = sqlite3.connect(legacy_db)
        conn.execute("CREATE TABLE schema_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        conn.execute("INSERT INTO schema_meta VALUES ('schema_version', '1')")
        conn.execute("CREATE TABLE data_sources(source_id TEXT PRIMARY KEY)")
        conn.execute("CREATE TABLE ingest_runs(run_id TEXT PRIMARY KEY)")
        conn.execute("CREATE TABLE trade_events(event_id TEXT PRIMARY KEY)")
        conn.execute("CREATE TABLE decisions(decision_id TEXT PRIMARY KEY)")
        conn.execute("PRAGMA user_version = 1")
        conn.commit()
        conn.close()
        before = sha256_file(legacy_db)

        with self.assertRaisesRegex(ReviewStoreError, "new v2 sidecar and reimport"):
            ReviewStore(legacy_db).initialize()

        self.assertEqual(before, sha256_file(legacy_db))
        self.assertFalse(Path(str(legacy_db) + "-wal").exists())
        self.assertFalse(Path(str(legacy_db) + "-shm").exists())

    def test_review_database_has_application_id(self) -> None:
        conn = sqlite3.connect(self.review_db)
        application_id = conn.execute("PRAGMA application_id").fetchone()[0]
        conn.close()
        self.assertEqual(application_id, APPLICATION_ID)

    def test_decision_known_at_and_finite_numbers_are_required(self) -> None:
        with self.assertRaises(ModelValidationError):
            DecisionRecord.build(
                symbol="600000.SH",
                occurred_at="2025-01-01 09:30:00",
                known_at=None,
                thesis="Historical note",
            )
        with self.assertRaises(ModelValidationError):
            CanonicalTradeEvent.build(
                source_id="source",
                source_record_id="record",
                event_type="fill",
                occurred_at="2026-07-14 10:05:00",
                known_at="2026-07-14 10:05:01",
                symbol="600000.SH",
                side="BUY",
                quantity="100",
                price="Infinity",
                timezone="Asia/Shanghai",
            )

    def test_decision_can_be_linked_to_event(self) -> None:
        source = SourceDefinition(
            name="manual-test",
            kind="manual",
            uri="manual://test",
            timezone="Asia/Shanghai",
        )
        event = CanonicalTradeEvent.build(
            source_id=source.source_id,
            source_record_id="manual-1",
            event_type="fill",
            occurred_at="2026-07-14 10:05:00",
            known_at="2026-07-14 10:05:30",
            symbol="600000.SH",
            side="BUY",
            quantity="100",
            price="10",
            timezone="Asia/Shanghai",
            raw_payload={"test": True},
        )
        self.store.import_events(source, [event])
        decision = DecisionRecord.build(
            symbol="600000.SH",
            occurred_at="2026-07-14 09:55:00",
            known_at="2026-07-14 09:56:00",
            thesis="Unit test thesis",
            timezone="Asia/Shanghai",
        )
        decision_id = self.store.add_decision(decision)
        self.store.link_decision_event(decision_id, event.event_id)
        status = self.store.status()
        self.assertEqual(status["counts"]["decisions"], 1)
        self.assertEqual(status["counts"]["decision_event_links"], 1)


if __name__ == "__main__":
    unittest.main()
