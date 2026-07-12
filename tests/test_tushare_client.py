from __future__ import annotations

import importlib

import pytest

from src.utils import tushare_client


def test_config_summary_does_not_require_optional_tushare_sdk(tmp_path, monkeypatch):
    env_file = tmp_path / ".env.local"
    env_file.write_text("TUSHARE_API_URL=https://api.tushare.pro\n", encoding="utf-8")

    def fail_import(name: str):
        if name == "tushare":
            raise AssertionError("config summary must not import the optional SDK")
        return importlib.import_module(name)

    monkeypatch.setattr(tushare_client.importlib, "import_module", fail_import)
    summary = tushare_client.tushare_config_summary(env_file)

    assert summary["token_present"] is False
    assert summary["api_url"] == "https://api.tushare.pro"


def test_live_client_reports_missing_optional_tushare_sdk(tmp_path, monkeypatch):
    env_file = tmp_path / ".env.local"
    env_file.write_text(f"TUSHARE_TOKEN={'A' * 56}\n", encoding="utf-8")

    def missing_tushare(name: str):
        if name == "tushare":
            raise ModuleNotFoundError("No module named 'tushare'")
        return importlib.import_module(name)

    monkeypatch.setattr(tushare_client.importlib, "import_module", missing_tushare)

    with pytest.raises(RuntimeError, match="optional 'tushare' package"):
        tushare_client.get_tushare_pro(env_file)
