"""编辑接口路由"""
import uuid
import json
import time
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional

from database import get_db
from models.database import EditSession, EditRecord
from models.schemas import EditResponseSchema
from providers import get_provider, EditRequest, TaskRouter
from services.storage import save_upload, save_outputs, get_file_bytes
from config import PROVIDERS_CONFIG

router = APIRouter(prefix="/api", tags=["编辑"])


@router.post("/edit", response_model=EditResponseSchema)
async def edit_image(
    main_image: UploadFile = File(..., description="主图"),
    instruction: str = Form(..., description="编辑指令"),
    session_id: Optional[str] = Form(None, description="会话 ID"),
    parent_id: Optional[int] = Form(None, description="父记录 ID"),
    parent_result_index: int = Form(0, description="父记录结果图索引"),
    provider: Optional[str] = Form(None, description="手动指定 provider"),
    output_count: int = Form(1, description="生成数量"),
    reference_images: List[UploadFile] = File(default=[], description="参考图"),
    db: AsyncSession = Depends(get_db)
):
    """
    图像编辑接口

    - 如果不传 session_id，创建新会话
    - 如果传 parent_id，则基于父记录的结果图继续编辑
    - 支持手动指定 provider，否则走智能路由
    """
    start_time = time.time()

    # 读取主图
    main_image_bytes = await main_image.read()

    # 读取参考图
    reference_bytes = []
    for ref_img in reference_images:
        reference_bytes.append(await ref_img.read())

    # 如果有 parent_id，从数据库读取父记录的结果图作为主图
    if parent_id:
        result = await db.execute(select(EditRecord).where(EditRecord.id == parent_id))
        parent_record = result.scalar_one_or_none()
        if not parent_record:
            raise HTTPException(404, "父记录不存在")

        # 使用用户选择的父记录结果图作为主图
        result_urls = json.loads(parent_record.result_urls or "[]")
        if not result_urls:
            raise HTTPException(404, "父记录没有结果图")
        if parent_result_index < 0 or parent_result_index >= len(result_urls):
            raise HTTPException(400, "父记录结果图索引超出范围")

        selected_parent_url = result_urls[parent_result_index]
        main_image_bytes = get_file_bytes(selected_parent_url)
        if not main_image_bytes:
            raise HTTPException(404, "父记录的结果图不存在")

    # 保存上传的图片
    _, main_url = save_upload(main_image_bytes)
    ref_urls = [save_upload(ref, ".jpg")[1] for ref in reference_bytes]

    # 创建或获取会话
    if not session_id:
        session_id = str(uuid.uuid4())
        # 创建新会话
        session = EditSession(
            id=session_id,
            title=instruction[:20],  # 取前20字作为标题
            original_url=main_url
        )
        db.add(session)
        await db.commit()
    else:
        # 验证会话存在
        result = await db.execute(select(EditSession).where(EditSession.id == session_id))
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(404, "会话不存在")

    # 智能路由选择 provider
    router_instance = TaskRouter(PROVIDERS_CONFIG["routing"])
    selected_provider, task_type = router_instance.select_provider(
        instruction=instruction,
        has_reference_images=len(reference_bytes) > 0,
        has_parent=parent_id is not None,
        manual_provider=provider
    )

    # 获取 provider 配置
    provider_config = PROVIDERS_CONFIG["providers"].get(selected_provider)
    if not provider_config or not provider_config.get("enabled"):
        raise HTTPException(400, f"Provider '{selected_provider}' 不可用")

    # 构建编辑请求
    edit_request = EditRequest(
        main_image=main_image_bytes,
        instruction=instruction,
        reference_images=reference_bytes,
        output_count=output_count
    )

    # 如果是迭代编辑，加载历史上下文（最多 10 轮）
    if parent_id:
        # TODO: 加载历史对话上下文
        pass

    # 调用 provider
    fallback_used = None
    try:
        provider_instance = get_provider(selected_provider, provider_config)
        response = await provider_instance.edit(edit_request)
    except Exception as e:
        # 尝试 fallback
        fallback_config = PROVIDERS_CONFIG.get("fallback", {})
        if fallback_config.get("enabled"):
            fallback_chain = fallback_config.get("chain", {}).get(selected_provider, [])
            if fallback_chain:
                fallback_provider = fallback_chain[0]
                fallback_provider_config = PROVIDERS_CONFIG["providers"].get(fallback_provider)
                if fallback_provider_config and fallback_provider_config.get("enabled"):
                    try:
                        fallback_instance = get_provider(fallback_provider, fallback_provider_config)
                        response = await fallback_instance.edit(edit_request)
                        fallback_used = selected_provider
                        selected_provider = fallback_provider
                    except Exception as fallback_error:
                        raise HTTPException(500, f"编辑失败: {str(e)}, Fallback 也失败: {str(fallback_error)}")
                else:
                    raise HTTPException(500, f"编辑失败: {str(e)}")
            else:
                raise HTTPException(500, f"编辑失败: {str(e)}")
        else:
            raise HTTPException(500, f"编辑失败: {str(e)}")

    # 保存结果图
    result_urls = save_outputs(response.images, prefix=f"{session_id[:8]}")

    # 计算耗时
    duration_ms = int((time.time() - start_time) * 1000)

    # 估算成本（简化版，实际应根据 token 计算）
    cost = response.usage.total_tokens * 0.00003 if response.usage.total_tokens > 0 else None

    # 写入数据库
    record = EditRecord(
        session_id=session_id,
        parent_id=parent_id,
        main_image_url=main_url,
        reference_urls=json.dumps(ref_urls) if ref_urls else None,
        instruction=instruction,
        task_type=task_type,
        provider=selected_provider,
        model=response.model,
        fallback_used=fallback_used,
        result_urls=json.dumps(result_urls),
        status="completed",
        token_usage=json.dumps({
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "total_tokens": response.usage.total_tokens
        }),
        cost=cost,
        duration_ms=duration_ms
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)

    return EditResponseSchema(
        record_id=record.id,
        session_id=session_id,
        provider=selected_provider,
        model=response.model,
        task_type=task_type,
        fallback_used=fallback_used,
        results=result_urls,
        usage={
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "total_tokens": response.usage.total_tokens
        },
        cost=cost,
        duration_ms=duration_ms
    )
