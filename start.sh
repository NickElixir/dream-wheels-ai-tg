#!/bin/bash

# Получаем порт от Render (или используем 10000 по умолчанию)
PORT=${PORT:-10000}

echo "Запускаем бэкенд FastAPI на порту $PORT..."
# uvicorn ищет ASGI-app по dotted path: <module>:<attr>
uvicorn src.main:app --host 0.0.0.0 --port $PORT &

echo "Запускаем Telegram-бота..."
python -m src.bot &

# wait -n завершается, как только упадёт первый процесс — Render
# увидит ненулевой exit и перезапустит контейнер целиком.
wait -n

exit $?
