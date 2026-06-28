"""Централизованный доступ к переменным окружения.

Все os.getenv() — здесь, чтобы:
- было одно место для документации/проверки переменных;
- удобно импортировать: `from src.config import DATABASE_URL`;
- легко подменять в тестах через monkeypatch.
"""

import os
from urllib.parse import urlparse

# Storage
DATABASE_URL = os.getenv("DATABASE_URL")
REDIS_URL = os.getenv("REDIS_URL")
REDIS_KEY_PREFIX = os.getenv("REDIS_KEY_PREFIX", "")
REDIS_JOB_QUEUE = os.getenv("REDIS_JOB_QUEUE", "job_queue")
WORKER_ENABLED = os.getenv("WORKER_ENABLED", "true").lower() == "true"

# External APIs
REVE_API_KEY = os.getenv("REVE_API_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_INTERNAL_TOKEN = os.getenv("API_INTERNAL_TOKEN")


def _env_str(name: str) -> str:
    return os.getenv(name, "").strip()


def _infer_supabase_project_ref() -> str:
    project_ref = _env_str("SUPABASE_PROJECT_REF")
    if project_ref:
        return project_ref

    supabase_url = _env_str("SUPABASE_URL").rstrip("/")
    if not supabase_url:
        return ""

    host = urlparse(supabase_url).hostname or ""
    if not host.endswith(".supabase.co"):
        return ""

    return host.removesuffix(".supabase.co")


# Supabase
SUPABASE_URL = _env_str("SUPABASE_URL").rstrip("/")
SUPABASE_PROJECT_REF = _infer_supabase_project_ref()
SUPABASE_SERVICE_ROLE_KEY = _env_str("SUPABASE_SERVICE_ROLE_KEY")
SUPABASE_STORAGE_URL = (
    f"{SUPABASE_URL}/storage/v1"
    if SUPABASE_URL
    else (f"https://{SUPABASE_PROJECT_REF}.supabase.co/storage/v1" if SUPABASE_PROJECT_REF else "")
)

# URLs
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "https://dream-wheels-ai-tg.onrender.com").rstrip(
    "/"
)
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:10000").rstrip("/")
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://dream-wheels-ai-webapp.vercel.app").rstrip("/")
LEGAL_BASE_URL = os.getenv("LEGAL_BASE_URL", "https://dream-wheels-ai-legal.vercel.app").rstrip("/")

# Billing / credits
STARTER_GRANT_CREDITS = int(os.getenv("STARTER_GRANT_CREDITS", "3"))
JOB_CREDIT_COST = int(os.getenv("JOB_CREDIT_COST", "1"))
PAYMENTS_ENABLED = os.getenv("PAYMENTS_ENABLED", "true").lower() == "true"
WEBAPP_DEV_AUTH_ENABLED = os.getenv("WEBAPP_DEV_AUTH_ENABLED", "false").lower() == "true"
TELEGRAM_LOGIN_CLIENT_ID = _env_str("TELEGRAM_LOGIN_CLIENT_ID")
TELEGRAM_LOGIN_CLIENT_SECRET = _env_str("TELEGRAM_LOGIN_CLIENT_SECRET")
TELEGRAM_LOGIN_ISSUER = _env_str("TELEGRAM_LOGIN_ISSUER") or "https://oauth.telegram.org"
TELEGRAM_LOGIN_JWKS_URL = (
    _env_str("TELEGRAM_LOGIN_JWKS_URL") or "https://oauth.telegram.org/.well-known/jwks.json"
)
TELEGRAM_AUTH_TOKEN_SECRET = _env_str("TELEGRAM_AUTH_TOKEN_SECRET")
TELEGRAM_AUTH_TOKEN_TTL_SEC = int(os.getenv("TELEGRAM_AUTH_TOKEN_TTL_SEC", "3600"))
TELEGRAM_LOGIN_NONCE_TTL_SEC = int(os.getenv("TELEGRAM_LOGIN_NONCE_TTL_SEC", "600"))

# Robokassa
ROBOKASSA_MERCHANT_LOGIN = os.getenv("ROBOKASSA_MERCHANT_LOGIN", "")
ROBOKASSA_PASSWORD1 = os.getenv("ROBOKASSA_PASSWORD1", "")
ROBOKASSA_PASSWORD2 = os.getenv("ROBOKASSA_PASSWORD2", "")
ROBOKASSA_PASSWORD3 = os.getenv("ROBOKASSA_PASSWORD3", "")
ROBOKASSA_TEST_PASSWORD1 = os.getenv("ROBOKASSA_TEST_PASSWORD1", "")
ROBOKASSA_TEST_PASSWORD2 = os.getenv("ROBOKASSA_TEST_PASSWORD2", "")
ROBOKASSA_PAYMENT_URL = os.getenv(
    "ROBOKASSA_PAYMENT_URL", "https://auth.robokassa.ru/Merchant/Index.aspx"
)
ROBOKASSA_HASH_ALGO = os.getenv("ROBOKASSA_HASH_ALGO", "md5").lower()
ROBOKASSA_IS_TEST = os.getenv("ROBOKASSA_IS_TEST", "false").lower() == "true"


def runtime_env_summary() -> dict[str, str | bool | None]:
    supabase_host = urlparse(SUPABASE_URL).hostname if SUPABASE_URL else None
    return {
        "supabase_project_ref": SUPABASE_PROJECT_REF or None,
        "supabase_host": supabase_host,
        "storage_configured": bool(SUPABASE_STORAGE_URL and SUPABASE_SERVICE_ROLE_KEY),
        "payments_test_mode": ROBOKASSA_IS_TEST,
    }
