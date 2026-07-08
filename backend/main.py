"""FastAPI 主入口"""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from database import init_db
from routers import admin, auth as auth_router, edit, history, providers
from config import UPLOAD_DIR, OUTPUT_DIR, CORS_ALLOWED_ORIGINS, validate_startup_config
from services.admin_bootstrap import ensure_admin_account


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    validate_startup_config()
    await init_db()
    await ensure_admin_account()
    print("数据库初始化完成")
    yield


app = FastAPI(
    title="AI 图像编辑 API",
    description="基于 Gemini / OpenAI 的图像编辑服务",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 配置（通过 CORS_ALLOWED_ORIGINS 环境变量设置白名单，默认仅开发环境使用 *）
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth_router.router)
app.include_router(admin.router)
app.include_router(edit.router)
app.include_router(history.router)
app.include_router(providers.router)

# 静态文件服务
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
app.mount("/outputs", StaticFiles(directory=str(OUTPUT_DIR)), name="outputs")


@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "AI 图像编辑 API",
        "docs": "/docs",
        "version": "1.0.0"
    }


@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=True
    )
