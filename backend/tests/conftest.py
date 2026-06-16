"""测试共享 fixtures"""
import os

# 在所有项目导入之前设置环境变量
os.environ["JWT_SECRET_KEY"] = "test-only-secret-key-minimum-32-characters-x!"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./tests/test.db"
os.environ["ADMIN_USERNAME"] = ""
os.environ["ADMIN_PHONE"] = ""
os.environ["ADMIN_PASSWORD"] = ""

import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from database import Base, engine
from main import app


@pytest_asyncio.fixture(autouse=True)
async def reset_db():
    """每个测试前建表，测试后清空数据，保证用例隔离。"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
