import asyncio

import asyncpg

from src.credits_service import _has_starter_grant_ledger_entry, _insert_starter_grant_ledger_entry


class _FakeTransaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


def test_has_starter_grant_uses_idempotency_key_instead_of_any_manual_adjustment():
    class FakeConn:
        async def fetchval(self, query: str, *args):
            assert "idempotency_key = $2" in query
            assert "operation_type = 'manual_adjustment'" not in query
            assert args == (123, "starter_grant:123")
            return 1

    assert asyncio.run(_has_starter_grant_ledger_entry(FakeConn(), 123)) is True


def test_insert_starter_grant_fallback_does_not_abort_outer_flow():
    class FakeConn:
        def __init__(self) -> None:
            self.calls = 0

        def transaction(self):
            return _FakeTransaction()

        async def execute(self, query: str, *args):
            self.calls += 1
            if self.calls == 1:
                raise asyncpg.PostgresError("legacy constraint mismatch")
            assert "operation_type" in query
            assert args == (123, 3, "starter_grant:123")
            return "INSERT 0 1"

    asyncio.run(_insert_starter_grant_ledger_entry(FakeConn(), user_id=123, balance_after=3))
