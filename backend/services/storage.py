"""图片存储服务：上传图和生成图统一保存到数据库。"""
import uuid
from typing import List, Optional
from mimetypes import guess_type
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from models.database import ImageAsset

ASSET_URL_PREFIX = "/api/assets/"


def _content_type(suffix: str) -> str:
    return guess_type(f"file{suffix}")[0] or "application/octet-stream"


async def save_upload(
    db: AsyncSession,
    file_bytes: bytes,
    suffix: str = ".jpg",
    filename: Optional[str] = None,
) -> tuple[str, str]:
    """
    将上传图片保存到数据库。

    Returns:
        (asset_id, relative_url)
    """
    asset_id = str(uuid.uuid4())
    asset = ImageAsset(
        id=asset_id,
        filename=filename or f"{asset_id}{suffix}",
        content_type=_content_type(suffix),
        data=file_bytes,
        size_bytes=len(file_bytes),
    )
    db.add(asset)
    await db.flush()
    return asset_id, f"{ASSET_URL_PREFIX}{asset_id}"


async def save_output(db: AsyncSession, file_bytes: bytes, prefix: str = "result") -> str:
    """
    将生成结果保存到数据库。

    Returns:
        relative_url
    """
    _, url = await save_upload(db, file_bytes, ".png", f"{prefix}_{uuid.uuid4().hex[:8]}.png")
    return url


async def save_outputs(db: AsyncSession, images: List[bytes], prefix: str = "result") -> List[str]:
    """批量保存结果图"""
    return [await save_output(db, img, prefix) for img in images]


async def get_file_bytes(db: AsyncSession, relative_url: str) -> Optional[bytes]:
    """
    根据相对 URL 读取文件内容

    Args:
        relative_url: 数据库资源 URL，如 /api/assets/xxx

    Returns:
        文件字节，不存在则返回 None
    """
    if relative_url.startswith(ASSET_URL_PREFIX):
        asset_id = relative_url[len(ASSET_URL_PREFIX):].split("/", 1)[0]
        result = await db.execute(select(ImageAsset).where(ImageAsset.id == asset_id))
        asset = result.scalar_one_or_none()
        return asset.data if asset else None

    return None


async def delete_file(db: AsyncSession, relative_url: str) -> bool:
    """删除数据库中的图片资源。"""
    if relative_url.startswith(ASSET_URL_PREFIX):
        asset_id = relative_url[len(ASSET_URL_PREFIX):].split("/", 1)[0]
        result = await db.execute(select(ImageAsset).where(ImageAsset.id == asset_id))
        asset = result.scalar_one_or_none()
        if not asset:
            return False
        await db.delete(asset)
        return True

    return False
