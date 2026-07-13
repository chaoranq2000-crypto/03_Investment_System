import pytest

from src.report.r5_reader_writer_v4 import render_reader_report
from src.report.r5_traceability_v4 import build_traceability_appendix
from tests.r5_bundle10r_test_fixtures import payload


def test_traceability_resolves_every_display_reference():
    p = payload()
    appendix = build_traceability_appendix(p, render_reader_report(p))
    assert appendix["unresolved_references"] == []
    assert appendix["duplicate_references"] == []


def test_duplicate_reference_fails():
    p = payload()
    p["reference_catalog"].append(dict(p["reference_catalog"][0]))
    with pytest.raises(ValueError):
        build_traceability_appendix(p, render_reader_report(p))
