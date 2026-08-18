from __future__ import annotations

import importlib
import os
from types import SimpleNamespace

import pytest

from src.utils import tushare_client


def test_config_summary_does_not_require_optional_tushare_sdk(tmp_path, monkeypatch):
    env_file = tmp_path / ".env.local"
    env_file.write_text("TUSHARE_HTTP_URL=https://current.example.test\n", encoding="utf-8")

    def fail_import(name: str):
        if name == "tushare":
            raise AssertionError("config summary must not import the optional SDK")
        return importlib.import_module(name)

    monkeypatch.setattr(tushare_client.importlib, "import_module", fail_import)
    summary = tushare_client.tushare_config_summary(env_file)

    assert summary["token_present"] is False
    assert summary["endpoint"] == "https://current.example.test"
    assert summary["endpoint_status"] == "valid"
    assert summary["proxy_mode"] == "environment"


def test_config_summary_does_not_use_legacy_endpoint_alias(tmp_path):
    env_file = tmp_path / ".env.local"
    env_file.write_text(
        "TUSHARE_TOKEN=fake-token\n"
        "TUSHARE_API_URL=https://legacy.example.test\n",
        encoding="utf-8",
    )

    summary = tushare_client.tushare_config_summary(env_file)

    assert summary["endpoint"] is None
    assert summary["endpoint_status"] == "missing"


def test_live_client_reports_missing_optional_tushare_sdk(tmp_path, monkeypatch):
    env_file = tmp_path / ".env.local"
    env_file.write_text(
        "TUSHARE_TOKEN=fake-token\n"
        "TUSHARE_HTTP_URL=https://current.example.test\n",
        encoding="utf-8",
    )

    def missing_tushare(name: str):
        if name == "tushare":
            raise ModuleNotFoundError("No module named 'tushare'")
        return importlib.import_module(name)

    monkeypatch.setattr(tushare_client.importlib, "import_module", missing_tushare)

    with pytest.raises(RuntimeError, match="optional 'tushare' package"):
        tushare_client.get_tushare_pro(env_file)


def test_live_client_passes_variable_length_token_without_persisting_it(
    tmp_path, monkeypatch
):
    token = "variable-format-token"
    endpoint = "https://compatible.example.test/gateway"
    env_file = tmp_path / ".env.local"
    env_file.write_text(
        f"TUSHARE_TOKEN={token}\nTUSHARE_HTTP_URL={endpoint}/\n",
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    class FakePro:
        pass

    def pro_api(value: str, *, timeout: int):
        captured.update(token=value, timeout=timeout)
        return FakePro()

    fake_tushare = SimpleNamespace(
        pro_api=pro_api,
        set_token=lambda _value: pytest.fail("set_token must never persist the token"),
    )
    monkeypatch.setattr(tushare_client, "_load_tushare", lambda: fake_tushare)

    pro = tushare_client.get_tushare_pro(env_file)

    assert captured == {
        "token": token,
        "timeout": tushare_client.DEFAULT_TUSHARE_TIMEOUT_SECONDS,
    }
    assert pro._DataApi__http_url == endpoint
    config = tushare_client.load_tushare_config(env_file)
    assert token not in repr(config)


@pytest.mark.parametrize(
    "token",
    ["token with space", "token\twith-control"],
)
def test_live_client_rejects_unsafe_token_characters(tmp_path, token):
    env_file = tmp_path / ".env.local"
    env_file.write_text(
        f"TUSHARE_TOKEN={token}\nTUSHARE_HTTP_URL=https://current.example.test\n",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="contains unsafe characters"):
        tushare_client.get_tushare_pro(env_file)


def test_live_client_rejects_newline_from_environment(tmp_path, monkeypatch):
    env_file = tmp_path / ".env.local"
    env_file.write_text(
        "TUSHARE_HTTP_URL=https://current.example.test\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("TUSHARE_TOKEN", "token\nwith-newline")

    with pytest.raises(RuntimeError, match="contains unsafe characters"):
        tushare_client.get_tushare_pro(env_file)


def test_live_client_rejects_unbounded_token(tmp_path):
    env_file = tmp_path / ".env.local"
    env_file.write_text(
        f"TUSHARE_TOKEN={'x' * (tushare_client.MAX_TOKEN_LENGTH + 1)}\n"
        "TUSHARE_HTTP_URL=https://current.example.test\n",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="is too long"):
        tushare_client.get_tushare_pro(env_file)


def test_live_client_requires_canonical_endpoint(tmp_path):
    env_file = tmp_path / ".env.local"
    env_file.write_text(
        "TUSHARE_TOKEN=fake-token\n"
        "TUSHARE_API_URL=https://legacy.example.test\n",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="TUSHARE_HTTP_URL is missing"):
        tushare_client.get_tushare_pro(env_file)


@pytest.mark.parametrize(
    ("endpoint", "message"),
    [
        ("http://insecure.example.test", "must use HTTPS"),
        ("https://user:pass@example.test", "must not contain credentials"),
        ("https://example.test/path?token=secret", "must not contain credentials"),
        ("https://example.test/path#fragment", "must not contain credentials"),
        ("https://example.test:invalid", "invalid port"),
    ],
)
def test_live_client_rejects_unsafe_endpoint_before_sdk_import(
    tmp_path, monkeypatch, endpoint, message
):
    env_file = tmp_path / ".env.local"
    env_file.write_text(
        f"TUSHARE_TOKEN=fake-token\nTUSHARE_HTTP_URL={endpoint}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        tushare_client,
        "_load_tushare",
        lambda: pytest.fail("SDK import must not happen for an unsafe endpoint"),
    )

    with pytest.raises(RuntimeError, match=message):
        tushare_client.get_tushare_pro(env_file)


def test_live_client_rejects_invalid_proxy_setting(tmp_path):
    env_file = tmp_path / ".env.local"
    env_file.write_text(
        "TUSHARE_TOKEN=fake-token\n"
        "TUSHARE_HTTP_URL=https://current.example.test\n"
        "TUSHARE_DISABLE_PROXY=sometimes\n",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="must be a boolean"):
        tushare_client.get_tushare_pro(env_file)


@pytest.mark.parametrize("timeout", [0, 121, True])
def test_live_client_rejects_invalid_timeout(tmp_path, timeout):
    env_file = tmp_path / ".env.local"
    env_file.write_text(
        "TUSHARE_TOKEN=fake-token\n"
        "TUSHARE_HTTP_URL=https://current.example.test\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="between 1 and 120"):
        tushare_client.get_tushare_pro(env_file, timeout_seconds=timeout)


def test_environment_values_override_env_file(tmp_path, monkeypatch):
    env_file = tmp_path / ".env.local"
    env_file.write_text(
        "TUSHARE_TOKEN=file-token\n"
        "TUSHARE_HTTP_URL=https://file.example.test\n",
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    class FakePro:
        pass

    def pro_api(token: str, *, timeout: int):
        captured.update(token=token, timeout=timeout)
        return FakePro()

    monkeypatch.setenv("TUSHARE_TOKEN", "environment-token")
    monkeypatch.setenv("TUSHARE_HTTP_URL", "https://environment.example.test")
    monkeypatch.setattr(
        tushare_client,
        "_load_tushare",
        lambda: SimpleNamespace(pro_api=pro_api),
    )

    pro = tushare_client.get_tushare_pro(env_file)

    assert captured["token"] == "environment-token"
    assert pro._DataApi__http_url == "https://environment.example.test"


def test_disable_proxy_adds_only_endpoint_host_for_call_and_restores_env(
    tmp_path, monkeypatch
):
    env_file = tmp_path / ".env.local"
    env_file.write_text(
        "TUSHARE_TOKEN=fake-token\n"
        "TUSHARE_HTTP_URL=https://compatible.example.test\n"
        "TUSHARE_DISABLE_PROXY=true\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("NO_PROXY", "localhost")
    monkeypatch.setenv("no_proxy", "localhost")
    observed: dict[str, str] = {}

    def daily():
        observed["NO_PROXY"] = os.environ.get("NO_PROXY", "")
        observed["no_proxy"] = os.environ.get("no_proxy", "")
        return "ok"

    fake_pro = SimpleNamespace(daily=daily)
    monkeypatch.setattr(
        tushare_client,
        "_load_tushare",
        lambda: SimpleNamespace(pro_api=lambda _token, timeout: fake_pro),
    )

    pro = tushare_client.get_tushare_pro(env_file)

    assert pro.daily() == "ok"
    for key in ("NO_PROXY", "no_proxy"):
        entries = observed[key].split(",")
        assert "compatible.example.test" in entries
        assert "*" not in entries
        assert os.environ[key] == "localhost"


def test_environment_proxy_mode_does_not_mutate_no_proxy(tmp_path, monkeypatch):
    env_file = tmp_path / ".env.local"
    env_file.write_text(
        "TUSHARE_TOKEN=fake-token\n"
        "TUSHARE_HTTP_URL=https://current.example.test\n"
        "TUSHARE_DISABLE_PROXY=false\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("NO_PROXY", "localhost")

    def daily():
        assert os.environ["NO_PROXY"] == "localhost"
        return "ok"

    monkeypatch.setattr(
        tushare_client,
        "_load_tushare",
        lambda: SimpleNamespace(
            pro_api=lambda _token, timeout: SimpleNamespace(daily=daily)
        ),
    )

    assert tushare_client.get_tushare_pro(env_file).daily() == "ok"
    assert os.environ["NO_PROXY"] == "localhost"


def test_client_sanitizes_provider_error_and_suppresses_raw_context(
    tmp_path, monkeypatch
):
    token = "sensitive-test-token"
    env_file = tmp_path / ".env.local"
    env_file.write_text(
        f"TUSHARE_TOKEN={token}\n"
        "TUSHARE_HTTP_URL=https://current.example.test\n",
        encoding="utf-8",
    )

    def daily():
        raise RuntimeError(
            f"token={token} Authorization: Bearer other-secret "
            "https://user:pass@example.test/path?api_key=query-secret"
        )

    monkeypatch.setattr(
        tushare_client,
        "_load_tushare",
        lambda: SimpleNamespace(
            pro_api=lambda _token, timeout: SimpleNamespace(daily=daily)
        ),
    )

    with pytest.raises(tushare_client.TushareProviderError) as failure:
        tushare_client.get_tushare_pro(env_file).daily()

    message = str(failure.value)
    for secret in (token, "other-secret", "user:pass", "query-secret"):
        assert secret not in message
    assert "<REDACTED>" in message
    assert failure.value.__suppress_context__ is True


def test_provider_error_scrubber_handles_dict_and_encoded_secret_forms():
    token = "sensitive token/value"
    message = (
        "{'Authorization': 'Bearer header-secret', "
        "'token': 'json-secret', 'password': 'password-secret'} "
        f"?access_token={quote_plus_for_test(token)}"
    )

    scrubbed = tushare_client.sanitize_provider_error(message, secrets=(token,))

    for secret in (
        "header-secret",
        "json-secret",
        "password-secret",
        quote_plus_for_test(token),
    ):
        assert secret not in scrubbed
    assert "<REDACTED>" in scrubbed


def quote_plus_for_test(value: str) -> str:
    from urllib.parse import quote_plus

    return quote_plus(value)
