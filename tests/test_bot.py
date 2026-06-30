import asyncio

from src import bot
from src.credits_service import CreditAccountState


class _FakeTransaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeConn:
    def transaction(self):
        return _FakeTransaction()


class _FakeAcquire:
    async def __aenter__(self):
        return _FakeConn()

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakePool:
    def acquire(self):
        return _FakeAcquire()


class _FakeMessage:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def reply_text(self, text: str, reply_markup=None):
        self.calls.append(text)
        assert reply_markup is not None


class _FakeUser:
    def __init__(self) -> None:
        self.id = 123456789
        self.username = "dw-user"
        self.language_code = "ru"


class _FakeUpdate:
    def __init__(self) -> None:
        self.effective_user = _FakeUser()
        self.message = _FakeMessage()


def test_start_grants_credits_before_sending_welcome(monkeypatch):
    events: list[str] = []

    async def fake_ensure_user(_conn, telegram_user_id: int, username: str | None):
        assert telegram_user_id == 123456789
        assert username == "dw-user"
        events.append("ensure_user")
        return 77

    async def fake_ensure_credit_account_state(_conn, user_id: int):
        assert user_id == 77
        events.append("ensure_credit_account_state")
        return CreditAccountState(balance=3, starter_credits_granted_now=True)

    monkeypatch.setattr(bot.db, "get_pool", lambda: _FakePool())
    monkeypatch.setattr(bot, "ensure_user", fake_ensure_user)
    monkeypatch.setattr(bot, "ensure_credit_account_state", fake_ensure_credit_account_state)

    update = _FakeUpdate()
    asyncio.run(bot.start(update, None))

    assert events == ["ensure_user", "ensure_credit_account_state"]
    assert update.message.calls == [
        "Привет! Дарим 3 стартовых credits на 30 дней. "
        "Жми кнопку ниже, чтобы открыть Mini App, или отправь фото машины прямо в чат."
    ]


def test_start_does_not_reannounce_existing_grant(monkeypatch):
    async def fake_ensure_user(_conn, telegram_user_id: int, username: str | None):
        assert telegram_user_id == 123456789
        assert username == "dw-user"
        return 77

    async def fake_ensure_credit_account_state(_conn, user_id: int):
        assert user_id == 77
        return CreditAccountState(balance=3, starter_credits_granted_now=False)

    monkeypatch.setattr(bot.db, "get_pool", lambda: _FakePool())
    monkeypatch.setattr(bot, "ensure_user", fake_ensure_user)
    monkeypatch.setattr(bot, "ensure_credit_account_state", fake_ensure_credit_account_state)

    update = _FakeUpdate()
    asyncio.run(bot.start(update, None))

    assert update.message.calls == [
        "Привет! Mini App уже готов. Жми кнопку ниже, чтобы открыть его, или отправь фото "
        "машины прямо в чат. Стартовый grant действует 30 дней с момента первого начисления."
    ]
