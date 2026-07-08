"""编辑接口路由 — 只负责参数解析与校验，业务逻辑委托给 EditService。"""
import json
from io import BytesIO
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError
from sqlalchemy.ext.asyncio import AsyncSession

from auth import get_current_user
from database import get_db
from models.database import User
from models.schemas import EditResponseSchema
from services.edit_service import EditService

# 上传限制
_MAX_IMAGE_SIZE = 20 * 1024 * 1024  # 20 MB
_MAX_TOTAL_IMAGE_SIZE = 20 * 1024 * 1024  # 20 MB
_ALLOWED_MIME_PREFIXES = ("image/jpeg", "image/png", "image/webp", "image/gif")
_IMAGE_SUFFIX_BY_FORMAT = {
    "JPEG": ".jpg",
    "PNG": ".png",
    "WEBP": ".webp",
    "GIF": ".gif",
}


async def _read_image(upload: UploadFile, field_name: str) -> tuple[bytes, str]:
    """读取上传图片并校验 MIME 类型、大小与真实图片格式。"""
    content_type = upload.content_type or ""
    if not any(content_type.startswith(p) for p in _ALLOWED_MIME_PREFIXES):
        raise HTTPException(415, f"{field_name} 必须是图片文件（jpeg/png/webp/gif），收到 {content_type!r}")
    data = await upload.read()
    if len(data) > _MAX_IMAGE_SIZE:
        raise HTTPException(413, f"{field_name} 超过 20 MB 限制")
    try:
        with Image.open(BytesIO(data)) as image:
            image.verify()
            suffix = _IMAGE_SUFFIX_BY_FORMAT.get(image.format or "")
    except (UnidentifiedImageError, OSError, ValueError):
        raise HTTPException(415, f"{field_name} 不是有效图片文件")
    if not suffix:
        raise HTTPException(415, f"{field_name} 图片格式不受支持")
    return data, suffix


def _validate_total_image_size(images: List[Optional[bytes]]) -> None:
    """校验一次请求中所有输入图片的总大小。"""
    total_size = sum(len(image) for image in images if image)
    if total_size > _MAX_TOTAL_IMAGE_SIZE:
        raise HTTPException(413, "所有输入图片总大小超过 20 MB 限制")


def _normalize_task_mode(task_mode: str) -> str:
    allowed = {"general", "local_edit", "text_layer"}
    if task_mode not in allowed:
        raise HTTPException(400, "不支持的任务模式")
    return task_mode


def _normalize_output_resolution(output_resolution: Optional[str]) -> Optional[str]:
    if not output_resolution or output_resolution == "auto":
        return None
    value = output_resolution.lower()
    if value not in {"1k", "2k", "4k"}:
        raise HTTPException(400, "不支持的输出分辨率")
    return value


def _normalize_edit_metadata(edit_metadata: Optional[str], task_mode: str) -> str:
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
    if task_mode == "local_edit" and has_mask:
        return (
            f"{instruction}\n\n"
            "请只修改遮罩图中白色区域对应的内容，遮罩黑色区域必须保持不变。"
            "不要改变未选区的商品主体、背景、文字、构图、透视、光照和颜色。"
        )
    return instruction


router = APIRouter(prefix="/api", tags=["编辑"])


@router.post("/edit", response_model=EditResponseSchema)
async def edit_image(
    main_image: UploadFile = File(..., description="主图"),
    instruction: str = Form(..., description="编辑指令"),
    session_id: Optional[str] = Form(None, description="会话 ID"),
    parent_id: Optional[int] = Form(None, description="父记录 ID"),
    parent_result_index: int = Form(0, description="父记录结果图索引"),
    provider: Optional[str] = Form(None, description="手动指定 provider"),
    output_count: int = Form(1, ge=1, description="生成数量"),
    output_resolution: Optional[str] = Form(None, description="输出分辨率档位：1k/2k/4k"),
    task_mode: str = Form("general", description="任务模式"),
    edit_metadata: Optional[str] = Form(None, description="前端编辑状态 JSON"),
    reference_images: List[UploadFile] = File(default=[], description="参考图"),
    mask_image: Optional[UploadFile] = File(None, description="局部编辑 mask"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # 读取并校验所有上传文件
    main_image_bytes, main_image_suffix = await _read_image(main_image, "main_image")
    reference_items = [
        await _read_image(ref, f"reference_images[{i}]")
        for i, ref in enumerate(reference_images)
    ]
    reference_bytes = [item[0] for item in reference_items]
    reference_suffixes = [item[1] for item in reference_items]
    mask_item = await _read_image(mask_image, "mask_image") if mask_image else None
    mask_bytes = mask_item[0] if mask_item else None
    mask_suffix = mask_item[1] if mask_item else None
    _validate_total_image_size([main_image_bytes, *reference_bytes, mask_bytes])

    # 参数归一化
    task_mode = _normalize_task_mode(task_mode)
    output_resolution = _normalize_output_resolution(output_resolution)
    edit_metadata_str = _normalize_edit_metadata(edit_metadata, task_mode)
    enhanced_instruction = _build_instruction(task_mode, instruction, bool(mask_bytes))

    return await EditService(db).run(
        user=current_user,
        main_image_bytes=main_image_bytes,
        main_image_suffix=main_image_suffix,
        reference_bytes=reference_bytes,
        reference_suffixes=reference_suffixes,
        mask_bytes=mask_bytes,
        mask_suffix=mask_suffix,
        instruction=instruction,
        session_id=session_id,
        parent_id=parent_id,
        parent_result_index=parent_result_index,
        manual_provider=provider,
        output_count=output_count,
        output_resolution=output_resolution,
        task_mode=task_mode,
        edit_metadata=edit_metadata_str,
        enhanced_instruction=enhanced_instruction,
    )
