"""用户注册与登录接口。"""
import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import create_access_token, get_current_user, get_password_hash, verify_password
from database import get_db
from models.database import User
from models.schemas import (
    AuthResponseSchema,
    LoginRequestSchema,
    RegisterRequestSchema,
    UserSchema,
)

router = APIRouter(prefix="/api/auth", tags=["用户认证"])


@router.post("/register", response_model=AuthResponseSchema)
async def register(
    payload: RegisterRequestSchema,
    db: AsyncSession = Depends(get_db),
):
    """开放注册并返回登录态。"""
    username = payload.username.strip()
    email = payload.email.strip().lower()

    if not re.fullmatch(r"[A-Za-z0-9_-]{3,50}", username):
        raise HTTPException(400, "用户名只能包含字母、数字、下划线和短横线，长度 3-50 位")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(400, "邮箱格式不正确")

    exists_result = await db.execute(
        select(User).where(or_(User.username == username, User.email == email))
    )
    exists = exists_result.scalar_one_or_none()
    if exists:
        if exists.username == username:
            raise HTTPException(409, "用户名已被使用")
        raise HTTPException(409, "邮箱已被使用")

    user = User(
        username=username,
        email=email,
        password_hash=get_password_hash(payload.password),
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return _auth_response(user)


@router.post("/login", response_model=AuthResponseSchema)
async def login(
    payload: LoginRequestSchema,
    db: AsyncSession = Depends(get_db),
):
    """用户名或邮箱登录。"""
    account = payload.username_or_email.strip()
    account_lower = account.lower()

    result = await db.execute(
        select(User).where(or_(User.username == account, User.email == account_lower))
    )
    user = result.scalar_one_or_none()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "账号或密码不正确")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "账号已被禁用")

    return _auth_response(user)


@router.get("/me", response_model=UserSchema)
async def me(current_user: User = Depends(get_current_user)):
    """获取当前登录用户。"""
    return current_user


def _auth_response(user: User) -> AuthResponseSchema:
    """组装认证响应。"""
    return AuthResponseSchema(
        access_token=create_access_token(str(user.id)),
        token_type="bearer",
        user=user,
    )
