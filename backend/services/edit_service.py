"""图像编辑核心服务：路由选择、历史上下文加载、fallback 链遍历、DB 写入。"""
import json
import time
import uuid
from typing import Dict, List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import PROVIDERS_CONFIG
from models.database import EditRecord, EditSession, User
from models.schemas import EditResponseSchema
from providers import EditRequest, EditResponse, TokenUsage, get_provider
from providers.router import TaskRouter
from services.storage import get_file_bytes, save_outputs, save_upload

_MAX_CONTEXT_TURNS: int = PROVIDERS_CONFIG.get("session", {}).get("max_context_turns", 10)


class EditService:
    """编辑业务逻辑层：路由 → 历史上下文 → provider 调用 → fallback → DB 写入。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def run(
        self,
        *,
        user: User,
        main_image_bytes: bytes,
        main_image_suffix: str,
        reference_bytes: List[bytes],
        reference_suffixes: List[str],
        mask_bytes: Optional[bytes],
        mask_suffix: Optional[str],
        instruction: str,
        session_id: Optional[str],
        parent_id: Optional[int],
        parent_result_index: int,
        manual_provider: Optional[str],
        output_count: int,
        output_resolution: Optional[str],
        task_mode: str,
        edit_metadata: str,
        enhanced_instruction: str,
    ) -> EditResponseSchema:
        start_time = time.time()

        # 1. 验证父记录所有权；非 text_layer 任务用父结果图替换主图
        main_image_bytes = await self._resolve_parent_image(
            user, parent_id, task_mode, parent_result_index, main_image_bytes
        )
        if parent_id and task_mode != "text_layer":
            main_image_suffix = ".png"

        # 2. 持久化上传文件
        _, main_url = save_upload(main_image_bytes, main_image_suffix)
        ref_urls = [
            save_upload(ref, suffix)[1]
            for ref, suffix in zip(reference_bytes, reference_suffixes)
        ]
        mask_url = save_upload(mask_bytes, mask_suffix or ".png")[1] if mask_bytes else None

        # 3. 创建或获取会话
        session = await self._get_or_create_session(user, session_id, main_url, instruction)

        # 4. 路由选择 provider
        router_instance = TaskRouter(PROVIDERS_CONFIG["routing"])
        selected_provider, task_type = router_instance.select_provider(
            instruction=enhanced_instruction,
            has_reference_images=bool(reference_bytes),
            has_parent=parent_id is not None,
            manual_provider=manual_provider,
        )
        if task_mode != "general":
            task_type = task_mode

        # 5. 验证 provider 可用（text_layer 在本地处理，跳过检查）
        provider_config = PROVIDERS_CONFIG["providers"].get(selected_provider)
        if task_mode != "text_layer" and (not provider_config or not provider_config.get("enabled")):
            raise HTTPException(400, f"Provider '{selected_provider}' 不可用")
        if task_mode != "text_layer":
            self._validate_provider_capabilities(
                selected_provider=selected_provider,
                provider_config=provider_config,
                task_mode=task_mode,
                reference_count=len(reference_bytes),
                has_mask=bool(mask_bytes),
                output_count=output_count,
            )

        # 6. 构建请求；迭代编辑时沿 parent_id 链注入历史上下文
        edit_request = EditRequest(
            main_image=main_image_bytes,
            instruction=enhanced_instruction,
            reference_images=reference_bytes,
            mask=mask_bytes,
            output_count=output_count,
            extra={"output_resolution": output_resolution} if output_resolution else {},
        )
        if parent_id:
            edit_request.history = await self._load_context(parent_id)

        # 7. 调用 provider（含 fallback 链遍历）
        response, selected_provider, fallback_used = await self._call_with_fallback(
            task_mode, edit_request, selected_provider, provider_config
        )

        # 8. 截断至 output_count 并保存结果图
        result_images = response.images[:output_count]
        if not result_images:
            raise HTTPException(500, "模型未返回可用图片")
        result_urls = save_outputs(result_images, prefix=session.id[:8])

        duration_ms = int((time.time() - start_time) * 1000)
        cost = response.usage.total_tokens * 0.00003 if response.usage.total_tokens > 0 else None

        # 9. 写入编辑记录
        record = EditRecord(
            session_id=session.id,
            user_id=user.id,
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
                "total_tokens": response.usage.total_tokens,
            }),
            cost=cost,
            duration_ms=duration_ms,
        )
        self.db.add(record)
        await self.db.commit()
        await self.db.refresh(record)

        return EditResponseSchema(
            record_id=record.id,
            session_id=session.id,
            provider=selected_provider,
            model=response.model,
            task_type=task_type,
            fallback_used=fallback_used,
            results=result_urls,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.total_tokens,
            },
            cost=cost,
            duration_ms=duration_ms,
        )

    # ──────────────────────────────────────────────────────────────
    # 私有辅助方法
    # ──────────────────────────────────────────────────────────────

    async def _resolve_parent_image(
        self,
        user: User,
        parent_id: Optional[int],
        task_mode: str,
        parent_result_index: int,
        current_image: bytes,
    ) -> bytes:
        """验证父记录存在且属于当前用户；text_layer 外的任务替换主图为父结果图。"""
        if not parent_id:
            return current_image

        result = await self.db.execute(
            select(EditRecord).where(
                EditRecord.id == parent_id,
                EditRecord.user_id == user.id,
            )
        )
        parent = result.scalar_one_or_none()
        if not parent:
            raise HTTPException(404, "父记录不存在")

        if task_mode == "text_layer":
            return current_image

        urls = json.loads(parent.result_urls or "[]")
        if not urls:
            raise HTTPException(404, "父记录没有结果图")
        if parent_result_index < 0 or parent_result_index >= len(urls):
            raise HTTPException(400, "父记录结果图索引超出范围")

        image_bytes = get_file_bytes(urls[parent_result_index])
        if not image_bytes:
            raise HTTPException(404, "父记录的结果图文件不存在")
        return image_bytes

    async def _get_or_create_session(
        self, user: User, session_id: Optional[str], main_url: str, instruction: str
    ) -> EditSession:
        if not session_id:
            session = EditSession(
                id=str(uuid.uuid4()),
                user_id=user.id,
                title=instruction[:20],
                original_url=main_url,
            )
            self.db.add(session)
            await self.db.commit()
            return session

        result = await self.db.execute(
            select(EditSession).where(
                EditSession.id == session_id,
                EditSession.user_id == user.id,
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(404, "会话不存在")
        return session

    async def _load_context(self, parent_id: int) -> List[Dict]:
        """
        沿 parent_id 链向上读取最多 _MAX_CONTEXT_TURNS 轮历史。
        每项：{"instruction": str, "result_image": bytes | None}
        返回按时序排列（最旧在前）。
        """
        turns: List[Dict] = []
        current_id: Optional[int] = parent_id

        while current_id is not None and len(turns) < _MAX_CONTEXT_TURNS:
            result = await self.db.execute(
                select(EditRecord).where(EditRecord.id == current_id)
            )
            record = result.scalar_one_or_none()
            if not record:
                break
            result_urls = json.loads(record.result_urls or "[]")
            turns.append({
                "instruction": record.instruction,
                "result_image": get_file_bytes(result_urls[0]) if result_urls else None,
            })
            current_id = record.parent_id

        turns.reverse()
        return turns

    def _validate_provider_capabilities(
        self,
        *,
        selected_provider: str,
        provider_config: dict,
        task_mode: str,
        reference_count: int,
        has_mask: bool,
        output_count: int,
    ) -> None:
        """按 provider 声明能力提前拒绝不支持的任务组合。"""
        if output_count < 1:
            raise HTTPException(400, "生成数量至少为 1")

        try:
            provider_instance = get_provider(selected_provider, provider_config)
        except KeyError as e:
            raise HTTPException(400, str(e))

        capabilities = provider_instance.capabilities()
        if output_count > capabilities.max_output_count:
            raise HTTPException(
                400,
                f"Provider '{selected_provider}' 单次最多生成 {capabilities.max_output_count} 张",
            )
        if reference_count > 0 and not capabilities.supports_multi_image:
            raise HTTPException(400, f"Provider '{selected_provider}' 不支持参考图")
        if has_mask and not capabilities.supports_mask:
            if selected_provider.startswith("openai") and task_mode == "local_edit":
                return
            raise HTTPException(400, f"Provider '{selected_provider}' 不支持局部 mask")

    async def _call_with_fallback(
        self,
        task_mode: str,
        edit_request: EditRequest,
        selected_provider: str,
        provider_config: Optional[dict],
    ) -> Tuple[EditResponse, str, Optional[str]]:
        """
        调用 provider。
        失败时按 fallback.chain 顺序逐个尝试，全部失败才抛 HTTP 500。
        """
        if task_mode == "text_layer":
            return (
                EditResponse(
                    images=[edit_request.main_image],
                    usage=TokenUsage(),
                    provider="local",
                    model="canvas-text-layer",
                    raw_response={"local": True},
                ),
                "local",
                None,
            )

        # 正常调用
        primary_error: Optional[Exception] = None
        try:
            instance = get_provider(selected_provider, provider_config)
            if edit_request.history:
                response = await instance.chat_edit(edit_request.history, edit_request)
            else:
                response = await instance.edit(edit_request)
            return response, selected_provider, None
        except Exception as e:
            primary_error = e

        # 遍历 fallback 链
        fallback_config = PROVIDERS_CONFIG.get("fallback", {})
        if not fallback_config.get("enabled"):
            raise HTTPException(500, f"编辑失败: {primary_error}")

        fallback_chain: List[str] = fallback_config.get("chain", {}).get(selected_provider, [])
        last_error: Exception = primary_error
        for fallback_name in fallback_chain:
            fb_config = PROVIDERS_CONFIG["providers"].get(fallback_name)
            if not fb_config or not fb_config.get("enabled"):
                continue
            try:
                fb_instance = get_provider(fallback_name, fb_config)
                if edit_request.history:
                    response = await fb_instance.chat_edit(edit_request.history, edit_request)
                else:
                    response = await fb_instance.edit(edit_request)
                return response, fallback_name, selected_provider
            except Exception as e:
                last_error = e

        raise HTTPException(500, f"编辑失败: {primary_error}，所有 Fallback 均失败: {last_error}")
