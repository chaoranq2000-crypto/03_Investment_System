from pathlib import Path

from src.report.r5_reader_payload_v4 import normalize_reader_payload
from src.report.r5_reader_writer_v4 import render_reader_report
from tests.r5_bundle10r_test_fixtures import MODEL_ID, MODEL_SHA, payload, reader_contract


def test_payload_and_generic_writer_render_cross_company():
    normalized = normalize_reader_payload(payload(), model_generation_id=MODEL_ID, model_aggregate_sha256=MODEL_SHA, reader_contract=reader_contract())
    report = render_reader_report(normalized)
    assert "示例制造公司（000001.SZ）" in report
    assert "因果机制" in report
    assert "反向证据" in report
    assert "后续验证与触发条件" in report
    assert "未来事件验证链" in report
    assert "2026-08-20" in report
    assert "人工复核：待进行" in report


def test_writer_source_has_no_pilot_literals():
    source = Path("src/report/r5_reader_writer_v4.py").read_text(encoding="utf-8")
    for forbidden in ("英维克", "002837", "机房温控", "机柜温控", "2026-07-10"):
        assert forbidden not in source
