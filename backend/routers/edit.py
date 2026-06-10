"""编辑接口路由"""
import uuid
import json
import time
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional

from auth import get_current_user
from database import get_db
from models.database import EditSession, EditRecord, User
from models.schemas import EditResponseSchema
from providers import get_provider, EditRequest, EditResponse, TaskRouter, TokenUsage
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
    task_mode: str = Form("general", description="任务模式"),
    edit_metadata: Optional[str] = Form(None, description="前端编辑状态 JSON"),
    reference_images: List[UploadFile] = File(default=[], description="参考图"),
    mask_image: Optional[UploadFile] = File(None, description="局部编辑 mask"),
    current_user: User = Depends(get_current_user),
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

    mask_bytes = await mask_image.read() if mask_image else None
    task_mode = _normalize_task_mode(task_mode)
    edit_metadata = _normalize_edit_metadata(edit_metadata, task_mode)
    enhanced_instruction = _build_instruction(task_mode, instruction, bool(mask_bytes))

    # 如果有 parent_id，从数据库读取父记录的结果图作为主图
    if parent_id and task_mode != "text_layer":
        result = await db.execute(
            select(EditRecord).where(
                EditRecord.id == parent_id,
                EditRecord.user_id == current_user.id,
            )
        )
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
    elif parent_id:
        result = await db.execute(
            select(EditRecord).where(
                EditRecord.id == parent_id,
                EditRecord.user_id == current_user.id,
            )
        )
        if not result.scalar_one_or_none():
            raise HTTPException(404, "父记录不存在")

    # 保存上传的图片
    _, main_url = save_upload(main_image_bytes)
    ref_urls = [save_upload(ref, ".jpg")[1] for ref in reference_bytes]
    mask_url = save_upload(mask_bytes, ".png")[1] if mask_bytes else None

    # 创建或获取会话
    if not session_id:
        session_id = str(uuid.uuid4())
        # 创建新会话
        session = EditSession(
            id=session_id,
            user_id=current_user.id,
            title=instruction[:20],  # 取前20字作为标题
            original_url=main_url
        )
        db.add(session)
        await db.commit()
    else:
        # 验证会话存在
        result = await db.execute(
            select(EditSession).where(
                EditSession.id == session_id,
                EditSession.user_id == current_user.id,
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(404, "会话不存在")

    # 智能路由选择 provider
    router_instance = TaskRouter(PROVIDERS_CONFIG["routing"])
    selected_provider, task_type = router_instance.select_provider(
        instruction=enhanced_instruction,
        has_reference_images=len(reference_bytes) > 0,
        has_parent=parent_id is not None,
        manual_provider=provider
    )

    if task_mode != "general":
        task_type = task_mode

    # 获取 provider 配置
    provider_config = PROVIDERS_CONFIG["providers"].get(selected_provider)
    if task_mode != "text_layer" and (not provider_config or not provider_config.get("enabled")):
        raise HTTPException(400, f"Provider '{selected_provider}' 不可用")

    # 构建编辑请求
    edit_request = EditRequest(
        main_image=main_image_bytes,
        instruction=enhanced_instruction,
        reference_images=reference_bytes,
        mask=mask_bytes,
        output_count=output_count
    )

    # 如果是迭代编辑，加载历史上下文（最多 10 轮）
    if parent_id:
        # TODO: 加载历史对话上下文
        pass

    # 调用 provider
    fallback_used = None
    if task_mode == "text_layer":
        response = _local_text_layer_response(main_image_bytes)
        selected_provider = "local"
    else:
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

    # 按用户选择的生成数量保存结果，避免兼容接口额外返回候选图导致前端多显示。
    result_images = response.images[:output_count]
    if not result_images:
        raise HTTPException(500, "模型未返回可用图片")

    # 保存结果图
    result_urls = save_outputs(result_images, prefix=f"{session_id[:8]}")

    # 计算耗时
    duration_ms = int((time.time() - start_time) * 1000)

    # 估算成本（简化版，实际应根据 token 计算）
    cost = response.usage.total_tokens * 0.00003 if response.usage.total_tokens > 0 else None

    # 写入数据库
    record = EditRecord(
        session_id=session_id,
        user_id=current_user.id,
        parent_id=parent_id,
        main_image_url=main_url,
        reference_urls=json.dumps(ref_urls) if ref_urls else None,
        mask_url=mask_url,
        edit_metadata=edit_metadata,
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


def _normalize_task_mode(task_mode: str) -> str:
    """校验任务模式，避免前端传入未支持的分支。"""
    allowed_modes = {"general", "local_edit", "text_layer"}
    if task_mode not in allowed_modes:
        raise HTTPException(400, "不支持的任务模式")
    return task_mode


def _normalize_edit_metadata(edit_metadata: Optional[str], task_mode: str) -> str:
    """校验并补齐前端编辑状态。"""
    if not edit_metadata:
        return json.dumps({"task_mode": task_mode}, ensure_ascii=False)

    try:
        metadata = json.loads(edit_metadata)
    except json.JSONDecodeError:
        raise HTTPException(400, "edit_metadata 必须是合法 JSON")

    if not isinstance(metadata, dict):
        raise HTTPException(400, "edit_metadata 必须是 JSON 对象")

    metadata["task_mode"] = task_mode
    return json.dumps(metadata, ensure_ascii=False)


def _build_instruction(task_mode: str, instruction: str, has_mask: bool) -> str:
    """根据任务模式增强提示词。"""
    if task_mode == "local_edit" and has_mask:
        return (
            f"{instruction}\n\n"
            "请只修改遮罩图中白色区域对应的内容，遮罩黑色区域必须保持不变。"
            "不要改变未选区的商品主体、背景、文字、构图、透视、光照和颜色。"
        )
    return instruction


def _local_text_layer_response(image_bytes: bytes) -> EditResponse:
    """文字图层已在前端合成，后端只保存合成结果。"""
    return EditResponse(
        images=[image_bytes],
        usage=TokenUsage(),
        provider="local",
        model="canvas-text-layer",
        raw_response={"local": True},
    )
