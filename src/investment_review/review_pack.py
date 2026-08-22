"""Build deterministic, auditable review fact packs from P2C trade episodes.

This module intentionally stops at the factual boundary.  It copies the source
trade episode, derives a stable timeline/read model, surfaces unresolved links,
and records cryptographic provenance.  It does not infer motives, emotions,
trade quality, or counterfactual outcomes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "investment-review.review-fact-pack.v1"
INDEX_SCHEMA_VERSION = "investment-review.review-fact-pack-index.v1"
INTERPRETATION_STATUS = "not_inferred"

_EPISODE_LIST_KEYS = ("episodes", "trade_episodes", "items")
_EPISODE_ID_KEYS = ("episode_id", "trade_episode_id", "id")
_SYMBOL_KEYS = ("symbol", "ticker", "security_code", "instrument_id", "asset_id")
_OPENED_AT_KEYS = ("opened_at", "open_at", "started_at", "entry_at", "start_at")
_CLOSED_AT_KEYS = ("closed_at", "close_at", "ended_at", "exit_at", "end_at")
_STATUS_KEYS = ("episode_status", "status", "state")
_CUTOFF_KEYS = ("cutoff_at", "knowledge_cutoff", "as_of", "built_through")
_EVENT_TIME_KEYS = (
    "occurred_at",
    "event_at",
    "event_time",
    "timestamp",
    "at",
    "executed_at",
    "filled_at",
    "trade_at",
    "submitted_at",
    "effective_at",
    "known_at",
    "as_of",
    "snapshot_as_of",
    "created_at",
)
_EVENT_KIND_KEYS = ("event_type", "type", "kind", "action", "side")
_COLLECTION_KINDS = {
    "timeline": "event",
    "events": "event",
    "event_refs": "event",
    "fills": "fill",
    "trades": "fill",
    "executions": "fill",
    "orders": "order",
    "snapshots": "snapshot",
    "portfolio_snapshots": "portfolio_snapshot",
    "position_snapshots": "position_snapshot",
    "snapshot_links": "snapshot_link",
    "decisions": "decision",
    "decision_links": "decision_link",
    "information_events": "information_event",
}
_UNRESOLVED_STATUSES = {"missing", "unlinked", "ambiguous", "invalid"}
_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ReviewPackError(RuntimeError):
    """Raised for invalid inputs or an unsafe build request."""


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json_bytes(value: Any) -> bytes:
    """Return canonical JSON bytes used for semantic hashes.

    Compact encoding is used for hashing so hashes do not depend on the pretty
    formatting used for files on disk.
    """

    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _reject_json_constant(constant: str) -> None:
    raise ValueError(f"non-standard JSON constant: {constant}")


def _pretty_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _load_json_bytes(path: Path) -> tuple[bytes, Any]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ReviewPackError(f"cannot read source artifact {path}: {exc}") from exc
    try:
        value = json.loads(
            raw.decode("utf-8-sig"),
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ReviewPackError(f"source artifact is not valid UTF-8 JSON: {path}: {exc}") from exc
    return raw, value


def _json_pointer_token(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def _pointer(parent: str, token: str | int) -> str:
    escaped = _json_pointer_token(str(token))
    return f"{parent}/{escaped}" if parent else f"/{escaped}"


def _first_present(mapping: Mapping[str, Any], keys: Sequence[str]) -> Any:
    for key in keys:
        if key in mapping and mapping[key] not in (None, ""):
            return mapping[key]
    return None


def _nested_first_present(value: Any, keys: Sequence[str], *, max_depth: int = 2) -> Any:
    if not isinstance(value, Mapping):
        return None
    direct = _first_present(value, keys)
    if direct is not None:
        return direct
    if max_depth <= 0:
        return None
    for nested_key in ("identity", "scope", "instrument", "security", "metadata", "summary"):
        nested = value.get(nested_key)
        found = _nested_first_present(nested, keys, max_depth=max_depth - 1)
        if found is not None:
            return found
    return None


def _as_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    if isinstance(value, (int, float, bool)):
        return str(value)
    return None


def _looks_like_episode(value: Mapping[str, Any]) -> bool:
    marker_keys = (
        set(_EPISODE_ID_KEYS)
        | set(_SYMBOL_KEYS)
        | set(_OPENED_AT_KEYS)
        | set(_COLLECTION_KINDS)
    )
    return any(key in value for key in marker_keys)


def _extract_episode_container(document: Any) -> tuple[list[Mapping[str, Any]], Mapping[str, Any]]:
    if isinstance(document, list):
        raw_episodes = document
        metadata: Mapping[str, Any] = {}
    elif isinstance(document, Mapping):
        list_key = next(
            (key for key in _EPISODE_LIST_KEYS if isinstance(document.get(key), list)),
            None,
        )
        if list_key is None:
            if _looks_like_episode(document):
                raw_episodes = [document]
                metadata = {}
            else:
                expected = ", ".join(_EPISODE_LIST_KEYS)
                raise ReviewPackError(
                    "P2C artifact must be a list, one episode object, or an object "
                    f"containing one of: {expected}"
                )
        else:
            raw_episodes = document[list_key]
            metadata = {key: value for key, value in document.items() if key != list_key}
    else:
        raise ReviewPackError("P2C artifact root must be a JSON object or array")

    episodes: list[Mapping[str, Any]] = []
    for index, item in enumerate(raw_episodes):
        if not isinstance(item, Mapping):
            raise ReviewPackError(f"episode at index {index} is not a JSON object")
        episodes.append(item)
    return episodes, metadata


def _extract_cutoff(metadata: Mapping[str, Any], explicit_cutoff: str | None) -> str | None:
    if explicit_cutoff:
        return explicit_cutoff
    found = _nested_first_present(metadata, _CUTOFF_KEYS)
    return _as_text(found)


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _timeline_sort_key(item: Mapping[str, Any]) -> tuple[int, str, str, int]:
    timestamp = item.get("at")
    parsed = _parse_timestamp(timestamp)
    if parsed is not None:
        normalized = parsed.isoformat(timespec="microseconds")
        unknown = 0
    elif timestamp is not None:
        normalized = str(timestamp)
        unknown = 1
    else:
        normalized = ""
        unknown = 2
    raw_sequence = item.get("source_sequence", 0)
    try:
        sequence = int(raw_sequence)
    except (TypeError, ValueError):
        sequence = 0
    return (
        unknown,
        normalized,
        str(item.get("source_pointer", "")),
        sequence,
    )


def _extract_timeline(episode: Mapping[str, Any]) -> list[dict[str, Any]]:
    timeline: list[dict[str, Any]] = []
    canonical_timeline = episode.get("timeline")
    if isinstance(canonical_timeline, list) and canonical_timeline:
        collections = (("timeline", _COLLECTION_KINDS["timeline"]),)
    else:
        collections = tuple(
            (name, kind) for name, kind in _COLLECTION_KINDS.items() if name != "timeline"
        )
    for collection_name, default_kind in collections:
        collection = episode.get(collection_name)
        if not isinstance(collection, list):
            continue
        for index, item in enumerate(collection):
            pointer = _pointer(_pointer("", collection_name), index)
            if isinstance(item, Mapping):
                at = _nested_first_present(item, _EVENT_TIME_KEYS, max_depth=1)
                kind = _as_text(_first_present(item, _EVENT_KIND_KEYS)) or default_kind
                facts: Any = item
            else:
                at = None
                kind = default_kind
                facts = item
            timeline.append(
                {
                    "at": at,
                    "kind": kind,
                    "source_collection": collection_name,
                    "source_pointer": pointer,
                    "source_sequence": index,
                    "facts": facts,
                }
            )
    timeline.sort(key=_timeline_sort_key)
    return timeline


def _walk_unresolved(value: Any, pointer: str = "") -> Iterable[dict[str, str]]:
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_pointer = _pointer(pointer, key)
            key_lower = str(key).lower()
            if isinstance(child, str) and (
                key_lower == "status"
                or key_lower.endswith("_status")
                or key_lower in {"linkage", "link_state", "resolution"}
            ):
                status = child.strip().lower()
                if status in _UNRESOLVED_STATUSES:
                    yield {"pointer": child_pointer, "status": status}
            yield from _walk_unresolved(child, child_pointer)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_unresolved(child, _pointer(pointer, index))


def _dedupe_records(records: Iterable[Mapping[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    output: list[dict[str, str]] = []
    for record in records:
        pair = (record["pointer"], record["status"])
        if pair in seen:
            continue
        seen.add(pair)
        output.append({"pointer": pair[0], "status": pair[1]})
    output.sort(key=lambda item: (item["status"], item["pointer"]))
    return output


def _safe_filename_token(value: str, *, limit: int = 80) -> str:
    normalized = _SAFE_FILENAME_RE.sub("_", value.strip()).strip("._-")
    if not normalized:
        normalized = "episode"
    return normalized[:limit]


def _episode_identity(episode: Mapping[str, Any]) -> dict[str, str | None]:
    return {
        "symbol": _as_text(_nested_first_present(episode, _SYMBOL_KEYS)),
        "opened_at": _as_text(_nested_first_present(episode, _OPENED_AT_KEYS)),
        "closed_at": _as_text(_nested_first_present(episode, _CLOSED_AT_KEYS)),
        "status": _as_text(_nested_first_present(episode, _STATUS_KEYS)),
    }


def _episode_id(episode: Mapping[str, Any], episode_hash: str) -> tuple[str, bool]:
    explicit = _as_text(_first_present(episode, _EPISODE_ID_KEYS))
    if explicit:
        return explicit, False
    return f"synthetic:{episode_hash[:20]}", True


def _bundle_id(source_hash: str, episode_hash: str, episode_id: str) -> str:
    seed = "\0".join((SCHEMA_VERSION, source_hash, episode_hash, episode_id)).encode("utf-8")
    return f"rfp_{_sha256_bytes(seed)[:24]}"


def build_review_pack(
    episode: Mapping[str, Any],
    *,
    source_hash: str,
    source_label: str,
    cutoff_at: str | None,
    source_index: int,
) -> dict[str, Any]:
    """Build one review fact pack without mutating the source episode."""

    episode_object = dict(episode)
    episode_hash = _sha256_bytes(_canonical_json_bytes(episode_object))
    episode_id, synthetic_id = _episode_id(episode_object, episode_hash)
    identity = _episode_identity(episode_object)
    timeline = _extract_timeline(episode_object)
    unresolved = _dedupe_records(_walk_unresolved(episode_object))

    missing_core_fields: list[str] = []
    if synthetic_id:
        missing_core_fields.append("episode_id")
    if identity["symbol"] is None:
        missing_core_fields.append("symbol")
    if identity["opened_at"] is None:
        missing_core_fields.append("opened_at")

    warnings: list[str] = []
    if synthetic_id:
        warnings.append(
            "source episode has no explicit identifier; "
            "a deterministic synthetic id was assigned"
        )
    if not timeline:
        warnings.append("no recognized event collection was available for a derived timeline")
    if any(item["at"] is None for item in timeline):
        warnings.append("one or more timeline entries have no recognized timestamp")

    unresolved_by_status = {
        status: [item for item in unresolved if item["status"] == status]
        for status in sorted(_UNRESOLVED_STATUSES)
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "bundle_id": _bundle_id(source_hash, episode_hash, episode_id),
        "episode_id": episode_id,
        "source": {
            "artifact_label": source_label,
            "artifact_sha256": source_hash,
            "episode_index": source_index,
            "episode_sha256": episode_hash,
        },
        "cutoff_at": cutoff_at,
        "identity": identity,
        "timeline": timeline,
        "linkage_diagnostics": {
            "unresolved": unresolved,
            "by_status": unresolved_by_status,
        },
        "completeness": {
            "missing_core_fields": sorted(missing_core_fields),
            "timeline_entry_count": len(timeline),
            "unresolved_link_count": len(unresolved),
            "warnings": warnings,
        },
        "interpretation": {
            "status": INTERPRETATION_STATUS,
            "reason": (
                "This artifact preserves and organizes P2C facts only. "
                "Decision motives, behavioral labels, quality judgments, "
                "and counterfactuals are out of scope."
            ),
        },
        "source_episode": episode_object,
    }


def _prepare_output_dir(output_dir: Path, *, overwrite: bool) -> None:
    if output_dir.exists() and not output_dir.is_dir():
        raise ReviewPackError(f"output path exists and is not a directory: {output_dir}")
    if output_dir.exists():
        entries = list(output_dir.iterdir())
        if entries and not overwrite:
            raise ReviewPackError(
                f"output directory is not empty: {output_dir}; "
                "pass --overwrite to replace generated content"
            )
        if overwrite:
            for child in entries:
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()
    else:
        output_dir.mkdir(parents=True)


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(file_descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def _select_episodes(
    episodes: Sequence[Mapping[str, Any]], selected_ids: Sequence[str]
) -> list[tuple[int, Mapping[str, Any]]]:
    indexed = list(enumerate(episodes))
    if not selected_ids:
        return indexed
    wanted = set(selected_ids)
    selected: list[tuple[int, Mapping[str, Any]]] = []
    matched: set[str] = set()
    for index, episode in indexed:
        episode_hash = _sha256_bytes(_canonical_json_bytes(dict(episode)))
        current_id, _ = _episode_id(episode, episode_hash)
        if current_id in wanted:
            selected.append((index, episode))
            matched.add(current_id)
    missing = sorted(wanted - matched)
    if missing:
        raise ReviewPackError(f"requested episode id(s) not found: {', '.join(missing)}")
    return selected


def build_review_packs(
    source_path: Path,
    output_dir: Path,
    *,
    selected_ids: Sequence[str] = (),
    cutoff_at: str | None = None,
    source_label: str | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Build one JSON file per selected episode plus a deterministic index."""

    raw_source, document = _load_json_bytes(source_path)
    episodes, metadata = _extract_episode_container(document)
    selected = _select_episodes(episodes, selected_ids)
    source_hash = _sha256_bytes(raw_source)
    label = source_label or source_path.name
    effective_cutoff = _extract_cutoff(metadata, cutoff_at)

    _prepare_output_dir(output_dir, overwrite=overwrite)

    index_entries: list[dict[str, Any]] = []
    used_filenames: set[str] = set()
    for source_index, episode in selected:
        pack = build_review_pack(
            episode,
            source_hash=source_hash,
            source_label=label,
            cutoff_at=effective_cutoff,
            source_index=source_index,
        )
        base = _safe_filename_token(str(pack["episode_id"]))
        filename = f"episode_{base}__{pack['source']['episode_sha256'][:12]}.json"
        if filename in used_filenames:
            raise ReviewPackError(f"duplicate generated filename: {filename}")
        used_filenames.add(filename)

        output_bytes = _pretty_json_bytes(pack)
        _atomic_write(output_dir / filename, output_bytes)
        identity = pack["identity"]
        index_entries.append(
            {
                "episode_id": pack["episode_id"],
                "bundle_id": pack["bundle_id"],
                "file": filename,
                "file_sha256": _sha256_bytes(output_bytes),
                "episode_sha256": pack["source"]["episode_sha256"],
                "source_index": source_index,
                "symbol": identity["symbol"],
                "opened_at": identity["opened_at"],
                "closed_at": identity["closed_at"],
                "status": identity["status"],
                "timeline_entry_count": pack["completeness"]["timeline_entry_count"],
                "unresolved_link_count": pack["completeness"]["unresolved_link_count"],
                "warning_count": len(pack["completeness"]["warnings"]),
            }
        )

    index_entries.sort(
        key=lambda item: (
            item["opened_at"] is None,
            item["opened_at"] or "",
            item["episode_id"],
            item["episode_sha256"],
        )
    )
    index = {
        "schema_version": INDEX_SCHEMA_VERSION,
        "source": {
            "artifact_label": label,
            "artifact_sha256": source_hash,
        },
        "cutoff_at": effective_cutoff,
        "episode_count": len(index_entries),
        "bundles": index_entries,
    }
    _atomic_write(output_dir / "index.json", _pretty_json_bytes(index))
    return index


def _read_json_file(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReviewPackError(f"cannot read JSON file {path}: {exc}") from exc


def validate_review_pack_directory(
    bundle_dir: Path,
    *,
    source_path: Path | None = None,
) -> list[str]:
    """Return validation errors; an empty list means the directory is valid."""

    errors: list[str] = []
    index_path = bundle_dir / "index.json"
    try:
        index = _read_json_file(index_path)
    except ReviewPackError as exc:
        return [str(exc)]
    if not isinstance(index, Mapping):
        return ["index.json root is not an object"]
    if index.get("schema_version") != INDEX_SCHEMA_VERSION:
        errors.append(f"index schema_version must be {INDEX_SCHEMA_VERSION}")
    source = index.get("source")
    if not isinstance(source, Mapping):
        errors.append("index source is not an object")
        source_hash = None
    else:
        source_hash = source.get("artifact_sha256")
        if not isinstance(source_hash, str) or _SHA256_RE.fullmatch(source_hash) is None:
            errors.append("index source.artifact_sha256 is not a SHA-256 hex digest")

    if source_path is not None:
        try:
            source_bytes = source_path.read_bytes()
        except OSError as exc:
            errors.append(f"cannot read validation source artifact {source_path}: {exc}")
        else:
            actual_source_hash = _sha256_bytes(source_bytes)
            if source_hash != actual_source_hash:
                errors.append(
                    "source artifact hash mismatch: "
                    f"index={source_hash} actual={actual_source_hash}"
                )

    bundles = index.get("bundles")
    if not isinstance(bundles, list):
        return errors + ["index bundles is not an array"]
    if index.get("episode_count") != len(bundles):
        errors.append("index episode_count does not equal number of bundle entries")

    seen_files: set[str] = set()
    seen_bundle_ids: set[str] = set()
    for entry_index, entry in enumerate(bundles):
        prefix = f"bundles[{entry_index}]"
        if not isinstance(entry, Mapping):
            errors.append(f"{prefix} is not an object")
            continue
        filename = entry.get("file")
        if not isinstance(filename, str) or not filename:
            errors.append(f"{prefix}.file is missing")
            continue
        if filename in seen_files:
            errors.append(f"duplicate bundle filename in index: {filename}")
        seen_files.add(filename)
        if Path(filename).name != filename:
            errors.append(f"{prefix}.file must be a basename, not a path: {filename}")
            continue
        bundle_path = bundle_dir / filename
        try:
            raw_bundle = bundle_path.read_bytes()
        except OSError as exc:
            errors.append(f"cannot read bundle {filename}: {exc}")
            continue
        actual_file_hash = _sha256_bytes(raw_bundle)
        if entry.get("file_sha256") != actual_file_hash:
            errors.append(f"bundle file hash mismatch: {filename}")
        try:
            bundle = json.loads(raw_bundle.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            errors.append(f"bundle is not valid UTF-8 JSON: {filename}: {exc}")
            continue
        if not isinstance(bundle, Mapping):
            errors.append(f"bundle root is not an object: {filename}")
            continue
        if bundle.get("schema_version") != SCHEMA_VERSION:
            errors.append(f"bundle schema_version is invalid: {filename}")
        episode_id = bundle.get("episode_id")
        bundle_id = bundle.get("bundle_id")
        if entry.get("episode_id") != episode_id:
            errors.append(f"episode_id mismatch between index and bundle: {filename}")
        if entry.get("bundle_id") != bundle_id:
            errors.append(f"bundle_id mismatch between index and bundle: {filename}")
        if isinstance(bundle_id, str):
            if bundle_id in seen_bundle_ids:
                errors.append(f"duplicate bundle_id: {bundle_id}")
            seen_bundle_ids.add(bundle_id)

        bundle_source = bundle.get("source")
        source_episode = bundle.get("source_episode")
        if not isinstance(bundle_source, Mapping):
            errors.append(f"bundle source is not an object: {filename}")
            continue
        if not isinstance(source_episode, Mapping):
            errors.append(f"bundle source_episode is not an object: {filename}")
            continue
        if source_hash is not None and bundle_source.get("artifact_sha256") != source_hash:
            errors.append(f"source artifact hash mismatch inside bundle: {filename}")
        episode_hash = _sha256_bytes(_canonical_json_bytes(dict(source_episode)))
        if bundle_source.get("episode_sha256") != episode_hash:
            errors.append(f"source episode hash mismatch: {filename}")
        if isinstance(episode_id, str) and isinstance(source_hash, str):
            expected_bundle_id = _bundle_id(source_hash, episode_hash, episode_id)
            if bundle_id != expected_bundle_id:
                errors.append(f"derived bundle_id mismatch: {filename}")

        interpretation = bundle.get("interpretation")
        if (
            not isinstance(interpretation, Mapping)
            or interpretation.get("status") != INTERPRETATION_STATUS
        ):
            errors.append(f"interpretation boundary is missing or changed: {filename}")
        timeline = bundle.get("timeline")
        if not isinstance(timeline, list):
            errors.append(f"timeline is not an array: {filename}")
        elif not all(isinstance(item, Mapping) for item in timeline):
            errors.append(f"timeline contains a non-object entry: {filename}")
        elif timeline != sorted(timeline, key=_timeline_sort_key):
            errors.append(f"timeline is not in deterministic order: {filename}")

    return errors


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="investment-review-review-pack",
        description=(
            "Build and validate deterministic P2D review fact packs "
            "from P2C trade episodes."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build", help="build review fact packs")
    build_parser.add_argument(
        "--episodes",
        type=Path,
        required=True,
        help="P2C trade episode JSON artifact",
    )
    build_parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="directory for index.json and episode bundles",
    )
    build_parser.add_argument(
        "--episode-id",
        action="append",
        default=[],
        help="build only this episode id; may be repeated",
    )
    build_parser.add_argument(
        "--cutoff-at",
        help="explicit knowledge cutoff copied into every bundle",
    )
    build_parser.add_argument(
        "--source-label",
        help="non-sensitive source label stored in bundles; defaults to the source filename",
    )
    build_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="replace all existing content in --output-dir",
    )

    validate_parser = subparsers.add_parser(
        "validate",
        help="validate hashes, ordering, and factual boundary",
    )
    validate_parser.add_argument("--bundle-dir", type=Path, required=True)
    validate_parser.add_argument(
        "--episodes",
        type=Path,
        help="optional original P2C artifact; validates the source artifact hash",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            index = build_review_packs(
                args.episodes,
                args.output_dir,
                selected_ids=args.episode_id,
                cutoff_at=args.cutoff_at,
                source_label=args.source_label,
                overwrite=args.overwrite,
            )
            print(
                json.dumps(
                    {
                        "status": "ok",
                        "episode_count": index["episode_count"],
                        "output_dir": str(args.output_dir),
                        "source_sha256": index["source"]["artifact_sha256"],
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "validate":
            errors = validate_review_pack_directory(args.bundle_dir, source_path=args.episodes)
            if errors:
                print(
                    json.dumps(
                        {"status": "invalid", "errors": errors},
                        ensure_ascii=False,
                        indent=2,
                    )
                )
                return 2
            print(
                json.dumps(
                    {"status": "ok", "bundle_dir": str(args.bundle_dir)},
                    ensure_ascii=False,
                )
            )
            return 0
    except ReviewPackError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    parser.error(f"unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
