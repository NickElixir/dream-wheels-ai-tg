import asyncio

from fastapi.testclient import TestClient

from src import jobs_api
from src.main import app

client = TestClient(app)


def test_compensate_queue_publish_failure_refunds_credit_and_marks_job_failed():
    calls: list[tuple[str, object]] = []

    class FakeTransaction:
        async def __aenter__(self):
            calls.append(("transaction_enter", None))
            return self

        async def __aexit__(self, exc_type, exc, tb):
            calls.append(("transaction_exit", exc_type))
            return False

    class FakeConn:
        def transaction(self):
            return FakeTransaction()

        async def execute(self, query: str, *args):
            calls.append(("execute", query, args))

    class FakeAcquire:
        async def __aenter__(self):
            return FakeConn()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakePool:
        def acquire(self):
            return FakeAcquire()

    async def fake_refund_job_credit(conn, *, user_id: int, job_id: str):
        calls.append(("refund", user_id, job_id))
        return 5

    original_refund = jobs_api.refund_job_credit
    jobs_api.refund_job_credit = fake_refund_job_credit
    try:
        asyncio.run(
            jobs_api._compensate_queue_publish_failure(
                pool=FakePool(),
                user_id=77,
                job_id="11111111-1111-1111-1111-111111111111",
                error_message="Queue publish failed",
            )
        )
    finally:
        jobs_api.refund_job_credit = original_refund

    assert ("refund", 77, "11111111-1111-1111-1111-111111111111") in calls
    assert any(
        item[0] == "execute"
        and "UPDATE jobs SET status = 'failed', error_code = $1, error_message = $2" in item[1]
        and item[2]
        == (
            "QUEUE_PUBLISH_FAILED",
            "Queue publish failed",
            "11111111-1111-1111-1111-111111111111",
        )
        for item in calls
    )


def test_create_job_returns_503_when_queue_publish_fails(monkeypatch):
    class FakeTransaction:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakeConn:
        def transaction(self):
            return FakeTransaction()

        async def execute(self, *_args, **_kwargs):
            return None

    class FakeAcquire:
        async def __aenter__(self):
            return FakeConn()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakePool:
        def acquire(self):
            return FakeAcquire()

    class FakeRedis:
        async def rpush(self, *_args, **_kwargs):
            raise RuntimeError("redis down")

    async def fake_enforce_rate_limit(**_kwargs):
        return None

    async def fake_ensure_user(_conn, telegram_user_id: int, username: str | None):
        assert telegram_user_id == 1
        assert username is None
        return 77

    async def fake_reserve_job_credit(_conn, *, user_id: int, job_id: str):
        assert user_id == 77
        assert job_id
        return 2

    compensated: list[tuple[int, str, str]] = []

    async def fake_compensate(*, pool, user_id: int, job_id: str, error_message: str):
        assert pool is fake_pool
        compensated.append((user_id, job_id, error_message))

    fake_pool = FakePool()
    monkeypatch.setattr(jobs_api, "enforce_rate_limit", fake_enforce_rate_limit)
    monkeypatch.setattr(jobs_api.db, "get_pool", lambda: fake_pool)
    monkeypatch.setattr(jobs_api.redis_client, "get_client", lambda: FakeRedis())
    monkeypatch.setattr(jobs_api, "ensure_user", fake_ensure_user)
    monkeypatch.setattr(jobs_api, "reserve_job_credit", fake_reserve_job_credit)
    monkeypatch.setattr(jobs_api, "_compensate_queue_publish_failure", fake_compensate)

    response = client.post(
        "/jobs",
        json={
            "telegram_user_id": 1,
            "car_url": "https://api.telegram.org/file/bot123/car.jpg",
            "wheel_url": "https://api.telegram.org/file/bot123/wheel.jpg",
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Job queue is temporarily unavailable"
    assert len(compensated) == 1
    assert compensated[0][0] == 77
    assert compensated[0][2] == "Queue publish failed"
