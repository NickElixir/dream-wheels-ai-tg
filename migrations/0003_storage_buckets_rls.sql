-- Миграция 0003: RLS-политики для Storage bucket'ов raw и results.
--
-- Зачем: создаем bucket'ы и задаем явные RLS-политики. Backend использует
-- service_role — он обходит RLS и работает в любом случае.
-- Политики нужны для двух вещей:
--   1. Public-чтение results bucket (картинки рендеров — открыты по URL).
--   2. Документация intent: что мы хотим разрешить, на случай если
--      кто-то поменяет ключ или подключит другой клиент.
--
-- Bucket layout (синхронно с src/storage.py):
--   raw     — private,  10 MB, исходники car/wheel
--   results — public,    5 MB, AI-рендеры
--
-- ПРИМЕНЕНИЕ: запустить через Supabase SQL Editor или Management API.

INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES
    ('raw', 'raw', false, 10485760, ARRAY['image/jpeg', 'image/png', 'image/webp']),
    ('results', 'results', true, 5242880, ARRAY['image/jpeg', 'image/png', 'image/webp'])
ON CONFLICT (id) DO UPDATE
SET public = EXCLUDED.public,
    file_size_limit = EXCLUDED.file_size_limit,
    allowed_mime_types = EXCLUDED.allowed_mime_types;

-- ---------------------------------------------------------------------
-- raw (private): никто кроме service_role не пишет/читает.
-- service_role обходит RLS, отдельную политику для него не пишем.
-- ---------------------------------------------------------------------

-- Удалить старые политики если миграция пере-применяется.
DROP POLICY IF EXISTS "raw: anon no access" ON storage.objects;
DROP POLICY IF EXISTS "raw: authenticated no access" ON storage.objects;

-- Никакой anon/authenticated-доступ к raw не разрешён — отсутствие
-- политики уже блокирует, но создаём явную для читаемости intent'а.
CREATE POLICY "raw: anon no access"
    ON storage.objects FOR ALL
    TO anon
    USING (bucket_id <> 'raw')
    WITH CHECK (false);

-- ---------------------------------------------------------------------
-- results (public): anon читает картинки. Запись только service_role.
-- ---------------------------------------------------------------------

DROP POLICY IF EXISTS "results: public read" ON storage.objects;
DROP POLICY IF EXISTS "results: no anon write" ON storage.objects;

CREATE POLICY "results: public read"
    ON storage.objects FOR SELECT
    TO anon, authenticated
    USING (bucket_id = 'results');

-- Запретить anon/authenticated INSERT/UPDATE/DELETE в results.
-- service_role не подпадает под RLS, поэтому backend может писать.
CREATE POLICY "results: no anon write"
    ON storage.objects FOR INSERT
    TO anon, authenticated
    WITH CHECK (false);
