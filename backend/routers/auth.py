"""用户注册与登录接口。"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import (
    create_access_token,
    get_current_user,
    get_password_hash,
    is_admin_user,
    validate_phone,
    validate_username,
    verify_password,
)
from database import get_db
from models.database import User
from models.schemas import (
    AuthResponseSchema,
    LoginRequestSchema,
    RegisterRequestSchema,
    UpdatePasswordRequestSchema,
    UpdateProfileRequestSchema,
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
    phone = payload.phone.strip()

    validate_username(username)
    validate_phone(phone)

    exists_result = await db.execute(
        select(User).where(or_(User.username == username, User.phone == phone))
    )
    exists = exists_result.scalar_one_or_none()
    if exists:
        if exists.username == username:
            raise HTTPException(409, "用户名已被使用")
        raise HTTPException(409, "手机号已被使用")

    user = User(
        username=username,
        phone=phone,
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
    """用户名或手机号登录。"""
    account = payload.username_or_phone.strip()

    result = await db.execute(
        select(User).where(or_(User.username == account, User.phone == account))
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
    return _user_schema(current_user)


@router.put("/me/profile", response_model=UserSchema)
async def update_profile(
    payload: UpdateProfileRequestSchema,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """修改当前用户的用户名和手机号。"""
    username = payload.username.strip()
    phone = payload.phone.strip()

    validate_username(username)
    validate_phone(phone)

    exists_result = await db.execute(
        select(User).where(
            User.id != current_user.id,
            or_(User.username == username, User.phone == phone),
        )
    )
    exists = exists_result.scalar_one_or_none()
    if exists:
        if exists.username == username:
            raise HTTPException(409, "用户名已被使用")
        raise HTTPException(409, "手机号已被使用")

    current_user.username = username
    current_user.phone = phone
    await db.commit()
    await db.refresh(current_user)
    return _user_schema(current_user)


@router.put("/me/password")
async def update_password(
    payload: UpdatePasswordRequestSchema,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """修改当前用户密码，需要先校验当前密码。"""
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "当前密码不正确")

    current_user.password_hash = get_password_hash(payload.new_password)
    await db.commit()
    return {"message": "密码已更新"}


def _auth_response(user: User) -> AuthResponseSchema:
    """组装认证响应。"""
    return AuthResponseSchema(
        access_token=create_access_token(str(user.id)),
        token_type="bearer",
        user=_user_schema(user),
    )


def _user_schema(user: User) -> UserSchema:
    """组装带管理员标记的用户响应。"""
    return UserSchema(
        id=user.id,
        username=user.username,
        phone=user.phone,
        is_active=user.is_active,
        is_admin=is_admin_user(user),
        created_at=user.created_at,
    )

