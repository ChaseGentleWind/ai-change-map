"""OpenAI-compatible Provider 实现"""
import base64
import re
from collections.abc import Mapping
from io import BytesIO

import httpx
from PIL import Image, UnidentifiedImageError

from .base import ImageEditorProvider
from .schemas import Capabilities, EditRequest, EditResponse, TokenUsage
from .registry import register

MAX_GPT_IMAGE_SIDE = 3840


def _detect_mime_type(image: bytes) -> str:
    """根据文件头粗略判断图片 MIME 类型。"""
    if image.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if image.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if image.startswith(b"RIFF") and image[8:12] == b"WEBP":
        return "image/webp"
    return "image/png"


def _to_data_url(image: bytes) -> str:
    """将图片字节转换为 OpenAI 兼容接口常用的 data URL。"""
    mime_type = _detect_mime_type(image)
    encoded = base64.b64encode(image).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


def _field(value, name: str):
    """兼容 dict 和 SDK 对象两种响应字段读取方式。"""
    if isinstance(value, Mapping):
        return value.get(name)
    return getattr(value, name, None)


def _resolve_output_size(image: bytes, configured_size: str | None) -> str:
    """根据配置决定输出尺寸，original 表示尽量沿用主图原始尺寸。"""
    size = (configured_size or "original").strip().lower()
    if size not in {"original", "input", "source"}:
        return configured_size or "auto"

    try:
        with Image.open(BytesIO(image)) as img:
            width, height = img.size
    except (UnidentifiedImageError, OSError, ValueError):
        return "auto"

    width, height = _fit_within_max_side(width, height, MAX_GPT_IMAGE_SIDE)
    return f"{width}x{height}"


def _fit_within_max_side(width: int, height: int, max_side: int) -> tuple[int, int]:
    """把超大图片等比缩到模型允许的最大边长内。"""
    if width <= 0 or height <= 0:
        return 1024, 1024

    longest_side = max(width, height)
    if longest_side <= max_side:
        return width, height

    scale = max_side / longest_side
    return max(1, round(width * scale)), max(1, round(height * scale))


@register("openai")
class OpenAIProvider(ImageEditorProvider):
    """GPT-Image-2 / OpenAI 兼容图片 Provider，统一走 /images/generations。"""

    def capabilities(self) -> Capabilities:
        return Capabilities(
            supports_multi_image=True,
            supports_mask=True,
            supports_chat=False,
            max_input_size_mb=50,
            max_output_count=10,
        )

    async def edit(self, request: EditRequest) -> EditResponse:
        """
        调用 OpenAI 兼容图片接口进行图像编辑。

        第三方中转站通常没有完整实现官方 /images/edits multipart 接口，
        这里按 /images/generations JSON 方式调用：模型名由配置控制，原图
        以 data URL 放入 image 字段，响应兼容 data[].b64_json / data[].url。
        """
        if not self.api_base:
            raise ValueError("OpenAI Provider 未配置 api_base")
        if not self.api_key:
            raise ValueError("OpenAI Provider 未配置 api_key")

        if self.config.get("request_mode") == "chat_completions":
            return await self._edit_with_chat_completions(request)

        return await self._edit_with_image_generations(request)

    async def _edit_with_image_generations(self, request: EditRequest) -> EditResponse:
        """调用 OpenAI 兼容 /images/generations 接口。"""
        url = f"{self.api_base}/images/generations"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        image_inputs = [_to_data_url(request.main_image)]
        image_inputs.extend(_to_data_url(image) for image in request.reference_images)
        if request.mask:
            image_inputs.append(_to_data_url(request.mask))

        payload = {
            "model": self.model,
            "prompt": request.instruction,
            "image": image_inputs[0] if len(image_inputs) == 1 else image_inputs,
            "n": request.output_count,
            "size": _resolve_output_size(request.main_image, self.config.get("size")),
            "quality": self.config.get("quality", "high"),
        }

        response_format = self.config.get("response_format")
        if response_format:
            payload["response_format"] = response_format

        # 允许在 providers.yaml 中给特定中转站追加兼容参数，例如 watermark=false。
        extra_payload = self.config.get("extra_payload")
        if isinstance(extra_payload, dict):
            payload.update(extra_payload)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code != 200:
                raise Exception(f"OpenAI API 错误 {response.status_code}: {_error_message(response)}")

            result = response.json()
            images = await _extract_images(result, client)

        if not images:
            raise Exception("OpenAI API 未返回图片数据")

        usage_data = result.get("usage", {}) or {}
        usage = TokenUsage(
            input_tokens=usage_data.get("input_tokens", 0),
            output_tokens=usage_data.get("output_tokens", 0),
            total_tokens=usage_data.get("total_tokens", 0),
        )

        return EditResponse(
            images=images,
            usage=usage,
            provider="openai",
            model=self.model,
            raw_response=result,
        )

    async def _edit_with_chat_completions(self, request: EditRequest) -> EditResponse:
        """调用支持图片输出的 OpenAI 兼容 /chat/completions 接口。"""
        url = f"{self.api_base}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        prompt = (
            f"{request.instruction}\n"
            "Generate exactly one edited image asset. Return only the image result."
        )
        content = [{"type": "text", "text": prompt}]

        input_images = [request.main_image, *request.reference_images]
        if request.mask:
            input_images.append(request.mask)

        for image in input_images:
            content.append({
                "type": "image_url",
                "image_url": {"url": _to_data_url(image)},
            })

        payload = {
            "model": self.model,
            "stream": False,
            "messages": [{"role": "user", "content": content}],
            "size": _resolve_output_size(request.main_image, self.config.get("size")),
        }

        extra_payload = self.config.get("extra_payload")
        if isinstance(extra_payload, dict):
            payload.update(extra_payload)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code != 200:
                raise Exception(f"OpenAI API 错误 {response.status_code}: {_error_message(response)}")

            result = response.json()
            images = await _extract_images(result, client)

        if not images:
            raise Exception("OpenAI API 未返回图片数据")

        usage_data = result.get("usage", {}) or {}
        usage = TokenUsage(
            input_tokens=usage_data.get("input_tokens", 0),
            output_tokens=usage_data.get("output_tokens", 0),
            total_tokens=usage_data.get("total_tokens", 0),
        )

        return EditResponse(
            images=images,
            usage=usage,
            provider="openai",
            model=self.model,
            raw_response=result,
        )


def _error_message(response: httpx.Response) -> str:
    """提取第三方 OpenAI 兼容接口的错误信息。"""
    try:
        error_data = response.json()
    except Exception:
        return response.text

    error = error_data.get("error")
    if isinstance(error, dict):
        return error.get("message") or response.text
    if isinstance(error, str):
        return error
    return response.text


async def _extract_images(result: dict, client: httpx.AsyncClient) -> list[bytes]:
    """从 OpenAI 图片接口响应中提取图片字节。"""
    images: list[bytes] = []
    image_items = []
    image_items.extend(_field(result, "data") or [])
    image_items.extend(_extract_choice_image_items(_field(result, "choices") or []))

    for item in image_items:
        b64_json = _field(item, "b64_json")
        image_url = _field(item, "url")

        if b64_json:
            images.append(base64.b64decode(b64_json))
        elif image_url:
            if str(image_url).startswith("data:image/"):
                images.append(_decode_data_url(image_url))
            else:
                img_response = await client.get(image_url)
                img_response.raise_for_status()
                images.append(img_response.content)

    return images


def _extract_choice_image_items(choices: list) -> list[dict]:
    """从 chat/completions 的 choices 中提取图片条目。"""
    items = []
    for choice in choices:
        message = _field(choice, "message") or {}
        content = _field(message, "content")
        if isinstance(content, list):
            for part in content:
                image_url = _field(_field(part, "image_url") or {}, "url")
                image_url = image_url or _field(part, "url") or _field(part, "image_url")
                b64_json = _field(part, "b64_json")
                text = _field(part, "text")
                if image_url:
                    items.append({"url": image_url})
                if b64_json:
                    items.append({"b64_json": b64_json})
                if isinstance(text, str):
                    items.extend(_extract_image_items_from_text(text))
        elif isinstance(content, str):
            items.extend(_extract_image_items_from_text(content))
    return items


def _extract_image_items_from_text(text: str) -> list[dict]:
    """从 Markdown、data URL 或裸 URL 文本中提取图片地址。"""
    items = []
    for match in re.finditer(r"!\[[^\]]*\]\(([^)]+)\)", text):
        items.append({"url": match.group(1)})
    for match in re.finditer(r"data:image/[a-zA-Z0-9.+-]+;base64,[A-Za-z0-9+/=]+", text):
        items.append({"url": match.group(0)})
    for match in re.finditer(r"https?://[^\s)]+", text):
        items.append({"url": match.group(0).rstrip(").,，。")})
    return items


def _decode_data_url(data_url: str) -> bytes:
    """解码 data:image/...;base64,... URL。"""
    _, encoded = data_url.split(",", 1)
    return base64.b64decode(encoded)
