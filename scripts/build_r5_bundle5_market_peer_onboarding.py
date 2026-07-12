#!/usr/bin/env python3
"""Acquire, archive and review Bundle 5.3 market/peer inputs."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
for module_path in (REPO_ROOT / "src", REPO_ROOT / "src/ingest"):
    if str(module_path) not in sys.path:
        sys.path.insert(0, str(module_path))

from evidence_io import EVIDENCE_FIELDNAMES, INGEST_RUN_FIELDNAMES, read_csv_dicts, utc_now_iso, write_csv_rows  # noqa: E402
from utils.tushare_client import get_tushare_pro  # noqa: E402

WORKFLOW_ID = "wf_20260703_stock_first_002837_invic"
STOCK_CODE = "002837"
TRADE_DATE = "20260710"
TS_CODES = ("002837.SZ", "301018.SZ", "300499.SZ", "300731.SZ", "300602.SZ")
INCLUDED_PEERS = ("301018", "300499")
EXCLUDED_PEERS = ("300731", "300602")
STOCK_NAMES = {
    "002837": "英维克",
    "301018": "申菱环境",
    "300499": "高澜股份",
    "300731": "科创新源",
    "300602": "飞荣达",
}
DAILY_BASIC_FIELDS = (
    "ts_code,trade_date,close,turnover_rate,volume_ratio,pe,pe_ttm,pb,ps,ps_ttm,"
    "dv_ratio,dv_ttm,total_share,float_share,free_share,total_mv,circ_mv"
)
UNIT_CONTRACT = {
    "close": "CNY_per_share",
    "turnover_rate": "pct",
    "volume_ratio": "multiple",
    "pe": "multiple",
    "pe_ttm": "multiple",
    "pb": "multiple",
    "ps": "multiple",
    "ps_ttm": "multiple",
    "dv_ratio": "pct",
    "dv_ttm": "pct",
    "total_share": "native_10k_shares_to_shares_x10000",
    "float_share": "native_10k_shares_to_shares_x10000",
    "free_share": "native_10k_shares_to_shares_x10000",
    "total_mv": "native_10k_CNY_to_CNY_x10000",
    "circ_mv": "native_10k_CNY_to_CNY_x10000",
}
NORMALIZED_FIELDS = [
    "stock_code",
    "ts_code",
    "stock_name",
    "trade_date",
    "close_price",
    "close_price_unit",
    "turnover_rate_pct",
    "volume_ratio",
    "pe",
    "pe_ttm",
    "pb",
    "ps",
    "ps_ttm",
    "total_share",
    "total_share_unit",
    "float_share",
    "free_share",
    "market_cap",
    "market_cap_unit",
    "circulating_market_cap",
    "normalization_method",
    "source_evidence_id",
]


def _clean_row(row: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in row.items():
        if value is None:
            result[str(key)] = None
            continue
        try:
            if value != value:
                result[str(key)] = None
                continue
        except TypeError:
            pass
        if hasattr(value, "item"):
            value = value.item()
        result[str(key)] = value
    return result


def fetch_live_rows(env_file: Path, trade_date: str = TRADE_DATE) -> list[dict[str, Any]]:
    pro = get_tushare_pro(env_file)
    calendar = pro.trade_cal(
        exchange="SSE",
        start_date=trade_date,
        end_date=trade_date,
        fields="cal_date,is_open,pretrade_date",
    )
    calendar_rows = calendar.to_dict(orient="records")
    if not calendar_rows or int(calendar_rows[0].get("is_open") or 0) != 1:
        raise RuntimeError(f"requested snapshot date is not an open trading day: {trade_date}")
    rows: list[dict[str, Any]] = []
    for ts_code in TS_CODES:
        frame = pro.daily_basic(ts_code=ts_code, trade_date=trade_date, fields=DAILY_BASIC_FIELDS)
        current = frame.to_dict(orient="records")
        if len(current) != 1:
            raise RuntimeError(f"expected one daily_basic row for {ts_code} on {trade_date}, got {len(current)}")
        rows.append(_clean_row(current[0]))
    return sorted(rows, key=lambda row: str(row.get("ts_code")))


def load_fixture_rows(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("rows") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise ValueError("fixture JSON must be a list or an object with rows")
    return sorted([_clean_row(dict(row)) for row in rows], key=lambda row: str(row.get("ts_code")))


def validate_raw_rows(rows: list[dict[str, Any]], trade_date: str = TRADE_DATE) -> None:
    by_code = {str(row.get("ts_code")): row for row in rows}
    if set(by_code) != set(TS_CODES):
        raise ValueError(f"snapshot code set mismatch: {sorted(by_code)}")
    required = {"trade_date", "close", "pe_ttm", "pb", "ps_ttm", "total_share", "total_mv"}
    for ts_code, row in by_code.items():
        if str(row.get("trade_date")) != trade_date:
            raise ValueError(f"mixed trade date for {ts_code}: {row.get('trade_date')}")
        missing = sorted(field for field in required if row.get(field) in {None, ""})
        if missing:
            raise ValueError(f"missing required fields for {ts_code}: {missing}")


def raw_payload(rows: list[dict[str, Any]], trade_date: str = TRADE_DATE) -> dict[str, Any]:
    validate_raw_rows(rows, trade_date)
    return {
        "schema_version": "r5_bundle5_tushare_daily_basic_snapshot_v0.1",
        "source_name": "tushare",
        "api_name": "daily_basic",
        "trade_date": trade_date,
        "request_fields": DAILY_BASIC_FIELDS,
        "unit_contract": UNIT_CONTRACT,
        "rows": rows,
    }


def _canonical_json_bytes(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _write_immutable(path: Path, data: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(data).hexdigest()
    if path.exists():
        current = hashlib.sha256(path.read_bytes()).hexdigest()
        if current != digest:
            raise FileExistsError(f"refusing to overwrite immutable evidence: {path}")
        return "unchanged"
    path.write_bytes(data)
    return "created"


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value))


def _number(value: Any) -> float | int | None:
    if value in {None, ""}:
        return None
    number = _decimal(value)
    if number == number.to_integral_value():
        return int(number)
    return float(number)


def normalize_rows(rows: list[dict[str, Any]], evidence_id: str) -> list[dict[str, Any]]:
    validate_raw_rows(rows)
    normalized: list[dict[str, Any]] = []
    for row in sorted(rows, key=lambda item: str(item["ts_code"])):
        stock_code = str(row["ts_code"]).split(".", 1)[0]
        normalized.append(
            {
                "stock_code": stock_code,
                "ts_code": row["ts_code"],
                "stock_name": STOCK_NAMES[stock_code],
                "trade_date": row["trade_date"],
                "close_price": _number(row["close"]),
                "close_price_unit": "CNY_per_share",
                "turnover_rate_pct": _number(row.get("turnover_rate")),
                "volume_ratio": _number(row.get("volume_ratio")),
                "pe": _number(row.get("pe")),
                "pe_ttm": _number(row.get("pe_ttm")),
                "pb": _number(row.get("pb")),
                "ps": _number(row.get("ps")),
                "ps_ttm": _number(row.get("ps_ttm")),
                "total_share": _number(_decimal(row["total_share"]) * Decimal("10000")),
                "total_share_unit": "shares",
                "float_share": _number(_decimal(row.get("float_share") or 0) * Decimal("10000")),
                "free_share": _number(_decimal(row.get("free_share") or 0) * Decimal("10000")),
                "market_cap": _number(_decimal(row["total_mv"]) * Decimal("10000")),
                "market_cap_unit": "CNY",
                "circulating_market_cap": _number(_decimal(row.get("circ_mv") or 0) * Decimal("10000")),
                "normalization_method": "Tushare daily_basic native 10k share/CNY fields multiplied by 10000; multiples unchanged",
                "source_evidence_id": evidence_id,
            }
        )
    return normalized


def _csv_bytes(rows: list[dict[str, Any]]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=NORMALIZED_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def peer_selection_review(repo_root: Path) -> dict[str, Any]:
    path = repo_root / "data/processed/normalized/segment_company_exposure.csv"
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = {row["stock_code"]: row for row in csv.DictReader(handle) if row.get("stock_code") in {STOCK_CODE, *INCLUDED_PEERS, *EXCLUDED_PEERS}}
    if set(rows) != {STOCK_CODE, *INCLUDED_PEERS, *EXCLUDED_PEERS}:
        raise ValueError("peer selection source does not contain the full candidate set")
    if rows["301018"]["exposure_type"] != "product" or rows["301018"]["exposure_score"] != "4":
        raise ValueError("301018 no longer meets the expected product-exposure contract")
    if rows["300499"]["exposure_type"] != "product" or rows["300499"]["exposure_score"] != "3":
        raise ValueError("300499 no longer meets the expected product-exposure contract")
    included = [
        {
            "stock_code": code,
            "stock_name": rows[code]["stock_name"],
            "exposure_type": rows[code]["exposure_type"],
            "exposure_score": int(rows[code]["exposure_score"]),
            "confidence": rows[code]["confidence"],
            "reason": "current local segment universe records product-level exposure; selected before reviewing valuation multiples",
        }
        for code in INCLUDED_PEERS
    ]
    excluded = [
        {
            "stock_code": code,
            "stock_name": rows[code]["stock_name"],
            "exposure_type": rows[code]["exposure_type"],
            "exposure_score": int(rows[code]["exposure_score"]),
            "confidence": rows[code]["confidence"],
            "reason": "current local universe records lower-scored technology-level rather than product-level exposure",
        }
        for code in EXCLUDED_PEERS
    ]
    return {
        "peer_set_id": "r5_b5_liquid_cooling_peer_set_20260710",
        "selection_source_path": "data/processed/normalized/segment_company_exposure.csv",
        "selection_sequence": "exposure comparability first, market multiples second",
        "included": included,
        "excluded": excluded,
        "peer_set_quality": "low",
        "quality_reason": "only two product-level candidates; 300499 exposure confidence is low and broad business mixes differ",
    }


def build_market_record(row: dict[str, Any], evidence_id: str, raw_path: str, reviewed_at: str) -> dict[str, Any]:
    rounded_product = float(Decimal(str(row["close_price"])) * Decimal(str(row["total_share"])))
    return {
        "input_id": "r5_b5_market_002837_20260710",
        "workflow_id": WORKFLOW_ID,
        "stock_code": STOCK_CODE,
        "input_type": "market_snapshot",
        "as_of_date": "2026-07-10",
        "source_evidence_id": evidence_id,
        "source_rank": "B",
        "review_status": "accepted",
        "reviewer": "codex",
        "reviewed_at": reviewed_at,
        "capture_method": "archived_tushare_snapshot_then_codex_offline_review_user_authorized",
        "no_live_api": True,
        "limitations": [
            "Trailing multiples reflect historical reported metrics and are not forward estimates.",
            "Source-reported market capitalization is retained instead of recomputing from rounded close and shares.",
        ],
        "market_date": "2026-07-10",
        "as_of_timestamp": "2026-07-10T15:00:00+08:00",
        "timezone": "Asia/Shanghai",
        "exchange": "SZSE",
        "price_adjustment_convention": "unadjusted_cash_close_from_daily_basic",
        "close_price": row["close_price"],
        "close_price_unit": "CNY_per_share",
        "share_count_basis": "daily_basic_total_share_end_of_day",
        "shares_outstanding": row["total_share"],
        "shares_outstanding_unit": "shares",
        "market_cap": row["market_cap"],
        "market_cap_unit": "CNY",
        "market_cap_method": "source_reported_total_mv_native_10k_CNY_x10000",
        "rounded_close_times_shares": rounded_product,
        "rounded_close_times_shares_difference_cny": round(float(row["market_cap"]) - rounded_product, 2),
        "currency": "CNY",
        "pe": row["pe"],
        "pe_ttm": row["pe_ttm"],
        "pb": row["pb"],
        "ps": row["ps"],
        "ps_ttm": row["ps_ttm"],
        "freshness_status": "latest_completed_trading_day_at_review",
        "source_path": raw_path,
        "sample_quality_allowed": False,
    }


def build_peer_records(
    normalized: list[dict[str, Any]],
    evidence_id: str,
    raw_path: str,
    reviewed_at: str,
    selection: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = {str(row["stock_code"]): row for row in normalized}
    selected = {item["stock_code"]: item for item in selection["included"]}
    records: list[dict[str, Any]] = []
    metric_specs = (
        ("pe_ttm", "TTM earnings as of 2026-07-10"),
        ("pb", "most recently reported equity as reflected by Tushare on 2026-07-10"),
        ("ps_ttm", "TTM revenue as of 2026-07-10"),
    )
    for peer_code in INCLUDED_PEERS:
        row = rows[peer_code]
        peer = selected[peer_code]
        for metric_name, basis in metric_specs:
            records.append(
                {
                    "input_id": f"r5_b5_peer_{peer_code}_{metric_name}_20260710",
                    "workflow_id": WORKFLOW_ID,
                    "stock_code": STOCK_CODE,
                    "input_type": "peer_snapshot",
                    "as_of_date": "2026-07-10",
                    "source_evidence_id": evidence_id,
                    "source_rank": "B",
                    "review_status": "accepted",
                    "reviewer": "codex",
                    "reviewed_at": reviewed_at,
                    "capture_method": "archived_tushare_snapshot_then_codex_offline_review_user_authorized",
                    "no_live_api": True,
                    "limitations": [
                        "Peer set has only two product-exposure candidates and is low confidence.",
                        "Business mixes and liquid-cooling financial disclosure remain non-identical.",
                    ],
                    "peer_set_id": selection["peer_set_id"],
                    "peer_stock_code": peer_code,
                    "peer_company_name": peer["stock_name"],
                    "peer_metric_name": metric_name,
                    "peer_metric_value": row[metric_name],
                    "peer_metric_unit": "multiple",
                    "metric_period": basis,
                    "accounting_basis": basis,
                    "normalization_method": "same-date Tushare daily_basic multiple; no cross-date interpolation",
                    "business_exposure_comparability": f"{peer['exposure_type']} exposure score {peer['exposure_score']}; confidence {peer['confidence']}",
                    "inclusion_reason": peer["reason"],
                    "selection_source_path": selection["selection_source_path"],
                    "source_path": raw_path,
                    "sample_quality_allowed": False,
                }
            )
    return records


def _write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _append_once(path: Path, fieldnames: list[str], row: dict[str, Any], key: str) -> str:
    existing = read_csv_dicts(path)
    matches = [item for item in existing if item.get(key) == str(row[key])]
    if matches:
        if key == "evidence_id" and matches[0].get("file_hash") != row.get("file_hash"):
            raise ValueError(f"existing evidence_id has different hash: {row[key]}")
        return "unchanged"
    write_csv_rows(path, fieldnames, [row])
    return "created"


def register_evidence(
    repo_root: Path,
    *,
    evidence_id: str,
    raw_rel: str,
    processed_rel: str,
    file_hash: str,
    params_hash: str,
    retrieved_at: str,
) -> dict[str, str]:
    row = {
        "evidence_id": evidence_id,
        "source_type": "structured_market_data",
        "source_name": "tushare",
        "source_group": "structured_database",
        "title": "Tushare same-date daily_basic snapshot for 002837 and reviewed peer candidates",
        "publisher": "Tushare Pro API via project-configured endpoint",
        "publish_date": "2026-07-10",
        "retrieved_at": retrieved_at,
        "ingested_at": retrieved_at,
        "as_of_date": "2026-07-10",
        "entity_type": "market",
        "entity_id": "002837",
        "segment_id": "ai_server_liquid_cooling",
        "company_id": "cn_002837_invic",
        "stock_code": STOCK_CODE,
        "source_url": "https://tushare.pro/document/2?doc_id=32",
        "raw_file_path": raw_rel,
        "raw_archive_policy": "immutable",
        "file_hash": file_hash,
        "content_hash": file_hash,
        "api_params_hash": params_hash,
        "processed_text_path": "",
        "processed_table_path": processed_rel,
        "page_map_path": "",
        "page_count": "",
        "language": "en",
        "file_format": "json",
        "ingest_mode": "tushare_live_reviewed_snapshot",
        "reliability_rank": "B",
        "material_claim_allowed": "metric_only",
        "allowed_claim_types": "metric_statement",
        "license_note": "Tushare terms; token stored outside artifacts",
        "stale_after": "7d",
        "status": "active",
        "parse_status": "normalized",
        "candidate_status": "generated",
        "review_status": "reviewed",
        "previous_evidence_id": "",
        "superseded_by": "",
        "notes": "unit-safe normalized snapshot; reviewer=codex; authorization_date=2026-07-12; no token persisted",
    }
    manifest_status = _append_once(repo_root / "data/manifests/evidence_manifest.csv", EVIDENCE_FIELDNAMES, row, "evidence_id")
    run_id = f"ingest_tushare_daily_basic_002837_{file_hash[:8]}"
    log_row = {
        "run_id": run_id,
        "ingest_mode": "tushare_live_reviewed_snapshot",
        "started_at": retrieved_at,
        "finished_at": utc_now_iso(),
        "result": "SUCCESS",
        "stock_code": STOCK_CODE,
        "source_name": "tushare",
        "source_type": "structured_market_data",
        "api_name": "daily_basic",
        "manifest_rows_created": "1" if manifest_status == "created" else "0",
        "manifest_rows_updated": "0",
        "metric_candidates": str(len(TS_CODES) * 5),
        "claim_candidates": "0",
        "issues": "",
        "notes": "same-date unit-safe market/peer snapshot; token not stored",
    }
    log_status = _append_once(repo_root / "data/manifests/ingest_runs.csv", INGEST_RUN_FIELDNAMES, log_row, "run_id")
    return {"manifest_status": manifest_status, "ingest_log_status": log_status, "run_id": run_id}


def write_readout(path: Path, evidence_id: str, reviewed_at: str, selection: dict[str, Any]) -> None:
    text = f"""# R5 Bundle 5.3 — Market and Peer Input Readout

status: accepted_low_confidence_peer_set

## result

- workflow_id: `{WORKFLOW_ID}`
- stock_code: `{STOCK_CODE}`
- market_date: `2026-07-10`
- reviewer: `codex`
- reviewed_at: `{reviewed_at}`
- source_evidence_id: `{evidence_id}`
- market_snapshot_records: `1`
- peer_snapshot_records: `6`
- peer_set_quality: `{selection['peer_set_quality']}`
- canonical_registry_changed: `false`
- sample_quality_report_allowed: `false`
- p2_allowed: `false`

## normalization

- Close is stored as CNY/share.
- Tushare `total_share`, `float_share` and `free_share` are multiplied by 10,000 to produce shares.
- Tushare `total_mv` and `circ_mv` are multiplied by 10,000 to produce CNY.
- PE, PE TTM, PB, PS and PS TTM remain multiples.
- Market capitalization uses source-reported `total_mv * 10,000`; it is not silently recomputed from rounded close and shares.

## peer_selection

- Included: `301018 申菱环境` (product exposure score 4), `300499 高澜股份` (product exposure score 3).
- Excluded: `300731 科创新源`, `300602 飞荣达` because the current local universe records lower-scored technology-level exposure.
- Selection was completed from the exposure universe before inspecting valuation multiples.
- Two peers are insufficient for a high-confidence relative-valuation set; downstream use must retain the low-confidence label.

## boundaries

The snapshot is a dated market context, not a live/current quote beyond 2026-07-10. Trailing multiples are not forward estimates. No registry promotion or transaction instruction was produced.
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_outputs(
    repo_root: Path,
    *,
    rows: list[dict[str, Any]],
    reviewed_at: str,
    retrieved_at: str,
) -> dict[str, Any]:
    datetime.fromisoformat(reviewed_at.replace("Z", "+00:00"))
    payload = raw_payload(rows)
    raw_bytes = _canonical_json_bytes(payload)
    file_hash = hashlib.sha256(raw_bytes).hexdigest()
    short_hash = file_hash[:8]
    evidence_id = f"ev_structured_market_data_002837_20260710_{file_hash[:6]}"
    raw_rel = f"data/raw/market_data/tushare_daily_basic_peer_set_2026-07-10_{short_hash}.json"
    normalized_rel = f"data/processed/normalized/market_peer_002837_2026-07-10_{short_hash}.csv"
    raw_status = _write_immutable(repo_root / raw_rel, raw_bytes)
    normalized = normalize_rows(rows, evidence_id)
    processed_status = _write_immutable(repo_root / normalized_rel, _csv_bytes(normalized))
    params_payload = {
        "api_name": "daily_basic",
        "trade_date": TRADE_DATE,
        "ts_codes": list(TS_CODES),
        "fields": DAILY_BASIC_FIELDS,
    }
    params_hash = hashlib.sha256(_canonical_json_bytes(params_payload)).hexdigest()
    registration = register_evidence(
        repo_root,
        evidence_id=evidence_id,
        raw_rel=raw_rel,
        processed_rel=normalized_rel,
        file_hash=file_hash,
        params_hash=params_hash,
        retrieved_at=retrieved_at,
    )
    selection = peer_selection_review(repo_root)
    by_code = {str(row["stock_code"]): row for row in normalized}
    market_record = build_market_record(by_code[STOCK_CODE], evidence_id, raw_rel, reviewed_at)
    peer_records = build_peer_records(normalized, evidence_id, raw_rel, reviewed_at, selection)
    dropzone = repo_root / "data/reviewed_inputs" / WORKFLOW_ID
    _write_yaml(dropzone / "market_snapshot/market_002837_20260710.yaml", {"records": [market_record]})
    _write_yaml(dropzone / "peer_snapshot/peer_set_20260710.yaml", {"records": peer_records})
    run_dir = repo_root / "reports/workflow_runs" / WORKFLOW_ID
    _write_yaml(run_dir / "R5_bundle5_peer_set_review.yaml", selection)
    acquisition = {
        "artifact_type": "R5_bundle5_market_peer_acquisition_log",
        "evidence_id": evidence_id,
        "retrieved_at": retrieved_at,
        "reviewed_at": reviewed_at,
        "raw_path": raw_rel,
        "normalized_path": normalized_rel,
        "raw_status": raw_status,
        "processed_status": processed_status,
        "registration": registration,
        "token_persisted": False,
        "sample_quality_report_allowed": False,
        "p2_allowed": False,
    }
    _write_yaml(run_dir / "R5_bundle5_market_peer_acquisition_log.yaml", acquisition)
    write_readout(repo_root / "reports/p1_6/R5_BUNDLE_5_3_MARKET_PEER_INPUT_READOUT.md", evidence_id, reviewed_at, selection)
    return {
        "evidence_id": evidence_id,
        "raw_path": raw_rel,
        "normalized_path": normalized_rel,
        "market_records": 1,
        "peer_records": len(peer_records),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build R5 Bundle 5.3 market and peer onboarding outputs.")
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--env-file", type=Path, default=Path(".env.local"))
    parser.add_argument("--fixture-json", type=Path)
    parser.add_argument("--allow-network", action="store_true")
    parser.add_argument("--reviewed-at", required=True)
    args = parser.parse_args(argv)
    repo_root = args.repo_root.resolve()
    if args.fixture_json:
        rows = load_fixture_rows(args.fixture_json)
    elif args.allow_network:
        env_file = args.env_file if args.env_file.is_absolute() else repo_root / args.env_file
        rows = fetch_live_rows(env_file)
    else:
        raise SystemExit("provide --fixture-json or explicit --allow-network")
    retrieved_at = utc_now_iso()
    result = build_outputs(repo_root, rows=rows, reviewed_at=args.reviewed_at, retrieved_at=retrieved_at)
    print(
        "r5_bundle5_card_5_3 status=accepted "
        f"evidence_id={result['evidence_id']} market={result['market_records']} peers={result['peer_records']} "
        "promotion_allowed=false sample_quality=false p2=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
