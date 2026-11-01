"""数据库图片资源存储测试。"""
from sqlalchemy import select

from models.database import ImageAsset
from services.storage import get_file_bytes, save_upload


async def test_uploaded_asset_is_stored_in_database_and_served(client):
    from database import AsyncSessionLocal

    image_bytes = b"database-backed-image"
    async with AsyncSessionLocal() as db:
        asset_id, asset_url = await save_upload(db, image_bytes, ".png", "original.png")
        await db.commit()

        result = await db.execute(select(ImageAsset).where(ImageAsset.id == asset_id))
        asset = result.scalar_one()
        assert asset.data == image_bytes
        assert asset.size_bytes == len(image_bytes)
        assert asset.content_type == "image/png"
        assert await get_file_bytes(db, asset_url) == image_bytes

    response = await client.get(asset_url)
    assert response.status_code == 200
    assert response.content == image_bytes
    assert response.headers["content-type"] == "image/png"


async def test_missing_database_asset_returns_404(client):
    response = await client.get("/api/assets/missing-asset")
    assert response.status_code == 404
