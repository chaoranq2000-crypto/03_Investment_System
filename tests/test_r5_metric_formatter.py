from src.report.r5_metric_formatter import cny, eps, iso_date, multiple, pct


def test_reader_metric_formatting_is_bounded():
    assert cny(1_234_567_890) == "12.35"
    assert pct(12.345) == "12.3%"
    assert pct(-1.235, 2) == "-1.24%"
    assert multiple(194.2045) == "194.2x"
    assert eps(0.073854, 3) == "0.074"
    assert iso_date("2026-07-10") == "2026-07-10"
