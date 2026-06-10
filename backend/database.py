"""数据库连接与会话管理"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from pathlib import Path
import os

# 确保 db 目录存在
db_dir = Path(__file__).parent / "db"
db_dir.mkdir(exist_ok=True)

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_dir}/app.db")

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    """FastAPI 依赖注入：获取数据库会话"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """初始化数据库，创建所有表"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _migrate_sqlite(conn)


async def _migrate_sqlite(conn):
    """补齐旧 SQLite 数据库缺失的轻量字段。"""
    if not DATABASE_URL.startswith("sqlite"):
        return

    result = await conn.execute(text("PRAGMA table_info(edit_sessions)"))
    session_columns = {row[1] for row in result.fetchall()}

    if "user_id" not in session_columns:
        await conn.execute(text("ALTER TABLE edit_sessions ADD COLUMN user_id INTEGER"))

    result = await conn.execute(text("PRAGMA table_info(edit_records)"))
    columns = {row[1] for row in result.fetchall()}

    if "edit_metadata" not in columns:
        await conn.execute(text("ALTER TABLE edit_records ADD COLUMN edit_metadata TEXT"))

    if "user_id" not in columns:
        await conn.execute(text("ALTER TABLE edit_records ADD COLUMN user_id INTEGER"))
