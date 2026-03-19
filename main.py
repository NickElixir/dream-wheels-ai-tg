from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import asyncpg
import redis.asyncio as redis
import os
import json

# Инициализация приложения FastAPI 
app = FastAPI(title="Wheel Try-On API (MVP)")

# ==========================================
# ⚙️ НАСТРОЙКИ ПОДКЛЮЧЕНИЙ
# ==========================================
# Сюда вы вставите ссылки, которые вам выдал Neon/Supabase и ваш Redis-провайдер
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/dbname")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Глобальные переменные для пула соединений
db_pool = None
redis_client = None

# ==========================================
# 📦 Pydantic СХЕМЫ (Валидация данных)
# ==========================================
class JobCreateRequest(BaseModel):
    telegram_user_id: int
    car_file_id: str
    wheel_file_id: str

class JobCreateResponse(BaseModel):
    job_id: str
    status: str

class JobStatusResponse(BaseModel):
    status: str
    output_image_url: str | None = None

# ==========================================
# 🔄 ЖИЗНЕННЫЙ ЦИКЛ ПРИЛОЖЕНИЯ
# ==========================================
@app.on_event("startup")
async def startup():
    global db_pool, redis_client
    # Открываем пул соединений с PostgreSQL
    db_pool = await asyncpg.create_pool(DATABASE_URL)
    # Подключаемся к Redis 
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)

@app.on_event("shutdown")
async def shutdown():
    # Закрываем соединения при выключении сервера
    await db_pool.close()
    await redis_client.close()

# ==========================================
# 🚀 ЭНДПОИНТЫ (API Routes)
# ==========================================

# 1. Проверка здоровья (Uptime check) [cite: 15]
@app.get("/health")
async def health_check():
    return {"status": "ok"}

# 2. Создание задачи (Create job) [cite: 15]
@app.post("/jobs", response_model=JobCreateResponse)
async def create_job(request: JobCreateRequest):
    async with db_pool.acquire() as connection:
        # Шаг 1: Проверяем, есть ли пользователь, если нет - создаем
        user_id = await connection.fetchval(
            "SELECT id FROM users WHERE telegram_user_id = $1", 
            request.telegram_user_id
        )
        if not user_id:
            user_id = await connection.fetchval(
                "INSERT INTO users (telegram_user_id) VALUES ($1) RETURNING id",
                request.telegram_user_id
            )
        
        # Шаг 2: Создаем запись о задаче в БД со статусом 'queued' [cite: 13, 15]
        job_id = await connection.fetchval(
            """
            INSERT INTO jobs (user_id, status) 
            VALUES ($1, 'queued') 
            RETURNING id
            """,
            user_id
        )
        job_id_str = str(job_id)

    # Шаг 3: Формируем полезную нагрузку для очереди
    # В реальном MVP здесь также может быть логика скачивания файлов и загрузки в S3 [cite: 15]
    job_payload = {
        "job_id": job_id_str,
        "telegram_user_id": request.telegram_user_id,
        "car_file_id": request.car_file_id,
        "wheel_file_id": request.wheel_file_id
    }
    
    # Шаг 4: Отправляем задачу в Redis очередь (RPUSH) [cite: 2, 15]
    await redis_client.rpush("image_processing_queue", json.dumps(job_payload))
    
    # Возвращаем ID задачи и статус [cite: 15]
    return JobCreateResponse(job_id=job_id_str, status="queued")

# 3. Проверка статуса задачи (Poll job status) [cite: 15]
@app.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    async with db_pool.acquire() as connection:
        # Ищем задачу в БД
        row = await connection.fetchrow(
            "SELECT status, output_image_url FROM jobs WHERE id = $1",
            job_id
        )
        
        if not row:
            raise HTTPException(status_code=404, detail="Job not found")
            
        # Возвращаем статус и ссылку на готовую картинку (если есть) [cite: 15]
        return JobStatusResponse(
            status=row["status"],
            output_image_url=row["output_image_url"]
        )
