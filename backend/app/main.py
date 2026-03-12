from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.database import init_db
from app.config import settings
from app.routers import tweets_router, media_router, settings_router, llm_router, engage_router, monitor_router, logs_router, cookies_router
from app.services.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时
    await init_db()
    start_scheduler()
    yield
    # 关闭时
    stop_scheduler()


app = FastAPI(
    title="HAA Social Autopilot",
    description="Twitter/X automation tool for HAA project",
    version="0.1.0",
    lifespan=lifespan
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(tweets_router)
app.include_router(media_router)
app.include_router(settings_router)
app.include_router(llm_router)
app.include_router(engage_router)
app.include_router(monitor_router)
app.include_router(logs_router)
app.include_router(cookies_router)

# 静态文件服务（上传的媒体文件）
os.makedirs(settings.upload_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")


@app.get("/")
async def root():
    return {
        "name": "HAA Social Autopilot",
        "version": "0.1.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
