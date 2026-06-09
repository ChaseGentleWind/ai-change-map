"""Gemini Provider 实现"""
import httpx
import base64
import json
from typing import List
from .base import ImageEditorProvider
from .schemas import EditRequest, EditResponse, Capabilities, TokenUsage
from .registry import register


@register("gemini")
class GeminiProvider(ImageEditorProvider):
    """Gemini 2.5 Flash Image Provider"""

    def capabilities(self) -> Capabilities:
        return Capabilities(
            supports_multi_image=True,
            supports_mask=True,
            supports_chat=True,
            max_input_size_mb=20,
            max_output_count=4
        )

    async def edit(self, request: EditRequest) -> EditResponse:
        """调用 Gemini API 进行图像编辑"""

        # 构建 contents 数组（Gemini 的输入格式）
        contents = []

        # 如果有历史对话，先加入历史
        if request.history:
            contents.extend(request.history)

        # 构建当前轮的 parts
        parts = []

        # 添加主图
        main_image_b64 = base64.b64encode(request.main_image).decode('utf-8')
        parts.append({
            "inline_data": {
                "mime_type": "image/jpeg",
                "data": main_image_b64
            }
        })

        # 添加参考图（如果有）
        for ref_img in request.reference_images:
            ref_b64 = base64.b64encode(ref_img).decode('utf-8')
            parts.append({
                "inline_data": {
                    "mime_type": "image/jpeg",
                    "data": ref_b64
                }
            })

        if request.mask:
            mask_b64 = base64.b64encode(request.mask).decode('utf-8')
            parts.append({
                "inline_data": {
                    "mime_type": "image/png",
                    "data": mask_b64
                }
            })

        # 添加文字指令
        parts.append({
            "text": request.instruction
        })

        # 当前轮的 content
        contents.append({
            "role": "user",
            "parts": parts
        })

        # 构建请求体
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": 0.4,
                "candidateCount": request.output_count
            }
        }

        # 调用 API
        url = f"{self.api_base}/models/{self.model}:generateContent"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            result = response.json()

        # 解析响应
        images = []
        candidates = result.get("candidates", [])

        for candidate in candidates:
            parts = candidate.get("content", {}).get("parts", [])
            for part in parts:
                if "inline_data" in part:
                    img_data = base64.b64decode(part["inline_data"]["data"])
                    images.append(img_data)

        # 提取 token 用量
        usage_metadata = result.get("usageMetadata", {})
        usage = TokenUsage(
            input_tokens=usage_metadata.get("promptTokenCount", 0),
            output_tokens=usage_metadata.get("candidatesTokenCount", 0),
            total_tokens=usage_metadata.get("totalTokenCount", 0)
        )

        return EditResponse(
            images=images,
            usage=usage,
            provider="gemini",
            model=self.model,
            raw_response=result
        )
