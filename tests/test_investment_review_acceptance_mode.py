from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from src.investment_review.store import (
    ReviewStore,
    ReviewStoreError,
    immutable_review_store_read_context,
)
from src.portfolio import cli as cli_module
from src.portfolio.investment_review_service import InvestmentReviewWebService
from src.portfolio.store import PortfolioStore
from src.portfolio.web import (
    REVIEW_ACCEPTANCE_TASK_ID,
    create_dashboard_server,
)


class _ReadOnlyReviewService:
    read_only_acceptance = True

    def __init__(self) -> None:
        self.mutation_calls = 0

    def get_health(self) -> dict[str, object]:
        return {
            "status": "healthy",
            "data": {
                "status": "healthy",
                "acceptance": {
                    "read_only": True,
                    "human_product_acceptance": "pending",
                },
            },
        }

    def list_reviews(
        self,
        *,
        scope: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> dict[str, object]:
        return {
            "status": "available",
            "data": {
                "items": [],
                "total_count": 0,
                "scope": scope,
                "run_status": status,
                "limit": limit,
            },
        }

    def create_decision(self, _payload: object) -> dict[str, object]:
        self.mutation_calls += 1
        return {"unexpected": True}


def _read_json(
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    body: bytes | None = None,
) -> tuple[int, dict[str, object]]:
    request = Request(
        base_url + path,
        data=body,
        method=method,
        headers={
            "Content-Type": "application/json",
            "Host": base_url.removeprefix("http://"),
            "X-Investment-Review-Action": "decision",
        },
    )
    try:
        with urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def test_acceptance_server_allows_only_review_reads_and_static_assets(
    tmp_path: Path,
) -> None:
    candidate = tmp_path / "candidate.sqlite3"
    candidate.write_bytes(b"acceptance-candidate")
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    expected_sha256 = hashlib.sha256(candidate.read_bytes()).hexdigest()
    service = _ReadOnlyReviewService()
    server = create_dashboard_server(
        PortfolioStore(tmp_path / "formal.sqlite3"),
        host="127.0.0.1",
        port=0,
        investment_review_service=service,  # type: ignore[arg-type]
        investment_review_db=candidate,
        investment_review_artifact_root=artifact_root,
        review_acceptance_read_only=True,
        expected_review_candidate_sha256=expected_sha256,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    base_url = f"http://{host}:{port}"
    try:
        status, health = _read_json(base_url, "/health")
        assert status == 200
        assert health["review_acceptance_read_only"] is True
        assert health["acceptance_task_id"] == REVIEW_ACCEPTANCE_TASK_ID
        assert health["review_candidate_sha256"] == expected_sha256
        assert health["automation_enabled"] is False
        assert health["external_network_allowed"] is False
        assert health["human_product_acceptance"] == "pending"
        assert server.dashboard_app.realtime_provider is None

        status, review_health = _read_json(
            base_url, "/api/investment-review/health"
        )
        assert status == 200
        assert review_health["data"]["acceptance"]["read_only"] is True

        status, blocked_portfolio = _read_json(base_url, "/api/portfolio")
        assert status == 403
        assert blocked_portfolio["code"] == "review_acceptance_read_only"

        status, blocked_live = _read_json(
            base_url,
            "/api/live-intraday",
            method="POST",
            body=b"{}",
        )
        assert status == 403
        assert blocked_live["code"] == "review_acceptance_read_only"

        status, blocked_mutation = _read_json(
            base_url,
            "/api/investment-review/decision",
            method="POST",
            body=b"{}",
        )
        assert status == 403
        assert blocked_mutation["code"] == "review_acceptance_read_only"
        assert service.mutation_calls == 0

        with urlopen(base_url + "/", timeout=5) as response:
            assert response.status == 200
            assert "持仓账本" in response.read().decode("utf-8")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_acceptance_server_requires_exact_candidate_identity(
    tmp_path: Path,
) -> None:
    candidate = tmp_path / "candidate.sqlite3"
    candidate.write_bytes(b"candidate")
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    with pytest.raises(ValueError, match="SHA-256 不匹配"):
        create_dashboard_server(
            PortfolioStore(tmp_path / "formal.sqlite3"),
            host="127.0.0.1",
            port=0,
            investment_review_service=_ReadOnlyReviewService(),  # type: ignore[arg-type]
            investment_review_db=candidate,
            investment_review_artifact_root=artifact_root,
            review_acceptance_read_only=True,
            expected_review_candidate_sha256="0" * 64,
        )


def test_acceptance_cli_skips_portfolio_initialize(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = tmp_path / "candidate.sqlite3"
    candidate.write_bytes(b"candidate")
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    candidate_sha256 = hashlib.sha256(candidate.read_bytes()).hexdigest()
    captured: dict[str, object] = {}

    def fail_initialize(_self: PortfolioStore, *_args: object, **_kwargs: object) -> None:
        raise AssertionError("acceptance mode must skip PortfolioStore.initialize")

    def fake_serve(_store: PortfolioStore, **kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(PortfolioStore, "initialize", fail_initialize)
    monkeypatch.setattr(cli_module, "serve_dashboard", fake_serve)
    result = cli_module.main(
        [
            "--db",
            str(tmp_path / "formal.sqlite3"),
            "web",
            "--host",
            "127.0.0.1",
            "--port",
            "8766",
            "--no-open",
            "--investment-review-acceptance",
            "--investment-review-db",
            str(candidate),
            "--investment-review-artifact-root",
            str(artifact_root),
            "--investment-review-candidate-sha256",
            candidate_sha256,
        ]
    )
    assert result == 0
    assert captured["review_acceptance_read_only"] is True
    assert captured["review_automation"] is False
    assert captured["investment_review_db"] == str(candidate)
    assert captured["investment_review_artifact_root"] == str(artifact_root)


def test_review_store_immutable_acceptance_reads_create_no_aux(
    tmp_path: Path,
) -> None:
    database = tmp_path / "review.sqlite3"
    connection = sqlite3.connect(database)
    connection.execute("CREATE TABLE marker(value TEXT NOT NULL)")
    connection.execute("INSERT INTO marker(value) VALUES ('ready')")
    connection.commit()
    connection.close()

    locked = ReviewStore(
        database,
        immutable_reads=True,
        allow_writes=False,
    )
    with locked.connection(read_only=True) as read_only:
        assert read_only.execute("PRAGMA query_only").fetchone()[0] == 1
        assert read_only.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        assert read_only.execute("SELECT value FROM marker").fetchone()[0] == "ready"
    assert not Path(f"{database}-wal").exists()
    assert not Path(f"{database}-shm").exists()

    with pytest.raises(ReviewStoreError, match="immutable read-only"):
        with locked.connection():
            pass
    with pytest.raises(ReviewStoreError, match="immutable read-only"):
        locked.initialize()


def test_nested_review_store_inherits_immutable_acceptance_context(
    tmp_path: Path,
) -> None:
    database = tmp_path / "review-wal.sqlite3"
    connection = sqlite3.connect(database)
    assert connection.execute("PRAGMA journal_mode = WAL").fetchone()[0] == "wal"
    connection.execute("CREATE TABLE marker(value TEXT NOT NULL)")
    connection.execute("INSERT INTO marker(value) VALUES ('ready')")
    connection.commit()
    connection.close()
    assert not Path(f"{database}-wal").exists()
    assert not Path(f"{database}-shm").exists()

    with immutable_review_store_read_context(database):
        inherited = ReviewStore(database)
        assert inherited.immutable_reads is True
        assert inherited.allow_writes is False
        with inherited.connection(read_only=True) as read_only:
            assert read_only.execute("PRAGMA query_only").fetchone()[0] == 1
            assert (
                read_only.execute("SELECT value FROM marker").fetchone()[0]
                == "ready"
            )

    assert not Path(f"{database}-wal").exists()
    assert not Path(f"{database}-shm").exists()


def test_acceptance_service_reuses_validated_process_local_cache(
    tmp_path: Path,
) -> None:
    review_db = tmp_path / "review.sqlite3"
    review_db.write_bytes(b"candidate")
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    portfolio_db = tmp_path / "portfolio.sqlite3"
    portfolio_db.write_bytes(b"formal")

    class _Runner:
        def __init__(self) -> None:
            self.review_db = review_db
            self.portfolio_db = portfolio_db
            self.artifact_root = artifact_root

    class _Catalog:
        def __init__(self) -> None:
            self.runner = _Runner()
            self.store = ReviewStore(review_db)
            self.bundle_calls = 0
            self.receipt_list_calls = 0
            self.status_list_calls = 0

        def get_episode_bundle(
            self,
            run_id: str,
            review_id: str,
            *,
            validated_receipt: object | None = None,
        ) -> dict[str, object]:
            self.bundle_calls += 1
            return {
                "run_id": run_id,
                "review_id": review_id,
                "validated_receipt": validated_receipt,
            }

        def list_receipts(
            self,
            *,
            scope: str | None = None,
            include_validated_receipt: bool = False,
        ) -> dict[str, object]:
            self.receipt_list_calls += 1
            assert include_validated_receipt is True
            return {"runs": [], "invalid_runs": []}

        def list_run_statuses(
            self,
            *,
            scope: str | None = None,
        ) -> dict[str, object]:
            self.status_list_calls += 1
            return {"runs": []}

    catalog = _Catalog()
    service = InvestmentReviewWebService(
        catalog=catalog,
        repo_root=tmp_path,
        read_only_acceptance=True,
    )
    service.catalog.get_episode_bundle = catalog.get_episode_bundle
    service.catalog.list_receipts = catalog.list_receipts
    service.catalog.list_run_statuses = catalog.list_run_statuses
    run_id = "reviewrun_" + "1" * 32
    review_id = "review:" + "2" * 32

    first = service._bundle(run_id, review_id)  # noqa: SLF001
    second = service._bundle(run_id, review_id)  # noqa: SLF001
    assert first is second
    assert catalog.bundle_calls == 1

    first_listing = service.list_reviews(limit=200)
    second_listing = service.list_reviews(limit=200)
    assert first_listing is second_listing
    assert catalog.receipt_list_calls == 1
    assert catalog.status_list_calls == 1
    assert service.store.immutable_reads is True
    assert service.store.allow_writes is False
