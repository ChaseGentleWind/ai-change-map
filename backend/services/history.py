"""历史会话组装与清理服务。"""
import json
from typing import Optional

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import EditRecord, EditSession
from models.schemas import RecordSchema, SessionListItemSchema, SessionSchema
from services.storage import delete_file


async def build_session_list_item(
    db: AsyncSession,
    session: EditSession,
    user_id: Optional[int] = None,
) -> SessionListItemSchema:
    """组装历史会话列表项。"""
    record_filters = [EditRecord.session_id == session.id]
    if user_id is not None:
        record_filters.append(EditRecord.user_id == user_id)

    record_count_result = await db.execute(
        select(func.count(EditRecord.id)).where(*record_filters)
    )
    record_count = record_count_result.scalar() or 0

    last_record_result = await db.execute(
        select(EditRecord)
        .where(*record_filters)
        .order_by(desc(EditRecord.created_at))
        .limit(1)
    )
    last_record = last_record_result.scalar_one_or_none()
    last_result_url = None
    if last_record and last_record.result_urls:
        result_urls = json.loads(last_record.result_urls)
        if result_urls:
            last_result_url = result_urls[0]

    return SessionListItemSchema(
        id=session.id,
        title=session.title,
        original_url=session.original_url,
        last_result_url=last_result_url,
        record_count=record_count,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


async def build_session_schema(
    db: AsyncSession,
    session: EditSession,
    user_id: Optional[int] = None,
) -> SessionSchema:
    """组装单个历史会话详情。"""
    record_filters = [EditRecord.session_id == session.id]
    if user_id is not None:
        record_filters.append(EditRecord.user_id == user_id)

    records_result = await db.execute(
        select(EditRecord)
        .where(*record_filters)
        .order_by(EditRecord.created_at)
    )
    records = records_result.scalars().all()

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
            created_at=record.created_at,
        ))

    return SessionSchema(
        id=session.id,
        title=session.title,
        original_url=session.original_url,
        records=record_schemas,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


async def delete_session_with_files(
    db: AsyncSession,
    session: EditSession,
    user_id: Optional[int] = None,
) -> None:
    """删除会话及其所有记录和关联文件。"""
    record_filters = [EditRecord.session_id == session.id]
    if user_id is not None:
        record_filters.append(EditRecord.user_id == user_id)

    records_result = await db.execute(select(EditRecord).where(*record_filters))
    records = records_result.scalars().all()

    for record in records:
        delete_file(record.main_image_url)

        if record.reference_urls:
            ref_urls = json.loads(record.reference_urls)
            for url in ref_urls:
                delete_file(url)

        if record.mask_url:
            delete_file(record.mask_url)

        if record.result_urls:
            result_urls = json.loads(record.result_urls)
            for url in result_urls:
                delete_file(url)

        await db.delete(record)

    delete_file(session.original_url)
    await db.delete(session)
