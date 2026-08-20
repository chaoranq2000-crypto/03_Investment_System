from __future__ import annotations

import json
from datetime import date

from src.utils import tushare_diagnostics


class FakeFrame:
    def __init__(self, columns: tuple[str, ...], rows: int = 1) -> None:
        self.columns = columns
        self._rows = rows

    def __len__(self) -> int:
        return self._rows


def test_probe_profiles_are_bounded_and_separate_product_needs():
    today = date(2026, 8, 19)

    core = tushare_diagnostics.probe_definitions("core", today=today)
    research = tushare_diagnostics.probe_definitions("research", today=today)
    portfolio = tushare_diagnostics.probe_definitions("portfolio", today=today)

    assert [item["api_name"] for item in core] == ["stock_basic", "daily"]
    assert {item["api_name"] for item in research} >= {
        "stock_basic",
        "daily",
        "daily_basic",
        "income",
    }
    assert {item["api_name"] for item in portfolio} >= {
        "adj_factor",
        "fund_daily",
        "fund_adj",
        "stk_mins",
        "etf_mins",
    }
    optional = {item["api_name"] for item in portfolio if not item["required"]}
    assert optional == {"cb_daily", "stk_mins", "etf_mins"}
    by_name = {item["api_name"]: item for item in portfolio}
    assert by_name["cb_daily"]["params"]["trade_date"] == "20260818"
    for api_name in ("stk_mins", "etf_mins"):
        params = by_name[api_name]["params"]
        assert params["start_date"].split(" ", 1)[0] == params["end_date"].split(" ", 1)[0]


def test_core_probe_reports_rows_and_schema(tmp_path, monkeypatch):
    env_file = tmp_path / ".env.local"
    env_file.write_text("TUSHARE_TOKEN=fake-token\n", encoding="utf-8")
    calls: list[str] = []

    class FakePro:
        _DataApi__http_url = "https://current.example.test"

        def stock_basic(self, **params):
            calls.append("stock_basic")
            return FakeFrame(tuple(params["fields"].split(",")))

        def daily(self, **params):
            calls.append("daily")
            return FakeFrame(tuple(params["fields"].split(",")))

    monkeypatch.setattr(tushare_diagnostics, "get_tushare_pro", lambda *_a, **_k: FakePro())

    result = tushare_diagnostics._probe_sdk(env_file, profile="core")

    assert result["status"] == "ok"
    assert calls == ["stock_basic", "daily"]
    assert result["probes"]["daily"]["rows"] == 1
    assert result["probes"]["daily"]["missing_columns"] == []


def test_probe_error_does_not_expose_token(tmp_path, monkeypatch):
    token = "sensitive-variable-token"
    env_file = tmp_path / ".env.local"
    env_file.write_text(f"TUSHARE_TOKEN={token}\n", encoding="utf-8")

    class FakePro:
        _DataApi__http_url = "https://current.example.test"

        def stock_basic(self, **_params):
            raise RuntimeError(f"token={token} Authorization: Bearer other-secret")

        def daily(self, **params):
            return FakeFrame(tuple(params["fields"].split(",")))

    monkeypatch.setattr(tushare_diagnostics, "get_tushare_pro", lambda *_a, **_k: FakePro())

    result = tushare_diagnostics._probe_sdk(env_file, profile="core")

    serialized = json.dumps(result, ensure_ascii=False)
    assert result["status"] == "required_probe_failed"
    assert token not in serialized
    assert "other-secret" not in serialized
    assert "<REDACTED>" in serialized


def test_probe_reports_schema_mismatch_for_missing_requested_fields(tmp_path, monkeypatch):
    env_file = tmp_path / ".env.local"
    env_file.write_text("TUSHARE_TOKEN=fake-token\n", encoding="utf-8")

    class FakePro:
        _DataApi__http_url = "https://current.example.test"

        def stock_basic(self, **_params):
            return FakeFrame(("ts_code",))

        def daily(self, **params):
            return FakeFrame(tuple(params["fields"].split(",")))

    monkeypatch.setattr(tushare_diagnostics, "get_tushare_pro", lambda *_a, **_k: FakePro())

    result = tushare_diagnostics._probe_sdk(env_file, profile="core")

    assert result["status"] == "required_probe_failed"
    assert result["probes"]["stock_basic"]["status"] == "schema_mismatch"
    assert result["probes"]["stock_basic"]["missing_columns"] == [
        "symbol",
        "name",
        "industry",
        "list_date",
    ]


def test_optional_portfolio_failures_do_not_fail_required_profile(tmp_path, monkeypatch):
    env_file = tmp_path / ".env.local"
    env_file.write_text("TUSHARE_TOKEN=fake-token\n", encoding="utf-8")
    optional = {"cb_daily", "stk_mins", "etf_mins"}

    class FakePro:
        _DataApi__http_url = "https://current.example.test"

        def __getattr__(self, name):
            def call(**params):
                if name in optional:
                    raise RuntimeError(f"{name} permission unavailable")
                return FakeFrame(tuple(params["fields"].split(",")))

            return call

    monkeypatch.setattr(tushare_diagnostics, "get_tushare_pro", lambda *_a, **_k: FakePro())

    result = tushare_diagnostics._probe_sdk(env_file, profile="portfolio")

    assert result["status"] == "ok"
    assert set(result["optional_failures"]) == optional
    assert result["minute_capability"] == "unavailable_or_unverified"


def test_config_only_main_never_loads_sdk_or_uses_network(tmp_path, monkeypatch, capsys):
    token = "config-only-fake-token"
    env_file = tmp_path / ".env.local"
    env_file.write_text(
        f"TUSHARE_TOKEN={token}\n"
        "TUSHARE_HTTP_URL=https://current.example.test\n"
        "TUSHARE_DISABLE_PROXY=false\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        tushare_diagnostics,
        "get_tushare_pro",
        lambda *_a, **_k: (_ for _ in ()).throw(
            AssertionError("configuration-only diagnostics must not load the SDK")
        ),
    )

    result = tushare_diagnostics.main(
        ["--env-file", str(env_file), "--profile", "research"]
    )

    output_text = capsys.readouterr().out
    payload = json.loads(output_text)
    assert result == 0
    assert payload["sdk_probe"]["status"] == "skipped_network_not_allowed"
    assert payload["network_policy"]["allow_network"] is False
    assert token not in output_text


def test_main_runs_fake_bounded_probe_only_with_explicit_flag(tmp_path, monkeypatch, capsys):
    token = "bounded-probe-fake-token"
    env_file = tmp_path / ".env.local"
    env_file.write_text(
        f"TUSHARE_TOKEN={token}\n"
        "TUSHARE_HTTP_URL=https://current.example.test\n",
        encoding="utf-8",
    )
    calls: list[str] = []

    def fake_probe(_path, *, profile):
        calls.append(profile)
        return {"status": "ok", "profile": profile, "probes": {}}

    monkeypatch.setattr(tushare_diagnostics, "_probe_sdk", fake_probe)

    result = tushare_diagnostics.main(
        [
            "--env-file",
            str(env_file),
            "--profile",
            "core",
            "--allow-network",
        ]
    )

    output_text = capsys.readouterr().out
    assert result == 0
    assert calls == ["core"]
    assert token not in output_text


def test_main_rejects_legacy_endpoint_alias_without_network(tmp_path, monkeypatch, capsys):
    token = "legacy-diagnostic-token"
    env_file = tmp_path / ".env.local"
    env_file.write_text(
        f"TUSHARE_TOKEN={token}\n"
        "TUSHARE_API_URL=https://legacy.example.test\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("TUSHARE_TOKEN", raising=False)
    monkeypatch.delenv("TUSHARE_HTTP_URL", raising=False)
    monkeypatch.delenv("TUSHARE_API_URL", raising=False)
    monkeypatch.setattr(
        tushare_diagnostics,
        "_probe_sdk",
        lambda *_a, **_k: (_ for _ in ()).throw(
            AssertionError("no probe is allowed in configuration-only mode")
        ),
    )

    result = tushare_diagnostics.main(["--env-file", str(env_file)])

    output_text = capsys.readouterr().out
    payload = json.loads(output_text)
    assert result == 1
    assert payload["configuration"]["endpoint"] is None
    assert payload["configuration"]["endpoint_status"] == "missing"
    assert token not in output_text


def test_proxy_metadata_never_outputs_proxy_values(monkeypatch):
    proxy_secret = "proxy-user:proxy-password"
    monkeypatch.setenv("HTTPS_PROXY", f"http://{proxy_secret}@proxy.example.test:8080")
    monkeypatch.setenv("NO_PROXY", "localhost,current.example.test")

    result = tushare_diagnostics._proxy_meta("https://current.example.test")

    serialized = json.dumps(result)
    assert result == {
        "environment_proxy_present": True,
        "no_proxy_present": True,
        "endpoint_host_in_no_proxy": True,
        "values_redacted": True,
    }
    assert proxy_secret not in serialized


def test_no_proxy_matching_handles_subdomains_ports_and_wildcards():
    host = "api.current.example.test"

    assert tushare_diagnostics._no_proxy_matches(host, ".example.test") is True
    assert tushare_diagnostics._no_proxy_matches(host, "api.current.example.test:443") is True
    assert tushare_diagnostics._no_proxy_matches(host, "*") is True
    assert tushare_diagnostics._no_proxy_matches(host, "unrelated.example.org") is False
