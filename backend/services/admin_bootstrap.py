"""管理员账号启动引导。"""
from sqlalchemy import or_, select

from auth import get_password_hash, validate_phone, validate_username
from config import ADMIN_PASSWORD, ADMIN_PHONE, ADMIN_USERNAME
from database import AsyncSessionLocal
from models.database import User


def _validate_admin_password(password: str) -> None:
    """校验管理员密码复杂度：长度 ≥ 8，含大写字母，含数字。"""
    if len(password) < 8:
        raise RuntimeError("ADMIN_PASSWORD 至少需要 8 个字符")
    if not any(c.isupper() for c in password):
        raise RuntimeError("ADMIN_PASSWORD 必须包含至少一个大写字母")
    if not any(c.isdigit() for c in password):
        raise RuntimeError("ADMIN_PASSWORD 必须包含至少一个数字")


async def ensure_admin_account():
    """根据 .env 自动创建或同步管理员账号。"""
    if not (ADMIN_USERNAME and ADMIN_PHONE and ADMIN_PASSWORD):
        return

    validate_username(ADMIN_USERNAME)
    validate_phone(ADMIN_PHONE)
    _validate_admin_password(ADMIN_PASSWORD)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User).where(or_(User.username == ADMIN_USERNAME, User.phone == ADMIN_PHONE))
        )
        users = result.scalars().all()
        if len({user.id for user in users}) > 1:
            raise RuntimeError("ADMIN_USERNAME 和 ADMIN_PHONE 分别属于不同用户，请先清理数据库账号")

        user = users[0] if users else None
        if user:
            user.username = ADMIN_USERNAME
            user.phone = ADMIN_PHONE
            user.password_hash = get_password_hash(ADMIN_PASSWORD)
            user.is_active = True
        else:
            db.add(User(
                username=ADMIN_USERNAME,
                phone=ADMIN_PHONE,
                password_hash=get_password_hash(ADMIN_PASSWORD),
                is_active=True,
            ))

        await db.commit()
