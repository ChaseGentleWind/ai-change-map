"""历史记录接口"""
import json
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from typing import List

from auth import get_current_user
from database import get_db
from models.database import EditSession, EditRecord, User
from models.schemas import (
    SessionListSchema,
    SessionListItemSchema,
    SessionSchema,
    RecordSchema
)
from services.storage import delete_file

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

    # 构建响应
    items = []
    for session in sessions:
        # 查询该会话的记录数
        record_count_result = await db.execute(
            select(func.count(EditRecord.id))
            .where(EditRecord.session_id == session.id, EditRecord.user_id == current_user.id)
        )
        record_count = record_count_result.scalar()

        # 查询最后一条记录的结果图
        last_record_result = await db.execute(
            select(EditRecord)
            .where(EditRecord.session_id == session.id, EditRecord.user_id == current_user.id)
            .order_by(desc(EditRecord.created_at))
            .limit(1)
        )
        last_record = last_record_result.scalar_one_or_none()
        last_result_url = None
        if last_record and last_record.result_urls:
            result_urls = json.loads(last_record.result_urls)
            if result_urls:
                last_result_url = result_urls[0]

        items.append(SessionListItemSchema(
            id=session.id,
            title=session.title,
            original_url=session.original_url,
            last_result_url=last_result_url,
            record_count=record_count,
            created_at=session.created_at,
            updated_at=session.updated_at
        ))

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

    # 查询该会话的所有记录
    records_result = await db.execute(
        select(EditRecord)
        .where(EditRecord.session_id == session_id, EditRecord.user_id == current_user.id)
        .order_by(EditRecord.created_at)
    )
    records = records_result.scalars().all()

    # 转换为 schema
    record_schemas = []
    for record in records:
        ref_urls = json.loads(record.reference_urls) if record.reference_urls else None
        result_urls = json.loads(record.result_urls) if record.result_urls else None
        edit_metadata = json.loads(record.edit_metadata) if record.edit_metadata else None

        record_schemas.append(RecordSchema(
            id=record.id,
            session_id=record.session_id,
            parent_id=record.parent_id,
            main_image_url=record.main_image_url,
            reference_urls=ref_urls,
            mask_url=record.mask_url,
            edit_metadata=edit_metadata,
            instruction=record.instruction,
            task_type=record.task_type,
            provider=record.provider,
            model=record.model,
            fallback_used=record.fallback_used,
            result_urls=result_urls,
            status=record.status,
            error_message=record.error_message,
            cost=record.cost,
            duration_ms=record.duration_ms,
            created_at=record.created_at
        ))

    return SessionSchema(
        id=session.id,
        title=session.title,
        original_url=session.original_url,
        records=record_schemas,
        created_at=session.created_at,
        updated_at=session.updated_at
    )


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

    # 查询所有记录
    records_result = await db.execute(
        select(EditRecord).where(EditRecord.session_id == session_id, EditRecord.user_id == current_user.id)
    )
    records = records_result.scalars().all()

    # 删除关联文件
    for record in records:
        # 删除主图
        delete_file(record.main_image_url)

        # 删除参考图
        if record.reference_urls:
            ref_urls = json.loads(record.reference_urls)
            for url in ref_urls:
                delete_file(url)

        if record.mask_url:
            delete_file(record.mask_url)

        # 删除结果图
        if record.result_urls:
            result_urls = json.loads(record.result_urls)
            for url in result_urls:
                delete_file(url)

        # 删除记录
        await db.delete(record)

    # 删除会话原图
    delete_file(session.original_url)

    # 删除会话
    await db.delete(session)
    await db.commit()

    return {"message": "会话已删除"}
