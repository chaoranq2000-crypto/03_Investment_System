from __future__ import annotations

from io import StringIO
from typing import Any, Sequence

import pandas as pd

from src.ingest.adapters.adapter_runtime import AdapterSpec, EndpointContract, FetchResult, adapter_main
from src.ingest.adapters.public_http import request_public


SPEC = AdapterSpec(
    adapter_id="ths_consensus_adapter",
    source_name="ths",
    source_group="third_party_analysis",
    source_type="third_party_research",
    publisher="Tonghuashun",
    reliability_rank="C",
    material_claim_allowed="false",
    allowed_claim_types="estimate",
    default_endpoint_hint="consensus_eps",
    endpoints={
        "consensus_eps": EndpointContract(
            expected_fields=("annual_period", "institution_count", "eps_mean"),
            metric_fields={
                "institution_count": "count",
                "eps_min": "CNY_per_share",
                "eps_mean": "CNY_per_share",
                "eps_max": "CNY_per_share",
                "industry_average": "CNY_per_share",
            },
            claim_boundary="estimate_only",
            empty_result_allowed=True,
        )
    },
    stale_after="30d",
)


def _normalize_table(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = ["_".join(str(item) for item in col if str(item) != "nan") for col in frame.columns]
    rows: list[dict[str, Any]] = []
    for values in frame.itertuples(index=False, name=None):
        if len(values) < 5:
            continue
        rows.append(
            {
                "annual_period": values[0],
                "institution_count": values[1],
                "eps_min": values[2],
                "eps_mean": values[3],
                "eps_max": values[4],
                "industry_average": values[5] if len(values) > 5 else None,
            }
        )
    return rows


def fetch_live(args: Any) -> FetchResult:
    url = f"https://basic.10jqka.com.cn/new/{args.stock_code}/worth.html"
    response = request_public(
        url=url,
        source_name="ths",
        capability="consensus_eps",
        headers={"Accept": "text/html,application/xhtml+xml"},
        referer="https://basic.10jqka.com.cn/",
        min_interval_seconds=0.8,
    )
    text = response.body.decode("gbk", errors="replace")
    tables = pd.read_html(StringIO(text))
    selected = next((table for table in tables if table.shape[1] >= 5 and table.shape[0] > 0), None)
    rows = _normalize_table(selected) if selected is not None else []
    raw_payload = {"rows": rows, "table_count": len(tables), "html_sha_basis": text[:2000]}
    return FetchResult(
        raw_payload=raw_payload,
        rows=rows,
        source_url=response.url,
        http_status=response.status,
        attempts=response.attempts,
        transport=response.transport,
        notes="Consensus estimate only; contributor count is retained and single-broker values are excluded.",
    )


def main(argv: Sequence[str] | None = None) -> int:
    return adapter_main(argv, spec=SPEC, live_fetcher=fetch_live, description="Archive THS consensus EPS estimates.")


if __name__ == "__main__":
    raise SystemExit(main())
