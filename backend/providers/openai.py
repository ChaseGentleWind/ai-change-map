"""OpenAI-compatible Provider 实现"""
import base64
import re
import sys
from collections.abc import Mapping
from io import BytesIO

import httpx
from PIL import Image, UnidentifiedImageError

from .base import ImageEditorProvider
from .schemas import Capabilities, EditRequest, EditResponse, TokenUsage
from .registry import register

# gpt-image-2-1k / gpt-image2-Pro4K 的官方分辨率表。
IMAGE_EDIT_SIZE_TIERS: dict[str, tuple[tuple[int, int], ...]] = {
    "1k": (
        (1024, 1024),
        (1152, 928),
        (1200, 896),
        (1264, 848),
        (1376, 768),
        (1584, 672),
        (928, 1152),
        (896, 1200),
        (848, 1264),
        (768, 1376),
    ),
    "2k": (
        (2048, 2048),
        (2048, 1648),
        (2048, 1536),
        (2048, 1376),
        (2048, 1136),
        (2048, 864),
        (1648, 2048),
        (1536, 2048),
        (1376, 2048),
        (1136, 2048),
    ),
    "4k": (
        (2880, 2880),
        (3200, 2560),
        (3264, 2448),
        (3504, 2336),
        (3584, 2016),
        (3808, 1632),
        (2560, 3200),
        (2448, 3264),
        (2336, 3504),
        (2016, 3584),
    ),
}
IMAGE_EDIT_SIZES: tuple[tuple[int, int], ...] = IMAGE_EDIT_SIZE_TIERS["1k"]

# gpt-image-2 /chat/completions 常用尺寸。自定义尺寸另有约束，优先使用文档列出的常用尺寸。
CHAT_COMPLETION_SIZES: tuple[tuple[int, int], ...] = (
    (1254, 1254),
    (1448, 1086),
    (1086, 1448),
    (1536, 1024),
    (1024, 1536),
)


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


def _ensure_png(image: bytes) -> bytes:
    """确保图片是 PNG 格式，非 PNG 则转换（/images/edits 要求 PNG）。"""
    if image.startswith(b"\x89PNG\r\n\x1a\n"):
        return image
    try:
        with Image.open(BytesIO(image)) as img:
            buf = BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()
    except (UnidentifiedImageError, OSError, ValueError):
        return image


def _field(value, name: str):
    """兼容 dict 和 SDK 对象两种响应字段读取方式。"""
    if isinstance(value, Mapping):
        return value.get(name)
    return getattr(value, name, None)


def _resolve_output_size(
    image: bytes,
    configured_size: str | None,
    allowed_sizes: tuple[tuple[int, int], ...] = IMAGE_EDIT_SIZES,
) -> str:
    """决定输出尺寸：original 按原图比例挑最接近的白名单尺寸；显式尺寸校正后返回。"""
    size = (configured_size or "original").strip().lower()

    if size in {"original", "input", "source"}:
        try:
            with Image.open(BytesIO(image)) as img:
                width, height = img.size
        except (UnidentifiedImageError, OSError, ValueError):
            return _fallback_size(allowed_sizes)
        return _pick_allowed_size(width, height, allowed_sizes)

    parsed = _parse_size_string(configured_size)
    if parsed is None:
        return _fallback_size(allowed_sizes)
    return _pick_allowed_size(*parsed, allowed_sizes)


def _resolve_image_edit_size(request: EditRequest, config: dict, model: str) -> str:
    """按模型、请求分辨率和原图比例决定 /images/edits 输出尺寸。"""
    requested_tier = str(request.extra.get("output_resolution") or "").strip().lower()
    configured_tier = str(
        config.get("resolution")
        or config.get("default_resolution")
        or ""
    ).strip().lower()

    if model == "gpt-image-2-1k":
        tier = "1k"
    elif model == "gpt-image2-Pro4K":
        tier = requested_tier if requested_tier in IMAGE_EDIT_SIZE_TIERS else configured_tier
        if tier not in IMAGE_EDIT_SIZE_TIERS:
            tier = "2k"
    else:
        tier = requested_tier or configured_tier

    allowed_sizes = IMAGE_EDIT_SIZE_TIERS.get(tier, IMAGE_EDIT_SIZES)
    return _resolve_output_size(request.main_image, config.get("size"), allowed_sizes)


def _resolve_downgrade_size(request: EditRequest, config: dict) -> str:
    """Pro4K 高分辨率失败时降到 2K，仍保持原图比例。"""
    return _resolve_output_size(request.main_image, config.get("size"), IMAGE_EDIT_SIZE_TIERS["2k"])


def _is_4k_size(size: str) -> bool:
    return _parse_size_string(size) in IMAGE_EDIT_SIZE_TIERS["4k"]


def _parse_size_string(value: str | None) -> tuple[int, int] | None:
    """解析 '1024x1536' 这类尺寸字符串。"""
    if not value:
        return None
    parts = value.lower().split("x")
    if len(parts) != 2:
        return None
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return None


def _pick_allowed_size(
    width: int,
    height: int,
    allowed_sizes: tuple[tuple[int, int], ...],
) -> str:
    """按目标宽高比挑选与之最接近的白名单尺寸。"""
    if width <= 0 or height <= 0:
        return _fallback_size(allowed_sizes)

    target_ratio = width / height
    best = min(
        allowed_sizes,
        key=lambda wh: abs((wh[0] / wh[1]) - target_ratio),
    )
    return f"{best[0]}x{best[1]}"


def _fallback_size(allowed_sizes: tuple[tuple[int, int], ...]) -> str:
    """返回尺寸白名单中的默认方图尺寸。"""
    width, height = allowed_sizes[0]
    return f"{width}x{height}"


def _client_options(config: dict, timeout: int | float) -> dict:
    """构建 httpx 客户端参数；默认绕过系统代理，避免长耗时图片响应被中间代理截断。"""
    return {
        "timeout": timeout,
        "trust_env": bool(config.get("trust_env", False)),
    }


def _build_edit_prompt(request: EditRequest, image_label: str) -> str:
    """构建上游编辑提示词，明确多张输入图的角色，避免参考图被模型忽略。"""
    instruction = request.instruction.strip()
    lines = [
        "用户原始指令：",
        instruction,
        "",
        "输入图片说明：",
        f"1. {_image_slot_name(1, image_label)} 是主图/待编辑图。以它的主体、构图、透视、光照和未指定区域为准。",
    ]

    next_index = 2
    if request.mask:
        lines.append(
            f"{next_index}. {_image_slot_name(next_index, image_label)} 是黑白局部遮罩。"
            "白色区域可以修改，黑色区域必须保持不变；这张遮罩只用于定位，不要画进结果图。"
        )
        next_index += 1

    if request.reference_images:
        ref_count = len(request.reference_images)
        if ref_count == 1:
            lines.append(
                f"{next_index}. {_image_slot_name(next_index, image_label)} 是参考图。"
                "必须读取其中与用户指令相关的产品、物体、文字、风格、材质、颜色或版式，并应用到主图指定位置。"
            )
        else:
            end_index = next_index + ref_count - 1
            lines.append(
                f"{next_index}. {_image_range_name(next_index, end_index, image_label)} 是参考图。"
                "必须逐张读取与用户指令相关的产品、物体、文字、风格、材质、颜色或版式，并应用到主图指定位置。"
            )

    lines.extend([
        "",
        "编辑约束：",
        "- 严格执行用户原始指令，必须产生可见修改，不要只返回原图。",
        "- 除用户明确要求修改的区域外，尽量保持主图的主体、背景、构图、透视、光照、颜色和清晰度不变。",
    ])
    if request.mask:
        lines.append("- 如果遮罩与用户指令冲突，以遮罩白色区域作为可编辑范围，黑色区域保持不变。")
    if request.reference_images:
        lines.append("- 不要忽略参考图；参考图用于提供要替换、借鉴或融合到主图中的目标元素。")
    lines.append(f"- 生成 {request.output_count} 张最终编辑后的图片，只返回图片结果。")

    return "\n".join(lines)


def _image_slot_name(index: int, image_label: str) -> str:
    if image_label == "image[]":
        return f"第{index}张 image[]"
    return f"第{index}张图片"


def _image_range_name(start: int, end: int, image_label: str) -> str:
    if image_label == "image[]":
        return f"第{start}张到第{end}张 image[]"
    return f"第{start}张到第{end}张图片"


def _safe_prompt_preview(prompt: str, limit: int = 120) -> str:
    """生成单行 prompt 预览，避免日志过长或控制字符污染终端。"""
    preview = " ".join(prompt.split())
    if len(preview) > limit:
        preview = f"{preview[:limit]}..."
    return preview


def _console_log(message: str) -> None:
    """Windows 终端编码不一致时安全打印调试日志。"""
    try:
        print(message)
    except UnicodeEncodeError:
        encoding = sys.stdout.encoding or "utf-8"
        print(message.encode(encoding, errors="replace").decode(encoding))


@register("openai_chat")
@register("openai_pro4k")
@register("openai_1k")
@register("openai")
class OpenAIProvider(ImageEditorProvider):
    """GPT-Image-2 / OpenAI 兼容图片 Provider。
    带图编辑走 /images/edits multipart；纯文生图走 /images/generations JSON。
    """

    def capabilities(self) -> Capabilities:
        return Capabilities(
            supports_multi_image=True,
            supports_mask=True,
            supports_chat=False,
            max_input_size_mb=20,
            max_output_count=10,
        )

    async def edit(self, request: EditRequest) -> EditResponse:
        if not self.api_base:
            raise ValueError("OpenAI Provider 未配置 api_base")
        if not self.api_key:
            raise ValueError("OpenAI Provider 未配置 api_key")

        request_mode = self._request_mode()
        if request_mode == "chat_completions":
            return await self._edit_with_chat_completions(request)
        if request_mode == "image_edits":
            return await self._edit_with_image_edits(request)
        if request_mode == "image_generations":
            return await self._edit_with_image_generations(request)

        # 默认：有主图走 /images/edits multipart，无主图走 /images/generations
        if request.main_image:
            return await self._edit_with_image_edits(request)
        return await self._edit_with_image_generations(request)

    def _request_mode(self) -> str:
        """读取请求模式；gpt-image-2 默认使用文档要求的 chat/completions 协议。"""
        request_mode = self.config.get("request_mode", "")
        if request_mode:
            return request_mode
        if self.model == "gpt-image-2":
            return "chat_completions"
        if self.model in {"gpt-image-2-1k", "gpt-image2-Pro4K"}:
            return "image_edits"
        return ""

    async def _edit_with_image_edits(self, request: EditRequest) -> EditResponse:
        """/images/edits multipart 接口，文档要求 image[] 字段，PNG 图片。"""
        url = f"{self.api_base}/images/edits"
        headers = {"Authorization": f"Bearer {self.api_key}"}

        # 文档统一要求 image[]：主图与参考图都按这个字段名追加
        files: list[tuple] = [
            ("image[]", ("image.png", _ensure_png(request.main_image), "image/png"))
        ]
        if request.mask:
            files.append(("image[]", ("mask.png", _ensure_png(request.mask), "image/png")))
        for i, ref in enumerate(request.reference_images):
            files.append(("image[]", (f"ref_{i}.png", _ensure_png(ref), "image/png")))

        # 文档明确不建议传 quality / mask / response_format / style，全部省略
        output_size = _resolve_image_edit_size(request, self.config, self.model)
        prompt = _build_edit_prompt(request, "image[]")
        data: dict = {
            "model": self.model,
            "prompt": prompt,
            "n": str(request.output_count),
            "size": output_size,
        }

        extra_payload = self.config.get("extra_payload")
        if isinstance(extra_payload, dict):
            for k, v in extra_payload.items():
                data[k] = str(v)

        if self.config.get("debug_request_log", True):
            _console_log(
                "[OpenAIProvider] /images/edits "
                f"model={self.model} size={output_size} output_count={request.output_count} "
                f"image_files={len(files)} reference_images={len(request.reference_images)} "
                f"mask={'yes' if request.mask else 'no'} prompt_chars={len(prompt)} "
                f"prompt_preview={_safe_prompt_preview(prompt)!r}"
            )

        async with httpx.AsyncClient(**_client_options(self.config, self.timeout)) as client:
            response = await client.post(url, headers=headers, data=data, files=files)
            if (
                response.status_code in {502, 503, 504}
                and self.model == "gpt-image2-Pro4K"
                and _is_4k_size(output_size)
                and self.config.get("downgrade_4k_on_gateway_error", True)
            ):
                data["size"] = _resolve_downgrade_size(request, self.config)
                response = await client.post(url, headers=headers, data=data, files=files)
            if response.status_code != 200:
                raise Exception(f"OpenAI API 错误 {response.status_code}: {_error_message(response)}")

            result = response.json()
            images = await _extract_images(result, client)

        if not images:
            raise Exception("OpenAI API 未返回图片数据")

        usage = _extract_usage(result)
        return EditResponse(images=images, usage=usage, provider="openai", model=self.model, raw_response=result)

    async def _edit_with_image_generations(self, request: EditRequest) -> EditResponse:
        """调用 OpenAI 兼容 /images/generations 接口（纯文生图）。"""
        url = f"{self.api_base}/images/generations"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # 文档明确不建议传 quality / response_format / style，全部省略
        payload = {
            "model": self.model,
            "prompt": request.instruction,
            "n": request.output_count,
            "size": _resolve_output_size(request.main_image, self.config.get("size")),
        }

        extra_payload = self.config.get("extra_payload")
        if isinstance(extra_payload, dict):
            payload.update(extra_payload)

        async with httpx.AsyncClient(**_client_options(self.config, self.timeout)) as client:
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code != 200:
                raise Exception(f"OpenAI API 错误 {response.status_code}: {_error_message(response)}")

            result = response.json()
            images = await _extract_images(result, client)

        if not images:
            raise Exception("OpenAI API 未返回图片数据")

        usage = _extract_usage(result)
        return EditResponse(images=images, usage=usage, provider="openai", model=self.model, raw_response=result)

    async def _edit_with_chat_completions(self, request: EditRequest) -> EditResponse:
        """调用支持图片输出的 OpenAI 兼容 /chat/completions 接口。"""
        url = f"{self.api_base}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        prompt = _build_edit_prompt(request, "图片")
        content = [{"type": "text", "text": prompt}]

        input_images = [request.main_image]
        if request.mask:
            input_images.append(request.mask)
        input_images.extend(request.reference_images)

        for image in input_images:
            content.append({
                "type": "image_url",
                "image_url": {"url": _to_data_url(image)},
            })

        payload = {
            "model": self.model,
            "stream": False,
            "n": request.output_count,
            "messages": [{"role": "user", "content": content}],
            "size": _resolve_output_size(
                request.main_image,
                self.config.get("size"),
                CHAT_COMPLETION_SIZES,
            ),
        }

        extra_payload = self.config.get("extra_payload")
        if isinstance(extra_payload, dict):
            payload.update(extra_payload)

        if self.config.get("debug_request_log", True):
            _console_log(
                "[OpenAIProvider] /chat/completions "
                f"model={self.model} size={payload['size']} output_count={request.output_count} "
                f"image_parts={len(input_images)} reference_images={len(request.reference_images)} "
                f"mask={'yes' if request.mask else 'no'} prompt_chars={len(prompt)} "
                f"prompt_preview={_safe_prompt_preview(prompt)!r}"
            )

        async with httpx.AsyncClient(**_client_options(self.config, self.timeout)) as client:
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code != 200:
                raise Exception(f"OpenAI API 错误 {response.status_code}: {_error_message(response)}")

            result = response.json()
            images = await _extract_images(result, client)

        if not images:
            raise Exception("OpenAI API 未返回图片数据")

        usage = _extract_usage(result)

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
    for response in _field(result, "responses") or []:
        image_items.extend(_extract_choice_image_items(_field(response, "choices") or []))

    seen_sources = set()
    for item in image_items:
        b64_json = _field(item, "b64_json")
        image_url = _field(item, "url")
        source_key = ("b64", b64_json) if b64_json else ("url", image_url)
        if source_key in seen_sources:
            continue
        seen_sources.add(source_key)

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


def _extract_usage(result: dict) -> TokenUsage:
    """兼容图片协议与 chat/completions 协议的 token 用量字段。"""
    usage = _field(result, "usage")
    if isinstance(usage, Mapping):
        return _usage_from_mapping(usage)

    usage_items = [
        response_usage
        for response in _field(result, "responses") or []
        if isinstance((response_usage := _field(response, "usage")), Mapping)
    ]

    input_tokens = 0
    output_tokens = 0
    total_tokens = 0
    for item in usage_items:
        item_usage = _usage_from_mapping(item)
        input_tokens += item_usage.input_tokens
        output_tokens += item_usage.output_tokens
        total_tokens += item_usage.total_tokens

    return TokenUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
    )


def _usage_from_mapping(usage: Mapping) -> TokenUsage:
    """把 OpenAI 图片协议或 chat 协议 usage 字段转换为统一结构。"""
    input_tokens = _to_int(usage.get("input_tokens") or usage.get("prompt_tokens"))
    output_tokens = _to_int(usage.get("output_tokens") or usage.get("completion_tokens"))
    total_tokens = _to_int(usage.get("total_tokens")) or input_tokens + output_tokens
    return TokenUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
    )


def _to_int(value) -> int:
    """宽松转换第三方返回的 token 数字。"""
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


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
