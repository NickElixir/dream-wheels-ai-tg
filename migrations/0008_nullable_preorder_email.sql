-- Миграция 0006: email необязателен для Telegram top-up платежей.
--
-- Старый preorder API продолжает требовать email на уровне Pydantic.
-- Для Mini App top-up source of truth пользователя — telegram_user_id.

ALTER TABLE preorders
    ALTER COLUMN email DROP NOT NULL;
