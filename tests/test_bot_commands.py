import asyncio

from src import bot

WEBAPP_URL = "https://dream-wheels-ai-webapp.vercel.app"
LEGAL_BASE_URL = "https://dream-wheels-ai-legal.vercel.app"


class DummyMessage:
    def __init__(self) -> None:
        self.calls = []

    async def reply_text(self, text, reply_markup=None):
        self.calls.append((text, reply_markup))


class DummyUser:
    def __init__(self, language_code: str = "ru") -> None:
        self.language_code = language_code


class DummyUpdate:
    def __init__(self, language_code: str = "ru") -> None:
        self.effective_user = DummyUser(language_code)
        self.effective_message = DummyMessage()


def test_webapp_url_builder_support_section():
    assert bot._webapp_url("support") == f"{WEBAPP_URL}/?section=support"


def test_legal_url_builder_points_to_public_domain():
    assert bot._legal_url("/legal/offer") == f"{LEGAL_BASE_URL}/legal/offer"


def test_start_replies_with_webapp_button():
    update = DummyUpdate()

    asyncio.run(bot.start(update, None))

    assert len(update.effective_message.calls) == 1
    text, markup = update.effective_message.calls[0]
    assert "Mini App" in text
    assert markup.inline_keyboard[0][0].web_app.url == WEBAPP_URL


def test_support_command_opens_support_section():
    update = DummyUpdate()

    asyncio.run(bot.support_command(update, None))

    _, markup = update.effective_message.calls[0]
    assert markup.inline_keyboard[0][0].web_app.url == f"{WEBAPP_URL}/?section=support"


def test_terms_command_opens_public_offer():
    update = DummyUpdate()

    asyncio.run(bot.terms_command(update, None))

    _, markup = update.effective_message.calls[0]
    assert markup.inline_keyboard[0][0].url == f"{LEGAL_BASE_URL}/legal/offer"
