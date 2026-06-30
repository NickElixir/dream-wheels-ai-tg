import asyncio

import asyncpg

from src.credits_service import (
    _calculate_remaining_starter_grant_credits,
    _has_starter_grant_ledger_entry,
    _insert_starter_grant_ledger_entry,
    ensure_credit_account,
    ensure_credit_account_state,
)


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


def test_remaining_starter_grant_drops_to_zero_after_spend_even_with_purchase():
    remaining = _calculate_remaining_starter_grant_credits(
        [
            {
                "event_type": "trial_grant",
                "credits_delta": 3,
                "idempotency_key": "starter_grant:123",
                "metadata": {"kind": "starter_grant"},
            },
            {
                "event_type": "purchase_grant",
                "credits_delta": 20,
                "idempotency_key": "payment_paid:1",
                "metadata": {},
            },
            {
                "event_type": "job_reserve",
                "credits_delta": -3,
                "idempotency_key": "job_reserve:1",
                "metadata": {},
            },
        ],
        user_id=123,
        granted_credits=3,
    )

    assert remaining == 0


def test_remaining_starter_grant_restores_refunded_credit():
    remaining = _calculate_remaining_starter_grant_credits(
        [
            {
                "event_type": "trial_grant",
                "credits_delta": 3,
                "idempotency_key": "starter_grant:123",
                "metadata": {"kind": "starter_grant"},
            },
            {
                "event_type": "job_reserve",
                "credits_delta": -1,
                "idempotency_key": "job_reserve:1",
                "metadata": {},
            },
            {
                "event_type": "job_refund",
                "credits_delta": 1,
                "idempotency_key": "job_refund:1",
                "metadata": {},
            },
        ],
        user_id=123,
        granted_credits=3,
    )

    assert remaining == 3


def test_ensure_credit_account_state_marks_new_grant():
    class FakeConn:
        def __init__(self) -> None:
            self.fetchrow_calls = 0
            self.execute_calls: list[tuple[str, tuple[object, ...]]] = []

        async def execute(self, query: str, *args):
            self.execute_calls.append((query, args))
            return "INSERT 0 1"

        async def fetchrow(self, query: str, *args):
            self.fetchrow_calls += 1
            if "SELECT balance, trial_used_at" in query:
                return {"balance": 0, "trial_used_at": None}
            if "FROM credit_ledger" in query:
                return None
            raise AssertionError(query)

        async def fetchval(self, query: str, *args):
            assert "starter_grant" in query
            return None

        def transaction(self):
            return _FakeTransaction()

    state = asyncio.run(ensure_credit_account_state(FakeConn(), 123))

    assert state.balance == 3
    assert state.starter_credits_granted_now is True


def test_ensure_credit_account_state_marks_existing_grant_without_regrant():
    class FakeConn:
        async def execute(self, query: str, *args):
            return "INSERT 0 0"

        async def fetchrow(self, query: str, *args):
            if "SELECT balance, trial_used_at" in query:
                return {"balance": 3, "trial_used_at": "2026-06-30T00:00:00Z"}
            if "FROM credit_ledger" in query:
                return None
            raise AssertionError(query)

        async def fetchval(self, query: str, *args):
            return None

        def transaction(self):
            return _FakeTransaction()

    state = asyncio.run(ensure_credit_account_state(FakeConn(), 123))

    assert state.balance == 3
    assert state.starter_credits_granted_now is False


def test_ensure_credit_account_keeps_int_contract(monkeypatch):
    async def fake_state(_conn, _user_id: int):
        return type("State", (), {"balance": 5, "starter_credits_granted_now": False})()

    monkeypatch.setattr("src.credits_service.ensure_credit_account_state", fake_state)

    balance = asyncio.run(ensure_credit_account(object(), 123))

    assert balance == 5
