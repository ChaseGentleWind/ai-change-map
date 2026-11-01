"""FastAPI 主入口"""
from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db, init_db
from models.database import ImageAsset
from routers import admin, auth as auth_router, edit, history
from config import CORS_ALLOWED_ORIGINS, validate_startup_config
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


@app.get("/api/assets/{asset_id}", include_in_schema=False)
async def get_image_asset(
    asset_id: str,
    db: AsyncSession = Depends(get_db),
):
    """从数据库返回图片资源，供页面的 img 标签直接读取。"""
    result = await db.execute(select(ImageAsset).where(ImageAsset.id == asset_id))
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(404, "图片资源不存在")
    return Response(
        content=asset.data,
        media_type=asset.content_type,
        headers={"Cache-Control": "private, max-age=3600"},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=True
    )
