from __future__ import annotations

import json

from src.portfolio.cli import main
from src.portfolio.store import PortfolioStore


def test_snapshot_cli_creates_lists_and_reads_revision(tmp_path, capsys):
    database = tmp_path / "portfolio.sqlite3"
    PortfolioStore(database).initialize()

    assert (
        main(
            [
                "--db",
                str(database),
                "snapshot",
                "--as-of",
                "2026-07-12",
                "--format",
                "json",
            ]
        )
        == 0
    )
    created = json.loads(capsys.readouterr().out)
    assert created["revision"] == 1
    assert created["valuation_complete"] is True

    assert (
        main(
            [
                "--db",
                str(database),
                "snapshot-list",
                "--from",
                "2026-07-01",
                "--to",
                "2026-07-31",
                "--format",
                "json",
            ]
        )
        == 0
    )
    listed = json.loads(capsys.readouterr().out)
    assert listed[0]["snapshot_id"] == created["snapshot_id"]

    assert (
        main(
            [
                "--db",
                str(database),
                "snapshot-show",
                "--as-of",
                "2026-07-12",
                "--revision",
                "1",
                "--format",
                "json",
            ]
        )
        == 0
    )
    shown = json.loads(capsys.readouterr().out)
    assert shown["snapshot_id"] == created["snapshot_id"]


def test_snapshot_cli_rejects_invalid_date_and_naive_cutoff(tmp_path, capsys):
    database = tmp_path / "portfolio.sqlite3"
    assert (
        main(
            [
                "--db",
                str(database),
                "snapshot",
                "--as-of",
                "not-a-date",
            ]
        )
        == 2
    )
    assert "错误:" in capsys.readouterr().err

    assert (
        main(
            [
                "--db",
                str(database),
                "snapshot",
                "--as-of",
                "2026-07-12",
                "--knowledge-cutoff",
                "2026-07-12T12:00:00",
            ]
        )
        == 2
    )
    assert "必须包含时区" in capsys.readouterr().err


def test_snapshot_cli_unknown_account_is_nonzero_and_not_created(tmp_path, capsys):
    database = tmp_path / "portfolio.sqlite3"
    PortfolioStore(database).initialize()

    assert (
        main(
            [
                "--db",
                str(database),
                "--account",
                "missing",
                "snapshot",
                "--as-of",
                "2026-07-12",
            ]
        )
        == 2
    )
    assert "账户不存在: missing" in capsys.readouterr().err
    with PortfolioStore(database).connect() as connection:
        assert (
            connection.execute("SELECT 1 FROM accounts WHERE account_id = 'missing'").fetchone()
            is None
        )


def test_snapshot_show_missing_revision_is_nonzero(tmp_path, capsys):
    database = tmp_path / "portfolio.sqlite3"
    PortfolioStore(database).initialize()

    assert (
        main(
            [
                "--db",
                str(database),
                "snapshot-show",
                "--as-of",
                "2026-07-12",
                "--revision",
                "99",
            ]
        )
        == 2
    )
    assert "未找到快照" in capsys.readouterr().err
