from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Mapping, Sequence

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from evidence_io import read_csv_dicts, repo_rel, write_json  # noqa: E402
from pdf_candidate_extractor import extract_candidates_from_page_map  # noqa: E402
from table_inventory_builder import build_table_inventory, write_table_inventory  # noqa: E402


def _expand_env_default(value: str) -> str:
    if value.startswith("${") and value.endswith("}") and ":-" in value:
        body = value[2:-1]
        env_name, default = body.split(":-", 1)
        return os.environ.get(env_name, default)
    return os.path.expandvars(value)


def load_job(path: Path) -> dict[str, object]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"job yaml must be a mapping: {path}")
    return payload


def _resolve_repo_path(repo_root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else repo_root / path


def _manifest_row_for_evidence(repo_root: Path, evidence_id: str) -> dict[str, str]:
    candidates = [
        repo_root / "data" / "manifests" / "evidence_manifest.csv",
        repo_root / "evidence_manifest_delta.csv",
        repo_root / "data" / "manifests" / "evidence_manifest.csv",
    ]
    for manifest in candidates:
        for row in read_csv_dicts(manifest):
            if row.get("evidence_id") == evidence_id:
                return row
    return {"evidence_id": evidence_id}


def _extract_pages_with_pypdf(pdf_path: Path) -> tuple[list[dict[str, object]], str, str]:
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(pdf_path))
        pages = []
        for index, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            pages.append({"page_no": index, "text": text, "char_count": len(text)})
        return pages, "pypdf_text_extraction", "SUCCESS"
    except Exception as exc:  # pragma: no cover - exercised by invalid-pdf tests
        raw_text = pdf_path.read_bytes().decode("utf-8", errors="replace")
        return [{"page_no": 1, "text": raw_text, "char_count": len(raw_text)}], f"bytes_fallback:{exc}", "PARTIAL_SUCCESS"


def _run_mineru_if_requested(job: Mapping[str, object], repo_root: Path, pdf_path: Path) -> dict[str, object]:
    mineru_cfg = job.get("mineru") if isinstance(job.get("mineru"), dict) else {}
    command = _expand_env_default(str(mineru_cfg.get("bin", "mineru")))
    should_call = str(os.environ.get("STOCK_REPORT_USE_MINERU", "")).lower() in {"1", "true", "yes"}
    should_call = should_call or bool(mineru_cfg.get("call_mineru"))
    if not should_call:
        return {"attempted": False, "reason": "external mineru call not requested"}
    resolved = shutil.which(command) or command
    output_dir = repo_root / ".tmp_mineru_output" / str(job.get("job_id") or job.get("evidence_id"))
    output_dir.mkdir(parents=True, exist_ok=True)
    args = [resolved, "--path", str(pdf_path), "--output", str(output_dir)]
    for extra in mineru_cfg.get("extra_args", []) or []:
        args.append(str(extra))
    result = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=900)
    return {
        "attempted": True,
        "command": args,
        "returncode": result.returncode,
        "stdout": result.stdout[-4000:],
        "output_dir": str(output_dir),
    }


def run_parse_job(job_path: Path, repo_root: Path | None = None) -> dict[str, object]:
    job = load_job(job_path)
    repo_root = (repo_root or Path(".")).resolve()
    evidence_id = str(job["evidence_id"])
    raw_pdf_path = _resolve_repo_path(repo_root, str(job["raw_pdf_path"]))
    if not raw_pdf_path.exists():
        raise FileNotFoundError(f"raw_pdf_path does not exist: {raw_pdf_path}")

    normalization = job.get("normalization") if isinstance(job.get("normalization"), dict) else {}
    text_path = _resolve_repo_path(
        repo_root,
        str(normalization.get("processed_text_path", f"data/processed/text/{evidence_id}.md")).format(
            evidence_id=evidence_id
        ),
    )
    content_json_path = _resolve_repo_path(
        repo_root,
        str(normalization.get("content_json_path", f"data/processed/layout/{evidence_id}_content.json")).format(
            evidence_id=evidence_id
        ),
    )
    middle_json_path = _resolve_repo_path(
        repo_root,
        str(normalization.get("middle_json_path", f"data/processed/layout/{evidence_id}_middle.json")).format(
            evidence_id=evidence_id
        ),
    )
    tables_path = _resolve_repo_path(
        repo_root,
        str(normalization.get("tables_path", f"data/processed/tables/{evidence_id}_tables.json")).format(
            evidence_id=evidence_id
        ),
    )
    page_map_path = _resolve_repo_path(
        repo_root,
        str(normalization.get("page_map_path", f"data/processed/page_maps/{evidence_id}_page_map.yaml")).format(
            evidence_id=evidence_id
        ),
    )
    parse_log_path = _resolve_repo_path(
        repo_root,
        str(normalization.get("parse_log_path", f"data/processed/logs/{evidence_id}_parse_log.json")).format(
            evidence_id=evidence_id
        ),
    )

    mineru_result = _run_mineru_if_requested(job, repo_root, raw_pdf_path)
    pages, parser_name, result_status = _extract_pages_with_pypdf(raw_pdf_path)
    table_inventory = build_table_inventory(evidence_id=evidence_id, pages=pages)

    text_path.parent.mkdir(parents=True, exist_ok=True)
    text_payload = [f"# Parsed PDF Text: {evidence_id}", ""]
    for page in pages:
        text_payload.extend([f"## Page {page['page_no']}", str(page.get("text", "")).strip(), ""])
    text_path.write_text("\n".join(text_payload), encoding="utf-8")

    content_json_path.parent.mkdir(parents=True, exist_ok=True)
    content_json_path.write_text(json.dumps({"evidence_id": evidence_id, "pages": pages}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    middle_json_path.parent.mkdir(parents=True, exist_ok=True)
    middle_json_path.write_text(
        json.dumps(
            {"evidence_id": evidence_id, "parser": parser_name, "mineru": mineru_result},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    write_table_inventory(tables_path, table_inventory)
    page_map_path.parent.mkdir(parents=True, exist_ok=True)
    page_map_path.write_text(yaml.safe_dump(pages, allow_unicode=True, sort_keys=False), encoding="utf-8")

    manifest_row = _manifest_row_for_evidence(repo_root, evidence_id)
    manifest_row.update(
        {
            "evidence_id": evidence_id,
            "processed_text_path": repo_rel(text_path, repo_root),
            "processed_table_path": repo_rel(tables_path, repo_root),
            "page_map_path": repo_rel(page_map_path, repo_root),
            "page_count": str(len(pages)),
            "parse_status": "parsed" if result_status == "SUCCESS" else "partial",
        }
    )
    candidate_info: dict[str, object] = {}
    candidate_cfg = job.get("candidate_generation") if isinstance(job.get("candidate_generation"), dict) else {}
    if candidate_cfg.get("generate_claim_candidates", True) or candidate_cfg.get("generate_metric_candidates", True):
        candidate_info = extract_candidates_from_page_map(
            page_map_path=page_map_path,
            manifest_row=manifest_row,
            output_dir=repo_root / "data" / "processed" / "candidates",
        )

    mineru_returncode = mineru_result.get("returncode") if mineru_result.get("attempted") else None
    mineru_status = "not_attempted"
    if mineru_result.get("attempted"):
        mineru_status = "success" if mineru_returncode == 0 else "failed_fallback_used"
    issues = [] if pages else [{"severity": "high", "issue": "PDF produced no pages"}]
    if mineru_status == "failed_fallback_used":
        issues.append(
            {
                "severity": "medium",
                "issue": "External MinerU CLI returned non-zero; pypdf fallback produced normalized locator outputs.",
            }
        )
    parse_log = {
        "job_id": job.get("job_id", ""),
        "run_id": job.get("run_id", ""),
        "evidence_id": evidence_id,
        "status": result_status,
        "normalization_status": result_status,
        "parser": parser_name,
        "mineru_status": mineru_status,
        "mineru": mineru_result,
        "raw_pdf_path": repo_rel(raw_pdf_path, repo_root),
        "processed_text_path": repo_rel(text_path, repo_root),
        "tables_path": repo_rel(tables_path, repo_root),
        "page_map_path": repo_rel(page_map_path, repo_root),
        "page_count": len(pages),
        "table_inventory_count": len(table_inventory),
        "candidate_info": candidate_info,
        "issues": issues,
    }
    write_json(parse_log_path, parse_log)
    return parse_log


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize a MinerU/PDF parse job into evidence outputs.")
    parser.add_argument("--job", required=True)
    parser.add_argument("--repo-root", default=".")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    result = run_parse_job(Path(args.job), Path(args.repo_root))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
