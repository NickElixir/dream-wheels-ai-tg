-- Миграция 0004: поле feedback для сбора лайков/дизлайков на результат рендера
-- Применяется вручную через psql или Supabase SQL editor.

ALTER TABLE jobs ADD COLUMN IF NOT EXISTS feedback VARCHAR(10);
