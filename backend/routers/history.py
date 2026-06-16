from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from auth import get_current_user
from database import get_db
from models.database import EditSession, EditRecord, User
from models.schemas import (
    SessionListSchema,
    SessionSchema,
)
from services.history import build_session_list_item, build_session_schema, delete_session_with_files

router = APIRouter(prefix="/api", tags=["历史记录"])


@router.get("/history", response_model=SessionListSchema)
async def list_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取会话列表（分页）"""
    # 查询总数
    count_result = await db.execute(
        select(func.count(EditSession.id)).where(EditSession.user_id == current_user.id)
    )
    total = count_result.scalar()

    # 查询会话列表
    offset = (page - 1) * page_size
    result = await db.execute(
        select(EditSession)
        .where(EditSession.user_id == current_user.id)
        .order_by(desc(EditSession.updated_at))
        .offset(offset)
        .limit(page_size)
    )
    sessions = result.scalars().all()

    items = [await build_session_list_item(db, session, current_user.id) for session in sessions]

    return SessionListSchema(
        total=total,
        page=page,
        page_size=page_size,
        items=items
    )


@router.get("/history/{session_id}", response_model=SessionSchema)
async def get_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取单个会话的详细信息（含所有编辑记录）"""
    # 查询会话
    result = await db.execute(
        select(EditSession).where(
            EditSession.id == session_id,
            EditSession.user_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "会话不存在")

    return await build_session_schema(db, session, current_user.id)


@router.delete("/history/{session_id}")
async def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除会话及其所有记录和关联文件"""
    # 查询会话
    result = await db.execute(
        select(EditSession).where(
            EditSession.id == session_id,
            EditSession.user_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "会话不存在")

    await delete_session_with_files(db, session, current_user.id)
    await db.commit()

    return {"message": "会话已删除"}
