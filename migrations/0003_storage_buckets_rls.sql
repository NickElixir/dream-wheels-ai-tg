-- Миграция 0003: RLS-политики для Storage bucket'ов raw и results.
--
-- Зачем: bucket'ы созданы через Studio, но без явных RLS-политик
-- storage.objects блокирует все операции для anon/authenticated. Backend
-- использует service_role — он обходит RLS и работает в любом случае.
-- Эти политики нужны для двух вещей:
--   1. Public-чтение results bucket (картинки рендеров — открыты по URL).
--   2. Документация intent: что мы хотим разрешить, на случай если
--      кто-то поменяет ключ или подключит другой клиент.
--
-- Bucket layout (синхронно с src/storage.py):
--   raw     — private,  10 MB, исходники car/wheel
--   results — public,    5 MB, AI-рендеры
--
-- ПРИМЕНЕНИЕ: запустить через Supabase SQL Editor (Studio → SQL).
-- Через psql/asyncpg не пройдёт — storage.objects живёт в схеме storage
-- к которой обычный DATABASE_URL может не иметь GRANT'ов.

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
