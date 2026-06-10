"""Централизованный доступ к переменным окружения.

Все os.getenv() — здесь, чтобы:
- было одно место для документации/проверки переменных;
- удобно импортировать: `from src.config import DATABASE_URL`;
- легко подменять в тестах через monkeypatch.
"""

import os

# Storage
DATABASE_URL = os.getenv("DATABASE_URL")
REDIS_URL = os.getenv("REDIS_URL")
WORKER_ENABLED = os.getenv("WORKER_ENABLED", "true").lower() == "true"

# External APIs
REVE_API_KEY = os.getenv("REVE_API_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Supabase
SUPABASE_PROJECT_REF = os.getenv("SUPABASE_PROJECT_REF", "qmgyccghsbdpehiybjae")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
SUPABASE_STORAGE_URL = f"https://{SUPABASE_PROJECT_REF}.supabase.co/storage/v1"

# URLs
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "https://dream-wheels-ai-tg.onrender.com").rstrip(
    "/"
)
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:10000").rstrip("/")
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://dream-wheels-ai-webapp.vercel.app").rstrip("/")

# Payments (Robokassa)
ROBOKASSA_PAYMENT_URL = os.getenv(
    "ROBOKASSA_PAYMENT_URL",
    "https://auth.robokassa.ru/Merchant/Index.aspx",
).rstrip("/")
ROBOKASSA_MERCHANT_LOGIN = os.getenv("ROBOKASSA_MERCHANT_LOGIN")
ROBOKASSA_PASSWORD1 = os.getenv("ROBOKASSA_PASSWORD1")
ROBOKASSA_PASSWORD2 = os.getenv("ROBOKASSA_PASSWORD2")
ROBOKASSA_PASSWORD3 = os.getenv("ROBOKASSA_PASSWORD3")
ROBOKASSA_IS_TEST = os.getenv("ROBOKASSA_IS_TEST", "true").lower() == "true"
PREORDER_AMOUNT_RUB = os.getenv("PREORDER_AMOUNT_RUB", "990.00")
PAYMENTS_ENABLED = os.getenv("PAYMENTS_ENABLED", "false").lower() == "true"
