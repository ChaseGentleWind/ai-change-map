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

    await _migrate_users_table(conn)

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


async def _migrate_users_table(conn):
    """兼容从邮箱账号切换到手机号账号的旧用户表。"""
    result = await conn.execute(text("PRAGMA table_info(users)"))
    rows = result.fetchall()
    if not rows:
        return

    columns = {row[1]: row for row in rows}
    email_is_required = "email" in columns and bool(columns["email"][3])
    needs_rebuild = "phone" not in columns or email_is_required
    if not needs_rebuild:
        return

    phone_select = "phone" if "phone" in columns else "NULL"
    email_select = "email" if "email" in columns else "NULL"

    await conn.execute(text("DROP TABLE IF EXISTS users_new"))
    await conn.execute(text("""
        CREATE TABLE users_new (
            id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            username VARCHAR(50) NOT NULL,
            email VARCHAR(255),
            phone VARCHAR(20),
            password_hash VARCHAR(255) NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """))
    await conn.execute(text(f"""
        INSERT INTO users_new (id, username, email, phone, password_hash, is_active, created_at)
        SELECT id, username, {email_select}, {phone_select}, password_hash, is_active, created_at
        FROM users
    """))
    await conn.execute(text("DROP TABLE users"))
    await conn.execute(text("ALTER TABLE users_new RENAME TO users"))
    await conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username ON users (username)"))
    await conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_phone ON users (phone)"))
    await conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email)"))
