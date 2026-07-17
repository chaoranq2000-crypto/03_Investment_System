"""Command-line entry point for the review foundation and P2A context."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .artifact_io import atomic_create_bytes, atomic_write_bytes
from .behavior_cohort import (
    EFFECTIVE_ANCHORS,
    build_behavior_cohort,
    load_behavior_cohort,
    query_behavior_cohort,
    replay_validate_behavior_cohort,
    save_behavior_cohort,
    validate_behavior_cohort,
)
from .behavior_observations import (
    DETECTOR_IDS,
    build_behavior_observation_set,
    load_behavior_observation_set,
    query_behavior_observation_set,
    replay_validate_behavior_observation_set,
    save_behavior_observation_set,
    validate_behavior_observation_set,
)
from .episodes import (
    build_episode_collection,
    load_episode_collection,
    load_p2b_snapshot_references,
    query_episode_collection,
    save_episode_collection,
    validate_episode_collection,
)
from .episode_portfolio_context import (
    build_episode_portfolio_context,
    load_episode_portfolio_context,
    query_episode_portfolio_context,
    replay_validate_episode_portfolio_context,
    save_episode_portfolio_context,
    validate_episode_portfolio_context,
)
from .episode_interpretation import (
    RecordedResponseProvider,
    UnavailableInterpretationProvider,
    build_model_assisted_episode_review,
    save_interpretation_attempt,
)
from .episode_review import (
    FACT_SECTION_NAMES,
    build_facts_only_episode_review,
    load_episode_review,
    query_episode_review,
    render_episode_review_markdown,
    replay_validate_episode_review,
    save_episode_review,
    validate_episode_review,
)
from .episode_revision import (
    apply_human_review,
    diff_episode_reviews,
    list_episode_review_revisions,
    load_human_review_request,
    save_new_episode_review,
    validate_revision_chain,
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
from .review_input_bundle import (
    build_review_input_bundle,
    load_review_input_bundle,
    query_review_input_bundle,
    replay_validate_review_input_bundle,
    save_review_input_bundle,
    validate_review_input_bundle,
)
from .store import ReviewStore
from .time_utils import utc_iso


DEFAULT_DB = "data/db/investment_review.sqlite3"


def _print(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


def _load_json_documents(paths: list[str]) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    for value in paths:
        payload = json.loads(Path(value).read_text(encoding="utf-8"))
        rows = payload if isinstance(payload, list) else [payload]
        if not all(isinstance(item, dict) for item in rows):
            raise ValueError(f"{value} must contain one JSON object or an array of objects")
        documents.extend(rows)
    return documents


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

    episode_context_build = sub.add_parser(
        "episode-portfolio-context-build",
        help="Bind point-in-time portfolio evidence to TradeEpisode event anchors",
    )
    episode_context_build.add_argument("--episode-artifact", required=True)
    episode_context_build.add_argument(
        "--portfolio-db",
        required=True,
        help="P2B portfolio or reviewed snapshot SQLite opened strictly read-only",
    )
    episode_context_build.add_argument(
        "--cutoff-at",
        required=True,
        help="Latest episode/event time included in the artifact",
    )
    episode_context_build.add_argument(
        "--knowledge-cutoff",
        required=True,
        help="Latest source knowledge time visible to this artifact revision",
    )
    episode_context_build.add_argument(
        "--episode-id",
        action="append",
        default=[],
        help="Optional episode ID filter; may be supplied more than once",
    )
    episode_context_build.add_argument("--output", required=True)

    episode_context_show = sub.add_parser(
        "episode-portfolio-context-show",
        help="Query a canonical TradeEpisode portfolio-context artifact",
    )
    episode_context_show.add_argument("artifact")
    episode_context_show.add_argument("--episode-id")
    episode_context_show.add_argument("--context-id")
    episode_context_show.add_argument("--content-id")

    episode_context_validate = sub.add_parser(
        "episode-portfolio-context-validate",
        help="Validate a canonical TradeEpisode portfolio-context artifact",
    )
    episode_context_validate.add_argument("artifact")
    episode_context_validate.add_argument(
        "--source-replay",
        action="store_true",
        help="Rebuild from the supplied P2C artifact and read-only P2B database",
    )
    episode_context_validate.add_argument("--episode-artifact")
    episode_context_validate.add_argument("--portfolio-db")

    review_input_build = sub.add_parser(
        "review-input-build",
        help="Freeze one source-verified episode and its P2E-3 evidence for P2F",
    )
    review_input_build.add_argument("--episode-artifact", required=True)
    review_input_build.add_argument("--portfolio-context")
    review_input_build.add_argument("--portfolio-db", required=True)
    review_input_build.add_argument("--episode-id", required=True)
    review_input_build.add_argument("--review-cutoff", required=True)
    review_input_build.add_argument(
        "--decision-source",
        action="append",
        default=[],
        help="Optional JSON source document; may be supplied more than once",
    )
    review_input_build.add_argument(
        "--supplemental-source",
        action="append",
        default=[],
        help="Optional cutoff-aware market/outcome/note JSON source document",
    )
    review_input_build.add_argument("--output", required=True)
    review_input_build.add_argument(
        "--allow-missing-portfolio-context",
        action="store_true",
        help="Build an explicit contract-only, release-blocked bundle",
    )

    review_input_show = sub.add_parser(
        "review-input-show",
        help="Query a canonical P2F review input bundle",
    )
    review_input_show.add_argument("artifact")
    review_input_show.add_argument("--section")
    review_input_show.add_argument("--source-id")
    review_input_show.add_argument("--content-id")

    review_input_validate = sub.add_parser(
        "review-input-validate",
        help="Validate a canonical P2F review input bundle",
    )
    review_input_validate.add_argument("artifact")
    review_input_validate.add_argument(
        "--source-replay",
        action="store_true",
        help="Rebuild from the original P2C/P2E-3/P2B sources",
    )
    review_input_validate.add_argument("--episode-artifact")
    review_input_validate.add_argument("--portfolio-context")
    review_input_validate.add_argument("--portfolio-db")
    review_input_validate.add_argument(
        "--decision-source", action="append", default=[]
    )
    review_input_validate.add_argument(
        "--supplemental-source", action="append", default=[]
    )

    episode_review_build = sub.add_parser(
        "episode-review-build",
        help="Build a deterministic facts-only review from one frozen P2F-1 bundle",
    )
    episode_review_build.add_argument("--input-bundle", required=True)
    episode_review_build.add_argument(
        "--facts-only",
        action="store_true",
        required=True,
        help="Explicitly select the P2F-2 deterministic facts engine",
    )
    episode_review_build.add_argument("--output", required=True)
    episode_review_build.add_argument(
        "--markdown-output",
        help="Optional facts-only Markdown rendering written after JSON validation",
    )

    episode_review_show = sub.add_parser(
        "episode-review-show", help="Query a canonical P2F episode-review artifact"
    )
    episode_review_show.add_argument("artifact")
    episode_review_show.add_argument("--section", choices=list(FACT_SECTION_NAMES))
    episode_review_show.add_argument("--fact-id")
    episode_review_show.add_argument("--content-id")

    episode_review_validate = sub.add_parser(
        "episode-review-validate", help="Validate a canonical P2F episode review"
    )
    episode_review_validate.add_argument("artifact")
    episode_review_validate.add_argument(
        "--source-replay",
        action="store_true",
        help="Rebuild facts from the supplied frozen P2F-1 bundle",
    )
    episode_review_validate.add_argument("--input-bundle")

    episode_review_interpret = sub.add_parser(
        "episode-review-interpret",
        help="Explicitly add bounded P2F-3 interpretations from a recorded provider response",
    )
    episode_review_interpret.add_argument("--artifact", required=True)
    episode_review_interpret.add_argument("--model-id", required=True)
    episode_review_interpret.add_argument("--generated-at", required=True)
    provider_group = episode_review_interpret.add_mutually_exclusive_group(
        required=True
    )
    provider_group.add_argument(
        "--model-response",
        help="UTF-8 JSON response already recorded from an explicitly selected provider",
    )
    provider_group.add_argument(
        "--simulate-unavailable",
        action="store_true",
        help="Exercise the facts-only fallback without calling any model",
    )
    episode_review_interpret.add_argument(
        "--parameters-json",
        default="{}",
        help="Canonical JSON object recorded as model parameters; binary floats are rejected",
    )
    episode_review_interpret.add_argument("--output", required=True)
    episode_review_interpret.add_argument("--attempt-output", required=True)

    episode_review_correct = sub.add_parser(
        "episode-review-correct",
        help="Append one human accept/reject/correct revision without overwriting its source",
    )
    episode_review_correct.add_argument("--artifact", required=True)
    episode_review_correct.add_argument("--request", required=True)
    episode_review_correct.add_argument("--output", required=True)

    episode_review_render = sub.add_parser(
        "episode-review-render",
        help="Render one validated P2F episode-review revision as safe Markdown",
    )
    episode_review_render.add_argument("--artifact", required=True)
    episode_review_render.add_argument("--output", required=True)

    episode_review_diff = sub.add_parser(
        "episode-review-diff",
        help="Show a deterministic diff between two P2F review revisions",
    )
    episode_review_diff.add_argument("before")
    episode_review_diff.add_argument("after")

    episode_review_revision_list = sub.add_parser(
        "episode-review-revision-list",
        help="Validate and list an append-only P2F review revision chain",
    )
    episode_review_revision_list.add_argument("artifact", nargs="+")

    behavior_cohort_build = sub.add_parser(
        "behavior-cohort-build",
        help="Freeze a deterministic facts-only cohort from explicit P2F revisions",
    )
    behavior_cohort_build.add_argument(
        "--episode-review",
        action="append",
        required=True,
        help="P2F review JSON; may be supplied more than once",
    )
    behavior_cohort_build.add_argument(
        "--input-bundle",
        action="append",
        required=True,
        help="P2F review-input bundle JSON; may be supplied more than once",
    )
    behavior_cohort_build.add_argument("--effective-from", required=True)
    behavior_cohort_build.add_argument("--effective-to", required=True)
    behavior_cohort_build.add_argument("--knowledge-cutoff", required=True)
    behavior_cohort_build.add_argument(
        "--effective-anchor", required=True, choices=list(EFFECTIVE_ANCHORS)
    )
    behavior_cohort_build.add_argument("--account", action="append", default=[])
    behavior_cohort_build.add_argument("--instrument", action="append", default=[])
    behavior_cohort_build.add_argument("--output", required=True)

    behavior_cohort_show = sub.add_parser(
        "behavior-cohort-show",
        help="Query a canonical P2G-1 behavior cohort without deriving new facts",
    )
    behavior_cohort_show.add_argument("artifact")
    behavior_cohort_show.add_argument("--episode-id")
    behavior_cohort_show.add_argument("--review-id")
    behavior_cohort_show.add_argument("--reason-code")
    behavior_cohort_show.add_argument("--content-id")

    behavior_cohort_validate = sub.add_parser(
        "behavior-cohort-validate",
        help="Validate a P2G-1 cohort, optionally by exact P2F source replay",
    )
    behavior_cohort_validate.add_argument("artifact")
    behavior_cohort_validate.add_argument("--source-replay", action="store_true")
    behavior_cohort_validate.add_argument("--episode-review", action="append", default=[])
    behavior_cohort_validate.add_argument("--input-bundle", action="append", default=[])

    behavior_observation_build = sub.add_parser(
        "behavior-observation-build",
        help="Build deterministic facts-only P2G-2 observations from one P2G-1 cohort",
    )
    behavior_observation_build.add_argument("--cohort", required=True)
    behavior_observation_build.add_argument(
        "--detector-config",
        help="Optional JSON detector config; omitted values are expanded and persisted",
    )
    behavior_observation_build.add_argument(
        "--detector",
        action="append",
        choices=list(DETECTOR_IDS),
        default=[],
        help="Restrict execution to one detector; may be supplied more than once",
    )
    behavior_observation_build.add_argument("--output", required=True)

    behavior_observation_show = sub.add_parser(
        "behavior-observation-show",
        help="Query P2G-2 evaluations with AND semantics",
    )
    behavior_observation_show.add_argument("artifact")
    behavior_observation_show.add_argument("--evaluation-id")
    behavior_observation_show.add_argument("--detector-id", choices=list(DETECTOR_IDS))
    behavior_observation_show.add_argument("--status")
    behavior_observation_show.add_argument("--episode-id")
    behavior_observation_show.add_argument("--review-id")
    behavior_observation_show.add_argument("--account-id")
    behavior_observation_show.add_argument("--instrument-id")
    behavior_observation_show.add_argument("--reason-code")
    behavior_observation_show.add_argument("--content-id")

    behavior_observation_validate = sub.add_parser(
        "behavior-observation-validate",
        help="Validate P2G-2 offline or by exact P2G-1 source replay",
    )
    behavior_observation_validate.add_argument("artifact")
    behavior_observation_validate.add_argument("--source-replay", action="store_true")
    behavior_observation_validate.add_argument("--cohort")

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
        elif args.command == "episode-portfolio-context-build":
            artifact = build_episode_portfolio_context(
                load_episode_collection(args.episode_artifact),
                portfolio_db=args.portfolio_db,
                as_of=args.cutoff_at,
                knowledge_cutoff=args.knowledge_cutoff,
                episode_ids=args.episode_id or None,
            )
            validation = validate_episode_portfolio_context(artifact)
            if validation["validation_status"] == "blocked":
                raise ValueError("P2E-3 artifact failed validation")
            output = save_episode_portfolio_context(args.output, artifact)
            _print(
                {
                    "status": validation["validation_status"],
                    "content_id": artifact["content_id"],
                    "context_count": len(artifact["contexts"]),
                    "delta_count": len(artifact["deltas"]),
                    "output": str(output),
                }
            )
        elif args.command == "episode-portfolio-context-show":
            _print(
                query_episode_portfolio_context(
                    load_episode_portfolio_context(args.artifact),
                    episode_id=args.episode_id,
                    context_id=args.context_id,
                    content_id=args.content_id,
                )
            )
        elif args.command == "episode-portfolio-context-validate":
            context_artifact = load_episode_portfolio_context(args.artifact)
            if args.source_replay:
                if not args.episode_artifact or not args.portfolio_db:
                    raise ValueError(
                        "--source-replay requires --episode-artifact and --portfolio-db"
                    )
                validation = replay_validate_episode_portfolio_context(
                    context_artifact,
                    episode_collection=load_episode_collection(
                        args.episode_artifact
                    ),
                    portfolio_db=args.portfolio_db,
                )
            else:
                validation = validate_episode_portfolio_context(
                    context_artifact
                )
            _print(validation)
            if validation["validation_status"] == "blocked":
                return 2
        elif args.command == "review-input-build":
            decision_sources = _load_json_documents(args.decision_source)
            supplemental_sources = _load_json_documents(args.supplemental_source)
            if (
                not args.portfolio_context
                and not args.allow_missing_portfolio_context
            ):
                raise ValueError(
                    "--portfolio-context is required unless "
                    "--allow-missing-portfolio-context is explicit"
                )
            artifact = build_review_input_bundle(
                load_episode_collection(args.episode_artifact),
                (
                    load_episode_portfolio_context(args.portfolio_context)
                    if args.portfolio_context
                    else None
                ),
                portfolio_db=args.portfolio_db,
                episode_id=args.episode_id,
                review_cutoff=args.review_cutoff,
                decision_sources=decision_sources,
                supplemental_sources=supplemental_sources,
                allow_missing_portfolio_context=(
                    args.allow_missing_portfolio_context
                ),
            )
            validation = validate_review_input_bundle(artifact)
            if validation["validation_status"] == "blocked":
                raise ValueError("P2F review input bundle failed validation")
            output = save_review_input_bundle(args.output, artifact)
            _print(
                {
                    "status": validation["validation_status"],
                    "content_id": artifact["content_id"],
                    "episode_id": artifact["episode_ref"]["episode_id"],
                    "source_count": len(artifact["source_inventory"]),
                    "release_readiness": artifact["release_readiness"]["status"],
                    "output": str(output),
                }
            )
            if artifact["release_readiness"]["status"] != "ready":
                return 2
        elif args.command == "review-input-show":
            _print(
                query_review_input_bundle(
                    load_review_input_bundle(args.artifact),
                    section=args.section,
                    source_id=args.source_id,
                    content_id=args.content_id,
                )
            )
        elif args.command == "review-input-validate":
            artifact = load_review_input_bundle(args.artifact)
            if args.source_replay:
                missing_context = (
                    artifact["portfolio_context_ref"]["status"] == "missing"
                )
                if not args.episode_artifact or not args.portfolio_db:
                    raise ValueError(
                        "--source-replay requires --episode-artifact and "
                        "--portfolio-db"
                    )
                if not missing_context and not args.portfolio_context:
                    raise ValueError(
                        "--source-replay requires --portfolio-context for a "
                        "release-ready bundle"
                    )
                validation = replay_validate_review_input_bundle(
                    artifact,
                    episode_collection=load_episode_collection(
                        args.episode_artifact
                    ),
                    episode_portfolio_context=(
                        load_episode_portfolio_context(args.portfolio_context)
                        if args.portfolio_context
                        else None
                    ),
                    portfolio_db=args.portfolio_db,
                    decision_sources=_load_json_documents(
                        args.decision_source
                    ),
                    supplemental_sources=_load_json_documents(
                        args.supplemental_source
                    ),
                )
            else:
                validation = validate_review_input_bundle(artifact)
            _print(validation)
            if (
                validation["validation_status"] == "blocked"
                or artifact["release_readiness"]["status"] != "ready"
                or artifact["source_verification"]["status"] != "verified"
            ):
                return 2
        elif args.command == "episode-review-build":
            input_bundle = load_review_input_bundle(args.input_bundle)
            artifact = build_facts_only_episode_review(input_bundle)
            validation = validate_episode_review(artifact)
            if validation["validation_status"] == "blocked":
                raise ValueError("P2F facts-only episode review failed validation")
            output = save_episode_review(args.output, artifact)
            markdown_output = None
            if args.markdown_output:
                markdown_output = atomic_write_bytes(
                    args.markdown_output,
                    render_episode_review_markdown(artifact).encode("utf-8"),
                )
            _print(
                {
                    "status": validation["validation_status"],
                    "content_id": artifact["content_id"],
                    "review_id": artifact["review_id"],
                    "episode_id": artifact["input_bundle_ref"]["episode_id"],
                    "fact_count": sum(
                        len(section["facts"])
                        for section in artifact["fact_sections"].values()
                    ),
                    "output": str(output),
                    "markdown_output": (
                        str(markdown_output) if markdown_output is not None else None
                    ),
                }
            )
        elif args.command == "episode-review-show":
            _print(
                query_episode_review(
                    load_episode_review(args.artifact),
                    section=args.section,
                    fact_id=args.fact_id,
                    content_id=args.content_id,
                )
            )
        elif args.command == "episode-review-validate":
            artifact = load_episode_review(args.artifact)
            if args.source_replay:
                if not args.input_bundle:
                    raise ValueError("--source-replay requires --input-bundle")
                validation = replay_validate_episode_review(
                    artifact,
                    input_bundle=load_review_input_bundle(args.input_bundle),
                )
            else:
                validation = validate_episode_review(artifact)
            _print(validation)
            if validation["validation_status"] == "blocked":
                return 2
        elif args.command == "episode-review-interpret":
            facts_artifact = load_episode_review(args.artifact)
            parameters = json.loads(args.parameters_json)
            if not isinstance(parameters, dict):
                raise ValueError("--parameters-json must decode to an object")
            provider = (
                UnavailableInterpretationProvider(args.model_id)
                if args.simulate_unavailable
                else RecordedResponseProvider(
                    args.model_id,
                    Path(args.model_response).read_text(encoding="utf-8"),
                )
            )
            result = build_model_assisted_episode_review(
                facts_artifact,
                provider=provider,
                attempted_at=args.generated_at,
                parameters=parameters,
            )
            output = save_episode_review(args.output, result.artifact)
            attempt_output = save_interpretation_attempt(
                args.attempt_output, result.attempt
            )
            _print(
                {
                    "status": result.attempt["status"],
                    "used_fallback": result.used_fallback,
                    "content_id": result.artifact["content_id"],
                    "attempt_content_id": result.attempt["content_id"],
                    "output": str(output),
                    "attempt_output": str(attempt_output),
                }
            )
        elif args.command == "episode-review-correct":
            source = load_episode_review(args.artifact)
            revised = apply_human_review(
                source, load_human_review_request(args.request)
            )
            output = save_new_episode_review(args.output, revised)
            _print(
                {
                    "status": "accepted",
                    "action": revised["governance"]["human_reviews"][-1]["action"],
                    "review_id": revised["review_id"],
                    "revision_no": revised["revision"]["revision_no"],
                    "content_id": revised["content_id"],
                    "supersedes_content_id": revised["revision"][
                        "supersedes_content_id"
                    ],
                    "output": str(output),
                }
            )
        elif args.command == "episode-review-render":
            artifact = load_episode_review(args.artifact)
            output = atomic_create_bytes(
                args.output, render_episode_review_markdown(artifact).encode("utf-8")
            )
            _print(
                {
                    "status": "accepted",
                    "review_id": artifact["review_id"],
                    "revision_no": artifact["revision"]["revision_no"],
                    "content_id": artifact["content_id"],
                    "output": str(output),
                }
            )
        elif args.command == "episode-review-diff":
            _print(
                diff_episode_reviews(
                    load_episode_review(args.before), load_episode_review(args.after)
                )
            )
        elif args.command == "episode-review-revision-list":
            artifacts = [load_episode_review(path) for path in args.artifact]
            validation = validate_revision_chain(artifacts)
            _print(
                {
                    "validation": validation,
                    "revisions": list_episode_review_revisions(artifacts),
                }
            )
        elif args.command == "behavior-cohort-build":
            artifact = build_behavior_cohort(
                _load_json_documents(args.episode_review),
                _load_json_documents(args.input_bundle),
                effective_from=args.effective_from,
                effective_to=args.effective_to,
                knowledge_cutoff=args.knowledge_cutoff,
                effective_anchor=args.effective_anchor,
                filters={
                    "account_ids": args.account,
                    "instrument_ids": args.instrument,
                },
            )
            validation = validate_behavior_cohort(artifact)
            if validation["validation_status"] == "blocked":
                raise ValueError("P2G-1 behavior cohort failed structural validation")
            output = save_behavior_cohort(args.output, artifact)
            _print(
                {
                    "status": validation["validation_status"],
                    "content_id": artifact["content_id"],
                    "cohort_id": artifact["cohort_id"],
                    "included_review_count": artifact["counts"]["included_review_count"],
                    "excluded_candidate_count": artifact["counts"]["excluded_candidate_count"],
                    "release_readiness": artifact["release_readiness"]["status"],
                    "source_verification": artifact["source_verification"]["status"],
                    "output": str(output),
                }
            )
            if (
                artifact["release_readiness"]["status"] != "ready"
                or artifact["source_verification"]["status"] != "verified"
            ):
                return 2
        elif args.command == "behavior-cohort-show":
            _print(
                query_behavior_cohort(
                    load_behavior_cohort(args.artifact),
                    episode_id=args.episode_id,
                    review_id=args.review_id,
                    reason_code=args.reason_code,
                    content_id=args.content_id,
                )
            )
        elif args.command == "behavior-cohort-validate":
            artifact = load_behavior_cohort(args.artifact)
            if args.source_replay:
                if not args.episode_review or not args.input_bundle:
                    raise ValueError(
                        "--source-replay requires --episode-review and --input-bundle"
                    )
                validation = replay_validate_behavior_cohort(
                    artifact,
                    episode_reviews=_load_json_documents(args.episode_review),
                    input_bundles=_load_json_documents(args.input_bundle),
                )
            else:
                validation = validate_behavior_cohort(artifact)
            _print(validation)
            if (
                validation["validation_status"] == "blocked"
                or artifact["release_readiness"]["status"] != "ready"
                or artifact["source_verification"]["status"] != "verified"
            ):
                return 2
        elif args.command == "behavior-observation-build":
            cohort = load_behavior_cohort(args.cohort)
            detector_config = None
            if args.detector_config:
                detector_config = json.loads(
                    Path(args.detector_config).read_text(encoding="utf-8")
                )
                if not isinstance(detector_config, dict):
                    raise ValueError("--detector-config must contain one JSON object")
            artifact = build_behavior_observation_set(
                cohort,
                detector_config=detector_config,
                detectors=args.detector or None,
            )
            validation = validate_behavior_observation_set(artifact)
            if validation["validation_status"] == "blocked":
                raise ValueError("P2G-2 observation set failed structural validation")
            output = save_behavior_observation_set(args.output, artifact)
            _print(
                {
                    "status": validation["validation_status"],
                    "content_id": artifact["content_id"],
                    "observation_set_id": artifact["observation_set_id"],
                    "evaluation_count": artifact["counts"]["evaluation_count"],
                    "release_readiness": artifact["release_readiness"]["status"],
                    "source_verification": artifact["source_verification"]["status"],
                    "output": str(output),
                }
            )
            if (
                artifact["release_readiness"]["status"] != "ready"
                or artifact["source_verification"]["status"] != "verified"
            ):
                return 2
        elif args.command == "behavior-observation-show":
            _print(
                query_behavior_observation_set(
                    load_behavior_observation_set(args.artifact),
                    evaluation_id=args.evaluation_id,
                    detector_id=args.detector_id,
                    status=args.status,
                    episode_id=args.episode_id,
                    review_id=args.review_id,
                    account_id=args.account_id,
                    instrument_id=args.instrument_id,
                    reason_code=args.reason_code,
                    content_id=args.content_id,
                )
            )
        elif args.command == "behavior-observation-validate":
            artifact = load_behavior_observation_set(args.artifact)
            if args.source_replay:
                if not args.cohort:
                    raise ValueError("--source-replay requires --cohort")
                validation = replay_validate_behavior_observation_set(
                    artifact,
                    cohort=load_behavior_cohort(args.cohort),
                )
            else:
                validation = validate_behavior_observation_set(artifact)
            _print(validation)
            if (
                validation["validation_status"] == "blocked"
                or artifact["release_readiness"]["status"] != "ready"
                or artifact["source_verification"]["status"] != "verified"
            ):
                return 2
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
