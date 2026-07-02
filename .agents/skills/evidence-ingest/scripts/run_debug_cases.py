#!/usr/bin/env python3
"""Run B1 evidence-ingest debug cases in a temporary workspace."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
ASSETS_DIR = SKILL_DIR / "assets" / "debug_cases"
MANIFEST_FIELDS = [
    "evidence_id","source_type","source_name","source_group","title","publisher","publish_date","retrieved_at","ingested_at","as_of_date","entity_type","entity_id","segment_id","company_id","stock_code","source_url","raw_file_path","raw_archive_policy","file_hash","content_hash","api_params_hash","processed_text_path","processed_table_path","page_map_path","page_count","language","file_format","ingest_mode","reliability_rank","material_claim_allowed","allowed_claim_types","license_note","stale_after","status","parse_status","candidate_status","review_status","previous_evidence_id","superseded_by","notes"
]
CLAIM_FIELDS = [
    "claim_candidate_id","evidence_id","source_type","source_name","reliability_rank","entity_type","entity_id","segment_id","company_id","stock_code","claim_text","claim_type","claim_scope","quote_or_excerpt","page_no_or_section","table_id","confidence","materiality","support_level","needs_review_reason","review_status","promote_to_claim_id","created_at","notes"
]
METRIC_FIELDS = [
    "metric_candidate_id","source_evidence_id","source_name","source_type","entity_type","entity_id","segment_id","company_id","stock_code","metric_name","metric_category","period","period_type","value","unit","currency","original_value_text","original_unit_text","table_id","page_no_or_section","calculation_method","is_estimate","is_reported","confidence","review_status","promote_to_metric_id","created_at","notes"
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    proc = subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return proc.returncode, proc.stdout


def base_row(now: str) -> dict[str, str]:
    return {f: "" for f in MANIFEST_FIELDS} | {
        "retrieved_at": now,
        "ingested_at": now,
        "language": "zh-CN",
        "status": "active",
        "parse_status": "parsed",
        "candidate_status": "not_generated",
        "review_status": "draft",
        "license_note": "debug fixture",
        "stale_after": "P1.6 debug only",
    }


def setup_manual_file_success(root: Path, now: str) -> tuple[Path, list[list[str]], bool]:
    case = "manual_file_success"
    src = ASSETS_DIR / case / "input" / "sample_policy.md"
    raw = root / "data/raw/user_uploaded/sample_policy.md"
    processed = root / "data/processed/text/ev_policy_document_policy_20260115_"  # placeholder below
    raw.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, raw)
    h = sha(raw)
    eid = f"ev_policy_document_policy_20260115_{h[:6]}"
    processed = root / f"data/processed/text/{eid}.md"
    processed.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, processed)
    manifest = root / "data/manifests/evidence_manifest.csv"
    row = base_row(now) | {
        "evidence_id": eid,
        "source_type": "policy_document",
        "source_name": "user_uploaded",
        "source_group": "user_uploaded",
        "title": "B1 debug policy fixture",
        "publisher": "debug",
        "publish_date": "2026-01-15",
        "entity_type": "policy",
        "raw_file_path": str(raw.relative_to(root)),
        "raw_archive_policy": "full_file_archived",
        "file_hash": h,
        "content_hash": h,
        "processed_text_path": str(processed.relative_to(root)),
        "file_format": "md",
        "ingest_mode": "manual_file",
        "reliability_rank": "C",
        "material_claim_allowed": "false",
        "allowed_claim_types": "clue;management_comment",
    }
    write_csv(manifest, MANIFEST_FIELDS, [row])
    return manifest, [[sys.executable, str(SCRIPT_DIR / "validate_manifest.py"), str(manifest), "--repo", str(root)]], True


def setup_structured_api_pull(root: Path, now: str) -> tuple[Path, list[list[str]], bool]:
    case = "structured_api_pull_snapshot"
    src = ASSETS_DIR / case / "input" / "tushare_income_fixture.csv"
    raw = root / "data/raw/financial_data/tushare_income_fixture.csv"
    norm = root / "data/processed/normalized/tushare_income_fixture.csv"
    raw.parent.mkdir(parents=True, exist_ok=True)
    norm.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, raw)
    shutil.copy2(src, norm)
    params = (ASSETS_DIR / case / "input" / "api_params.json").read_text(encoding="utf-8")
    phash = hashlib.sha256(params.encode("utf-8")).hexdigest()
    h = sha(raw)
    eid = f"ev_structured_financial_data_tushare_002837_20251231_{h[:6]}"
    manifest = root / "data/manifests/evidence_manifest.csv"
    row = base_row(now) | {
        "evidence_id": eid,
        "source_type": "structured_financial_data",
        "source_name": "tushare",
        "source_group": "structured_database",
        "title": "Tushare income debug snapshot 002837 2025",
        "publisher": "Tushare Pro",
        "as_of_date": "2025-12-31",
        "entity_type": "company",
        "company_id": "company_002837",
        "stock_code": "002837.SZ",
        "raw_file_path": str(raw.relative_to(root)),
        "raw_archive_policy": "snapshot_archived",
        "file_hash": h,
        "content_hash": h,
        "api_params_hash": phash,
        "processed_table_path": str(norm.relative_to(root)),
        "file_format": "csv",
        "ingest_mode": "structured_api_pull",
        "reliability_rank": "B",
        "material_claim_allowed": "metric_only",
        "allowed_claim_types": "metric_statement",
        "candidate_status": "generated",
    }
    write_csv(manifest, MANIFEST_FIELDS, [row])
    metric = root / "data/manifests/metrics_draft.csv"
    write_csv(metric, METRIC_FIELDS, [{
        "metric_candidate_id": "mc_debug_001",
        "source_evidence_id": eid,
        "source_name": "tushare",
        "source_type": "structured_financial_data",
        "entity_type": "company",
        "entity_id": "company_002837",
        "segment_id": "",
        "company_id": "company_002837",
        "stock_code": "002837.SZ",
        "metric_name": "revenue",
        "metric_category": "income_statement",
        "period": "2025FY",
        "period_type": "annual",
        "value": "1000000",
        "unit": "CNY",
        "currency": "CNY",
        "original_value_text": "1000000",
        "original_unit_text": "CNY",
        "table_id": "fixture_income",
        "page_no_or_section": "api_snapshot",
        "calculation_method": "reported_by_source",
        "is_estimate": "false",
        "is_reported": "true",
        "confidence": "medium",
        "review_status": "draft",
        "promote_to_metric_id": "",
        "created_at": now,
        "notes": "debug metric candidate; does not imply segment exposure",
    }])
    return manifest, [
        [sys.executable, str(SCRIPT_DIR / "validate_manifest.py"), str(manifest), "--repo", str(root)],
        [sys.executable, str(SCRIPT_DIR / "validate_candidates.py"), "--manifest", str(manifest), "--metric-candidates", str(metric)],
    ], True


def setup_d_source_clue(root: Path, now: str) -> tuple[Path, list[list[str]], bool]:
    case = "d_source_clue_blocked"
    src = ASSETS_DIR / case / "input" / "news_clue.md"
    raw = root / "data/raw/web_snapshots/news_clue.md"
    raw.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, raw)
    h = sha(raw)
    eid = f"ev_news_social_clue_market_20260201_{h[:6]}"
    manifest = root / "data/manifests/evidence_manifest.csv"
    row = base_row(now) | {
        "evidence_id": eid,
        "source_type": "news_social_clue",
        "source_name": "news",
        "source_group": "clue",
        "title": "D source debug clue",
        "publisher": "debug news",
        "publish_date": "2026-02-01",
        "entity_type": "segment",
        "segment_id": "debug_segment",
        "source_url": "https://example.com/debug-news",
        "raw_file_path": str(raw.relative_to(root)),
        "raw_archive_policy": "snapshot_archived",
        "file_hash": h,
        "content_hash": h,
        "file_format": "md",
        "ingest_mode": "web_page_snapshot",
        "reliability_rank": "D",
        "material_claim_allowed": "false",
        "allowed_claim_types": "clue",
        "candidate_status": "generated",
    }
    write_csv(manifest, MANIFEST_FIELDS, [row])
    claim = root / "data/manifests/claims_draft.csv"
    write_csv(claim, CLAIM_FIELDS, [{
        "claim_candidate_id": "cc_debug_clue_001",
        "evidence_id": eid,
        "source_type": "news_social_clue",
        "source_name": "news",
        "reliability_rank": "D",
        "entity_type": "segment",
        "entity_id": "debug_segment",
        "segment_id": "debug_segment",
        "company_id": "",
        "stock_code": "",
        "claim_text": "Debug clue that requires official verification.",
        "claim_type": "clue",
        "claim_scope": "clue_only",
        "quote_or_excerpt": "Debug clue excerpt.",
        "page_no_or_section": "snapshot",
        "table_id": "",
        "confidence": "low",
        "materiality": "low",
        "support_level": "clue_only",
        "needs_review_reason": "D-level source requires official verification",
        "review_status": "draft",
        "promote_to_claim_id": "",
        "created_at": now,
        "notes": "TODO: verify with official disclosure",
    }])
    return manifest, [
        [sys.executable, str(SCRIPT_DIR / "validate_manifest.py"), str(manifest), "--repo", str(root)],
        [sys.executable, str(SCRIPT_DIR / "validate_candidates.py"), "--manifest", str(manifest), "--claim-candidates", str(claim)],
    ], True


def setup_invalid_manifest(root: Path, now: str) -> tuple[Path, list[list[str]], bool]:
    manifest = root / "data/manifests/evidence_manifest.csv"
    row = base_row(now) | {
        "evidence_id": "ev_bad_debug_20260201_deadbe",
        "source_type": "news_social_clue",
        "source_name": "news",
        "source_group": "clue",
        "title": "Invalid debug row",
        "publisher": "debug",
        "publish_date": "2099-01-01",
        "raw_file_path": "https://example.com/not-a-local-path.pdf",
        "raw_archive_policy": "full_file_archived",
        "file_hash": "deadbeef",
        "file_format": "pdf",
        "ingest_mode": "manual_file",
        "reliability_rank": "D",
        "material_claim_allowed": "true",
        "allowed_claim_types": "fact",
        "status": "bad_status",
    }
    write_csv(manifest, MANIFEST_FIELDS, [row])
    return manifest, [[sys.executable, str(SCRIPT_DIR / "validate_manifest.py"), str(manifest), "--repo", str(root)]], False


def run_case(name: str, setup_func, now: str) -> dict[str, str]:
    with tempfile.TemporaryDirectory(prefix=f"b1_{name}_") as tmp:
        root = Path(tmp)
        manifest, commands, expect_success = setup_func(root, now)
        outputs: list[str] = []
        ok = True
        for cmd in commands:
            code, out = run(cmd, cwd=root)
            outputs.append(out.strip())
            if expect_success and code != 0:
                ok = False
            if not expect_success and code == 0:
                ok = False
        return {
            "case": name,
            "result": "PASS" if ok else "FAIL",
            "expected": "success" if expect_success else "failure",
            "manifest": str(manifest),
            "output": "\n".join(outputs)[:2000],
        }


def local_dir_duplicate() -> dict[str, str]:
    case_dir = ASSETS_DIR / "local_dir_duplicate" / "input"
    a = case_dir / "file_a.md"
    b = case_dir / "file_a_copy.md"
    result = sha(a) == sha(b)
    return {
        "case": "local_dir_duplicate",
        "result": "PASS" if result else "FAIL",
        "expected": "duplicate hashes equal",
        "manifest": "not applicable",
        "output": f"file_a_hash={sha(a)}\nfile_a_copy_hash={sha(b)}",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run B1 evidence-ingest debug cases")
    parser.add_argument("--repo", default=".", help="Repo root, accepted for interface compatibility")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    results = [
        run_case("manual_file_success", setup_manual_file_success, now),
        local_dir_duplicate(),
        run_case("structured_api_pull_snapshot", setup_structured_api_pull, now),
        run_case("d_source_clue_blocked", setup_d_source_clue, now),
        run_case("invalid_manifest_failure", setup_invalid_manifest, now),
    ]
    all_pass = all(r["result"] == "PASS" for r in results)
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for r in results:
            print(f"[{r['result']}] {r['case']} expected={r['expected']}")
            print(r["output"])
            print("---")
        print("B1_DEBUG_READOUT=PASS" if all_pass else "B1_DEBUG_READOUT=FAIL")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
