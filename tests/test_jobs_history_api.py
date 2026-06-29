from datetime import UTC, datetime

from fastapi.testclient import TestClient

from src import jobs_api
from src.auth import AuthContext
from src.main import app

client = TestClient(app)


def _base_asset_fields(prefix: str, *, kind: str | None = None) -> dict:
    return {
        f"{prefix}_asset_id": f"00000000-0000-4000-8000-00000000000{len(prefix)}" if kind else None,
        f"{prefix}_asset_kind": kind,
        f"{prefix}_asset_bucket": "results" if kind == "result" else "raw",
        f"{prefix}_asset_storage_key": f"users/10/jobs/job/{kind}/asset.jpg" if kind else None,
        f"{prefix}_asset_content_type": "image/jpeg" if kind else None,
        f"{prefix}_asset_size_bytes": 123 if kind else None,
        f"{prefix}_asset_width": None,
        f"{prefix}_asset_height": None,
        f"{prefix}_asset_created_at": datetime(2026, 6, 29, tzinfo=UTC) if kind else None,
    }


def _job_row(**overrides) -> dict:
    row = {
        "job_id": "11111111-1111-4111-8111-111111111111",
        "status": "completed",
        "created_at": datetime(2026, 6, 29, tzinfo=UTC),
        "completed_at": datetime(2026, 6, 29, tzinfo=UTC),
        "output_image_url": "https://example.test/result.jpg",
        "error_code": None,
        "error_message": None,
        "generation_provider": "reve",
        "provider_request_id": "safe-id",
    }
    row.update(_base_asset_fields("car", kind="car_original"))
    row.update(_base_asset_fields("rim", kind="rim_original"))
    row.update(_base_asset_fields("result", kind="result"))
    row.update(overrides)
    return row


class FakeAcquire:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakePool:
    def __init__(self, conn):
        self.conn = conn

    def acquire(self):
        return FakeAcquire(self.conn)


def _patch_auth(monkeypatch, *, user_id: int = 10) -> None:
    monkeypatch.setattr(
        jobs_api,
        "_resolve_jobs_auth",
        lambda **_kwargs: AuthContext(
            telegram_user_id=123456789,
            username="dw-user",
            auth_channel="website",
        ),
    )

    async def fake_ensure_user(_conn, telegram_user_id: int, username: str | None):
        assert telegram_user_id == 123456789
        assert username == "dw-user"
        return user_id

    monkeypatch.setattr(jobs_api, "ensure_user", fake_ensure_user)


def test_history_query_is_scoped_to_authenticated_user(monkeypatch):
    calls: list[tuple[str, tuple]] = []

    class FakeConn:
        async def fetch(self, query: str, *args):
            calls.append((query, args))
            assert "WHERE jobs.user_id = $1" in query
            return [_job_row()]

    _patch_auth(monkeypatch, user_id=10)
    monkeypatch.setattr(jobs_api.db, "get_pool", lambda: FakePool(FakeConn()))

    response = client.get("/jobs?limit=5&offset=0")

    assert response.status_code == 200
    assert calls[0][1] == (10, 5, 0)
    body = response.json()
    assert body["jobs"][0]["job_id"] == "11111111-1111-4111-8111-111111111111"
    assert set(body["jobs"][0]["assets"]) == {"car_original", "rim_original", "result"}


def test_job_detail_returns_404_for_non_owner(monkeypatch):
    class FakeConn:
        async def fetchrow(self, query: str, *args):
            assert "AND jobs.user_id = $2" in query
            assert args[1] == 10
            return None

    _patch_auth(monkeypatch, user_id=10)
    monkeypatch.setattr(jobs_api.db, "get_pool", lambda: FakePool(FakeConn()))

    response = client.get("/jobs/11111111-1111-4111-8111-111111111111?telegram_user_id=123")

    assert response.status_code == 404


def test_failed_job_status_returns_error_metadata_for_owner(monkeypatch):
    class FakeConn:
        async def fetchrow(self, *_args):
            return _job_row(
                status="failed",
                output_image_url=None,
                completed_at=None,
                error_code="StorageError",
                error_message="Storage upload failed",
                **_base_asset_fields("result"),
            )

    _patch_auth(monkeypatch, user_id=10)
    monkeypatch.setattr(jobs_api.db, "get_pool", lambda: FakePool(FakeConn()))

    response = client.get("/jobs/11111111-1111-4111-8111-111111111111/status?telegram_user_id=123")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["error_code"] == "StorageError"
    assert body["error"] == "Storage upload failed"


def test_legacy_job_response_keeps_existing_shape(monkeypatch):
    monkeypatch.setattr(jobs_api, "_resolve_jobs_auth", lambda **_kwargs: None)

    class FakeConn:
        async def fetchrow(self, query: str, *args):
            assert query == "SELECT status, output_image_url FROM jobs WHERE id = $1::uuid"
            return {"status": "queued", "output_image_url": None}

    monkeypatch.setattr(jobs_api.db, "get_pool", lambda: FakePool(FakeConn()))

    response = client.get("/jobs/11111111-1111-4111-8111-111111111111")

    assert response.status_code == 200
    assert response.json() == {"status": "queued", "output_image_url": None}
