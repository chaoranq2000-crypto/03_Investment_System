from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from .models import IndustryClassification, Instrument


class IndustryFetchError(RuntimeError):
    """行业分类接口不可用或返回格式异常。"""


UNCLASSIFIED_ETF = "未分类（ETF需复核映射）"
TAXONOMY_PATH = Path(__file__).resolve().parents[2] / "config" / "portfolio_industry_taxonomy.json"


@dataclass(frozen=True)
class EtfIndustryOverride:
    industry_name: str
    index_code: str
    index_name: str
    reviewed_at: str
    evidence_source: str


@dataclass(frozen=True)
class IndustryTaxonomy:
    taxonomy_id: str
    aliases: dict[str, str]
    etf_overrides: dict[str, EtfIndustryOverride]


def _records(frame: Any) -> list[dict[str, Any]]:
    if frame is None:
        return []
    if isinstance(frame, list):
        return [dict(item) for item in frame]
    if hasattr(frame, "to_dict"):
        return list(frame.to_dict(orient="records"))
    raise IndustryFetchError(f"无法识别 Tushare 返回类型: {type(frame).__name__}")


def _clean_text(value: Any) -> str:
    text = str(value or "").strip()
    return "" if text.lower() in {"nan", "none"} else text


@lru_cache(maxsize=1)
def load_industry_taxonomy(path: str | Path = TAXONOMY_PATH) -> IndustryTaxonomy:
    config_path = Path(path)
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
        overrides = {
            str(code): EtfIndustryOverride(
                industry_name=str(item["industry_name"]),
                index_code=str(item["index_code"]),
                index_name=str(item["index_name"]),
                reviewed_at=str(item["reviewed_at"]),
                evidence_source=str(item["evidence_source"]),
            )
            for code, item in payload.get("etf_overrides", {}).items()
        }
        return IndustryTaxonomy(
            taxonomy_id=str(payload["taxonomy_id"]),
            aliases={str(key): str(value) for key, value in payload["aliases"].items()},
            etf_overrides=overrides,
        )
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise IndustryFetchError(f"行业归一化配置无效: {config_path}: {exc}") from exc


def normalize_industry(raw_industry: str, taxonomy: IndustryTaxonomy | None = None) -> str:
    raw = _clean_text(raw_industry)
    if not raw:
        return ""
    rules = taxonomy or load_industry_taxonomy()
    return rules.aliases.get(raw, raw)


class TushareIndustryProvider:
    """股票用标准行业；ETF 只使用经复核的代码映射。"""

    def __init__(self, pro: Any, *, taxonomy: IndustryTaxonomy | None = None) -> None:
        self.pro = pro
        self.taxonomy = taxonomy or load_industry_taxonomy()

    def _stock_industries(self) -> tuple[dict[str, str], dict[str, str]]:
        try:
            frame = self.pro.stock_basic(
                exchange="",
                list_status="L",
                fields="ts_code,name,industry",
            )
        except Exception as exc:
            raise IndustryFetchError(
                f"stock_basic 行业分类抓取失败: {type(exc).__name__}: {exc}"
            ) from exc
        raw_by_code: dict[str, str] = {}
        normalized_by_code: dict[str, str] = {}
        for row in _records(frame):
            ts_code = _clean_text(row.get("ts_code"))
            raw = _clean_text(row.get("industry"))
            if not ts_code or not raw:
                continue
            normalized = normalize_industry(raw, self.taxonomy)
            raw_by_code[ts_code] = raw
            normalized_by_code[ts_code] = normalized
        return raw_by_code, normalized_by_code

    def _index_identity(self, instrument: Instrument) -> tuple[str, str]:
        endpoint = getattr(self.pro, "etf_basic", None)
        if endpoint is None:
            return "", ""
        try:
            rows = _records(
                endpoint(ts_code=instrument.ts_code, fields="ts_code,index_code,index_name")
            )
        except Exception:
            return "", ""
        if not rows:
            return "", ""
        return _clean_text(rows[0].get("index_code")), _clean_text(rows[0].get("index_name"))

    def _classify_etf(
        self, instrument: Instrument, now: str
    ) -> tuple[IndustryClassification, bool]:
        override = self.taxonomy.etf_overrides.get(instrument.ts_code)
        if override is None:
            return (
                IndustryClassification(
                    instrument.ts_code,
                    UNCLASSIFIED_ETF,
                    f"reviewed_override_missing|taxonomy={self.taxonomy.taxonomy_id}",
                    now,
                    method="reviewed_etf_override",
                    confidence="unverified",
                ),
                False,
            )

        actual_code, actual_name = self._index_identity(instrument)
        mismatch = (actual_code and actual_code != override.index_code) or (
            actual_name and actual_name != override.index_name
        )
        if mismatch:
            source = (
                f"reviewed_override_mismatch|expected_index_code={override.index_code}"
                f"|expected_index={override.index_name}|actual_index_code={actual_code or 'MISSING'}"
                f"|actual_index={actual_name or 'MISSING'}|taxonomy={self.taxonomy.taxonomy_id}"
            )
            return (
                IndustryClassification(
                    instrument.ts_code,
                    UNCLASSIFIED_ETF,
                    source,
                    now,
                    method="reviewed_etf_override",
                    source_date=override.reviewed_at,
                    confidence="unverified",
                ),
                False,
            )

        verification = "live_index_match" if actual_code or actual_name else "reviewed_config"
        source = (
            f"{override.evidence_source}|index_code={override.index_code}"
            f"|index={override.index_name}|reviewed_at={override.reviewed_at}"
            f"|verification={verification}|confidence=high"
            f"|taxonomy={self.taxonomy.taxonomy_id}"
        )
        return (
            IndustryClassification(
                ts_code=instrument.ts_code,
                industry_name=override.industry_name,
                source=source,
                classified_at=now,
                method="reviewed_etf_override",
                source_date=override.reviewed_at,
                confidence="high",
            ),
            True,
        )

    def fetch_many(
        self, instruments: list[Instrument]
    ) -> tuple[list[IndustryClassification], list[str]]:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        classifications: list[IndustryClassification] = []
        missing: list[str] = []
        raw_by_code, normalized_by_code = self._stock_industries()

        for instrument in instruments:
            if instrument.asset_type == "equity":
                raw = raw_by_code.get(instrument.ts_code, "")
                industry_name = normalized_by_code.get(instrument.ts_code, "")
                if not industry_name:
                    missing.append(instrument.ts_code)
                    continue
                source = "tushare.stock_basic.industry"
                if industry_name != raw:
                    source += (
                        f"|raw={raw}|normalized={industry_name}"
                        f"|taxonomy={self.taxonomy.taxonomy_id}"
                    )
                classifications.append(
                    IndustryClassification(
                        ts_code=instrument.ts_code,
                        industry_name=industry_name,
                        source=source,
                        classified_at=now,
                        method="stock_basic_normalized",
                        confidence="high",
                    )
                )
            elif instrument.asset_type == "etf":
                classification, sufficient = self._classify_etf(instrument, now)
                classifications.append(classification)
                if not sufficient:
                    missing.append(instrument.ts_code)
            else:
                missing.append(instrument.ts_code)
        return classifications, missing
