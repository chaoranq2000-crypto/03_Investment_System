"""Command-line entry point for the review foundation and P2A context."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .episodes import (
    build_episode_collection,
    load_episode_collection,
    load_p2b_snapshot_references,
    query_episode_collection,
    save_episode_collection,
    validate_episode_collection,
)
from .ingest import ingest_csv, ingest_sqlite
from .introspection import (
    discover_sqlite_files,
    inspect_sqlite,
    suggest_trade_mapping,
    write_json,
)
from .models import DecisionRecord
from .portfolio_context import (
    PortfolioContext,
    load_snapshot_document,
    render_portfolio_context_markdown,
)
from .store import ReviewStore
from .time_utils import utc_iso


DEFAULT_DB = "data/db/investment_review.sqlite3"


def _print(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.investment_review",
        description="Evidence-first investment review data and portfolio context",
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

    snapshot = sub.add_parser(
        "snapshot-add", help="Add one reviewed portfolio snapshot to the sidecar database"
    )
    snapshot.add_argument("snapshot_json", help="JSON document with source and snapshot objects")

    context = sub.add_parser(
        "portfolio-context",
        help="Build a deterministic portfolio analysis block for a decision or trade episode",
    )
    reference = context.add_mutually_exclusive_group(required=True)
    reference.add_argument("--decision-id")
    reference.add_argument("--episode-id")
    context.add_argument("--symbol", help="Required with --episode-id")
    context.add_argument("--occurred-at", help="Required with --episode-id")
    context.add_argument("--timezone", default="Asia/Shanghai")
    context.add_argument("--before-snapshot", required=True)
    context.add_argument("--after-snapshot")
    context.add_argument("--out-json")
    context.add_argument("--out-markdown")

    episode_build = sub.add_parser(
        "episode-build",
        help="Build deterministic TradeEpisode v1 artifacts from normalized review events",
    )
    episode_build.add_argument("--cutoff-at", required=True)
    episode_build.add_argument("--timezone", default="Asia/Shanghai")
    episode_build.add_argument("--account")
    episode_build.add_argument("--symbol")
    episode_build.add_argument(
        "--portfolio-db",
        help="Optional P2B portfolio SQLite; opened strictly read-only for snapshot links",
    )
    episode_build.add_argument("--output", required=True)

    episode_query = sub.add_parser(
        "episode-query", help="Query a canonical TradeEpisode collection artifact"
    )
    episode_query.add_argument("artifact")
    episode_query.add_argument("--episode-id")
    episode_query.add_argument("--account")
    episode_query.add_argument("--instrument")
    episode_query.add_argument(
        "--status", choices=["open", "closed", "data_gap", "ambiguous"]
    )
    episode_query.add_argument("--from", dest="interval_start")
    episode_query.add_argument("--to", dest="interval_end")

    episode_validate = sub.add_parser(
        "episode-validate", help="Validate a canonical TradeEpisode collection artifact"
    )
    episode_validate.add_argument("artifact")

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
        elif args.command == "snapshot-add":
            source, snapshot = load_snapshot_document(args.snapshot_json)
            _print(store.save_portfolio_snapshot(source, snapshot))
        elif args.command == "portfolio-context":
            if args.decision_id:
                context = store.build_decision_portfolio_context(
                    decision_id=args.decision_id,
                    before_snapshot_id=args.before_snapshot,
                    after_snapshot_id=args.after_snapshot,
                )
            else:
                if not args.symbol or not args.occurred_at:
                    raise ValueError("--symbol and --occurred-at are required with --episode-id")
                context = PortfolioContext(
                    reference_type="trade_episode",
                    reference_id=args.episode_id,
                    reference_symbol=args.symbol.strip().upper(),
                    reference_occurred_at=utc_iso(args.occurred_at, args.timezone),
                    before_snapshot=store.load_portfolio_snapshot(args.before_snapshot),
                    after_snapshot=(
                        store.load_portfolio_snapshot(args.after_snapshot)
                        if args.after_snapshot
                        else None
                    ),
                )
            payload = context.to_dict()
            if args.out_json:
                output = Path(args.out_json)
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
                    encoding="utf-8",
                )
            if args.out_markdown:
                output = Path(args.out_markdown)
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(render_portfolio_context_markdown(payload), encoding="utf-8")
            _print(payload)
        elif args.command == "episode-build":
            cutoff_at = utc_iso(args.cutoff_at, args.timezone)
            events = store.list_episode_projection_inputs(
                account=args.account,
                symbol=args.symbol,
            )
            snapshots = (
                load_p2b_snapshot_references(args.portfolio_db, account=args.account)
                if args.portfolio_db
                else []
            )
            collection = build_episode_collection(
                events,
                cutoff_at=cutoff_at,
                snapshot_references=snapshots,
            )
            output = save_episode_collection(args.output, collection)
            _print(
                {
                    "status": collection["validation"]["validation_status"],
                    "episode_count": len(collection["episodes"]),
                    "collection_digest": collection["collection_digest"],
                    "output": str(output),
                }
            )
        elif args.command == "episode-query":
            collection = load_episode_collection(args.artifact)
            _print(
                query_episode_collection(
                    collection,
                    episode_id=args.episode_id,
                    account=args.account,
                    instrument=args.instrument,
                    status=args.status,
                    interval_start=args.interval_start,
                    interval_end=args.interval_end,
                )
            )
        elif args.command == "episode-validate":
            _print(validate_episode_collection(load_episode_collection(args.artifact)))
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
