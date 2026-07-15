"""Command-line entry point for the Phase 1 review foundation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .ingest import ingest_csv, ingest_sqlite
from .introspection import (
    discover_sqlite_files,
    inspect_sqlite,
    suggest_trade_mapping,
    write_json,
)
from .models import DecisionRecord
from .store import ReviewStore


DEFAULT_DB = "data/db/investment_review.sqlite3"


def _print(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.investment_review",
        description="Evidence-first investment review data foundation",
    )
    parser.add_argument(
        "--db",
        default=DEFAULT_DB,
        help=f"Sidecar review SQLite database (default: {DEFAULT_DB})",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Create or verify the v2 sidecar review database")
    sub.add_parser("status", help="Show schema, integrity and row counts")

    doctor = sub.add_parser(
        "doctor", help="Inspect existing portfolio SQLite files in read-only mode"
    )
    doctor.add_argument(
        "--portfolio-db",
        action="append",
        default=[],
        help="Portfolio SQLite file; may be supplied multiple times",
    )
    doctor.add_argument(
        "--search-root",
        default="data/db",
        help="Directory scanned when --portfolio-db is omitted",
    )
    doctor.add_argument(
        "--out",
        default="reports/investment_review/phase1/schema_manifest.json",
        help="JSON schema report output",
    )
    doctor.add_argument(
        "--mapping-out",
        help="Write a generated mapping for the highest-scoring trade table",
    )
    doctor.add_argument("--table", help="Specific table for --mapping-out")
    doctor.add_argument("--include-counts", action="store_true")

    csv_cmd = sub.add_parser("ingest-csv", help="Import a broker CSV using a JSON mapping")
    csv_cmd.add_argument("csv_path")
    csv_cmd.add_argument("--mapping", required=True)
    csv_cmd.add_argument("--dry-run", action="store_true")

    sqlite_cmd = sub.add_parser(
        "ingest-sqlite", help="Import a mapped table from the portfolio DB in read-only mode"
    )
    sqlite_cmd.add_argument("portfolio_db")
    sqlite_cmd.add_argument("--mapping", required=True)
    sqlite_cmd.add_argument("--dry-run", action="store_true")

    note = sub.add_parser("note-add", help="Capture a decision note with occurred/known times")
    note.add_argument("--symbol", required=True)
    note.add_argument("--occurred-at", required=True)
    note.add_argument(
        "--known-at",
        required=True,
        help="Actual knowledge/recording time; required to prevent historical backdating",
    )
    note.add_argument("--timezone", default="Asia/Shanghai")
    note.add_argument("--thesis", required=True)
    note.add_argument("--market")
    note.add_argument("--status", default="OPEN")
    note.add_argument("--trigger")
    note.add_argument("--invalidation")
    note.add_argument("--horizon")
    note.add_argument("--portfolio-role")
    note.add_argument("--direct-reason")
    note.add_argument("--risk-notes")
    note.add_argument("--raw-note")

    events = sub.add_parser("events", help="List recently normalized trade events")
    events.add_argument("--limit", type=int, default=50)
    events.add_argument("--symbol")
    events.add_argument("--include-raw", action="store_true")

    link = sub.add_parser("link", help="Link a decision note to an execution event")
    link.add_argument("decision_id")
    link.add_argument("event_id")
    link.add_argument("--relation", default="execution")

    return parser


def _doctor(args: argparse.Namespace) -> int:
    paths = [Path(value) for value in args.portfolio_db]
    if not paths:
        paths = discover_sqlite_files(args.search_root)
    review_db = Path(args.db).resolve()
    paths = [path for path in paths if path.resolve() != review_db]
    if not paths:
        raise FileNotFoundError(
            f"No SQLite files found. Supply --portfolio-db or check {args.search_root!r}."
        )

    reports = [inspect_sqlite(path, include_counts=args.include_counts) for path in paths]
    payload = {
        "mode": "read_only",
        "database_count": len(reports),
        "databases": reports,
    }
    output = write_json(args.out, payload)
    result: dict[str, Any] = {"schema_manifest": str(output), **payload}

    if args.mapping_out:
        ranked = sorted(
            reports,
            key=lambda report: max(
                (candidate["trade_score"] for candidate in report.get("candidates", [])),
                default=0,
            ),
            reverse=True,
        )
        mapping = suggest_trade_mapping(ranked[0], table_name=args.table)
        mapping_path = write_json(args.mapping_out, mapping)
        result["mapping_suggestion"] = str(mapping_path)
        result["mapping_review_required"] = mapping["generated_from"]["review_required"]

    _print(result)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    store = ReviewStore(args.db)

    try:
        if args.command == "init":
            _print(store.initialize())
        elif args.command == "status":
            _print(store.status())
        elif args.command == "doctor":
            return _doctor(args)
        elif args.command == "ingest-csv":
            _print(ingest_csv(args.csv_path, args.mapping, store, dry_run=args.dry_run))
        elif args.command == "ingest-sqlite":
            _print(
                ingest_sqlite(
                    args.portfolio_db,
                    args.mapping,
                    store,
                    dry_run=args.dry_run,
                )
            )
        elif args.command == "note-add":
            decision = DecisionRecord.build(
                symbol=args.symbol,
                occurred_at=args.occurred_at,
                known_at=args.known_at,
                timezone=args.timezone,
                thesis=args.thesis,
                market=args.market,
                status=args.status,
                trigger_text=args.trigger,
                invalidation_text=args.invalidation,
                expected_horizon=args.horizon,
                portfolio_role=args.portfolio_role,
                direct_reason=args.direct_reason,
                risk_notes=args.risk_notes,
                raw_note=args.raw_note,
            )
            _print({"decision_id": store.add_decision(decision), "status": "CREATED"})
        elif args.command == "events":
            _print(
                store.list_events(
                    limit=args.limit,
                    symbol=args.symbol,
                    include_raw=args.include_raw,
                )
            )
        elif args.command == "link":
            store.link_decision_event(args.decision_id, args.event_id, args.relation)
            _print({"status": "LINKED", "decision_id": args.decision_id, "event_id": args.event_id})
        else:
            parser.error(f"Unhandled command: {args.command}")
    except Exception as exc:
        print(
            json.dumps(
                {"status": "ERROR", "error_type": type(exc).__name__, "error": str(exc)},
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2
    return 0
