"""管理员接口。"""
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import get_current_admin_user, is_admin_user, validate_phone, validate_username
from database import get_db
from models.database import EditRecord, EditSession, User
from models.schemas import (
    AdminSessionDetailSchema,
    AdminUpdateUserRequestSchema,
    AdminUserDetailSchema,
    AdminUserHistorySchema,
    AdminUserListSchema,
)
from services.history import build_session_list_item, build_session_schema, delete_session_with_files

router = APIRouter(prefix="/api/admin", tags=["管理员"])


@router.get("/users", response_model=AdminUserListSchema)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: Optional[str] = Query(None, max_length=50),
    _: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """分页查看所有用户。"""
    filters = _user_search_filters(q)
    total_result = await db.execute(select(func.count(User.id)).where(*filters))
    total = total_result.scalar() or 0

    offset = (page - 1) * page_size
    result = await db.execute(
        select(User)
        .where(*filters)
        .order_by(desc(User.created_at), desc(User.id))
        .offset(offset)
        .limit(page_size)
    )
    users = result.scalars().all()

    # 批量拉取统计数据，整页 2 条 SQL，消除 N+1
    batch_stats = await _batch_user_stats(db, [u.id for u in users])
    items = [
        AdminUserDetailSchema(
            id=u.id,
            username=u.username,
            phone=u.phone,
            is_active=u.is_active,
            is_admin=is_admin_user(u),
            session_count=batch_stats[u.id]["session_count"],
            record_count=batch_stats[u.id]["record_count"],
            last_active_at=batch_stats[u.id]["last_active_at"],
            created_at=u.created_at,
        )
        for u in users
    ]

    return AdminUserListSchema(total=total, page=page, page_size=page_size, items=items)


@router.get("/users/{user_id}", response_model=AdminUserDetailSchema)
async def get_user_detail(
    user_id: int,
    _: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """查看单个用户详情。"""
    user = await _get_user_or_404(db, user_id)
    return await _build_admin_user_detail(db, user)


@router.put("/users/{user_id}", response_model=AdminUserDetailSchema)
async def update_user(
    user_id: int,
    payload: AdminUpdateUserRequestSchema,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """管理员修改用户基础信息。"""
    user = await _get_user_or_404(db, user_id)
    username = payload.username.strip()
    phone = payload.phone.strip()

    validate_username(username)
    validate_phone(phone)

    if user.id == current_admin.id and not payload.is_active:
        raise HTTPException(400, "不能禁用当前管理员账号")

    exists_result = await db.execute(
        select(User).where(
            User.id != user.id,
            or_(User.username == username, User.phone == phone),
        )
    )
    exists = exists_result.scalar_one_or_none()
    if exists:
        if exists.username == username:
            raise HTTPException(409, "用户名已被使用")
        raise HTTPException(409, "手机号已被使用")

    user.username = username
    user.phone = phone
    user.is_active = payload.is_active
    await db.commit()
    await db.refresh(user)
    return await _build_admin_user_detail(db, user)


@router.get("/users/{user_id}/history", response_model=AdminUserHistorySchema)
async def get_user_history(
    user_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """查看指定用户的历史会话。"""
    user = await _get_user_or_404(db, user_id)

    total_result = await db.execute(
        select(func.count(EditSession.id)).where(EditSession.user_id == user.id)
    )
    total = total_result.scalar() or 0

    offset = (page - 1) * page_size
    result = await db.execute(
        select(EditSession)
        .where(EditSession.user_id == user.id)
        .order_by(desc(EditSession.updated_at))
        .offset(offset)
        .limit(page_size)
    )
    sessions = result.scalars().all()
    items = [await build_session_list_item(db, session, user.id) for session in sessions]

    return AdminUserHistorySchema(
        user=await _build_admin_user_detail(db, user),
        total=total,
        page=page,
        page_size=page_size,
        items=items,
    )


@router.get("/history/{session_id}", response_model=AdminSessionDetailSchema)
async def get_admin_session(
    session_id: str,
    _: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """管理员查看任意会话详情。"""
    session = await _get_session_or_404(db, session_id)
    user = await _get_user_or_404(db, session.user_id)
    return AdminSessionDetailSchema(
        user=await _build_admin_user_detail(db, user),
        session=await build_session_schema(db, session, user.id),
    )


@router.delete("/history/{session_id}")
async def delete_admin_session(
    session_id: str,
    _: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """管理员删除任意用户的历史会话。"""
    session = await _get_session_or_404(db, session_id)
    await delete_session_with_files(db, session, session.user_id)
    await db.commit()
    return {"message": "会话已删除"}


def _user_search_filters(q: Optional[str]):
    """构造用户搜索条件。"""
    keyword = q.strip() if q else ""
    if not keyword:
        return []
    return [or_(User.username.contains(keyword), User.phone.contains(keyword))]


async def _get_user_or_404(db: AsyncSession, user_id: Optional[int]) -> User:
    """获取用户，不存在则返回 404。"""
    if user_id is None:
        raise HTTPException(404, "用户不存在")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "用户不存在")
    return user


async def _get_session_or_404(db: AsyncSession, session_id: str) -> EditSession:
    """获取会话，不存在则返回 404。"""
    result = await db.execute(select(EditSession).where(EditSession.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "会话不存在")
    return session


async def _build_admin_user_detail(db: AsyncSession, user: User) -> AdminUserDetailSchema:
    """组装管理员用户详情。"""
    session_count_result = await db.execute(
        select(func.count(EditSession.id)).where(EditSession.user_id == user.id)
    )
    record_count_result = await db.execute(
        select(func.count(EditRecord.id)).where(EditRecord.user_id == user.id)
    )
    last_session_result = await db.execute(
        select(func.max(EditSession.updated_at)).where(EditSession.user_id == user.id)
    )
    last_record_result = await db.execute(
        select(func.max(EditRecord.created_at)).where(EditRecord.user_id == user.id)
    )

    last_active_at = _max_datetime(
        last_session_result.scalar_one_or_none(),
        last_record_result.scalar_one_or_none(),
    )

    return AdminUserDetailSchema(
        id=user.id,
        username=user.username,
        phone=user.phone,
        is_active=user.is_active,
        is_admin=is_admin_user(user),
        session_count=session_count_result.scalar() or 0,
        record_count=record_count_result.scalar() or 0,
        last_active_at=last_active_at,
        created_at=user.created_at,
    )


async def _batch_user_stats(db: AsyncSession, user_ids: List[int]) -> Dict[int, dict]:
    """批量查询一组用户的会话数、记录数和最近活跃时间，只发 2 条 SQL。"""
    if not user_ids:
        return {}

    session_rows = await db.execute(
        select(
            EditSession.user_id,
            func.count(EditSession.id).label("session_count"),
            func.max(EditSession.updated_at).label("last_session_at"),
        )
        .where(EditSession.user_id.in_(user_ids))
        .group_by(EditSession.user_id)
    )
    record_rows = await db.execute(
        select(
            EditRecord.user_id,
            func.count(EditRecord.id).label("record_count"),
            func.max(EditRecord.created_at).label("last_record_at"),
        )
        .where(EditRecord.user_id.in_(user_ids))
        .group_by(EditRecord.user_id)
    )

    stats: Dict[int, dict] = {
        uid: {"session_count": 0, "record_count": 0, "last_active_at": None}
        for uid in user_ids
    }
    for row in session_rows.all():
        stats[row.user_id]["session_count"] = row.session_count
        stats[row.user_id]["last_active_at"] = row.last_session_at
    for row in record_rows.all():
        stats[row.user_id]["record_count"] = row.record_count
        stats[row.user_id]["last_active_at"] = _max_datetime(
            stats[row.user_id]["last_active_at"], row.last_record_at
        )
    return stats


def _max_datetime(*values: Optional[datetime]) -> Optional[datetime]:
    """返回非空时间中的最大值。"""
    candidates = [value for value in values if value is not None]
    if not candidates:
        return None
    return max(candidates)
