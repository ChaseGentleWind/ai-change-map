"""OpenAIProvider 上游协议组装测试。"""
import base64
from io import BytesIO

import pytest
from PIL import Image

from providers.openai import OpenAIProvider
from providers.schemas import EditRequest


_PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
)


def _make_png(width: int, height: int) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (width, height), "white").save(buf, format="PNG")
    return buf.getvalue()


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = str(payload)

    def json(self):
        return self._payload


class _FakeAsyncClient:
    calls = []
    init_kwargs = []
    response_payload = {}
    response_status_codes = []

    def __init__(self, **kwargs):
        self.__class__.init_kwargs.append(kwargs)
        self.timeout = kwargs.get("timeout")

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, **kwargs):
        call = {"url": url, **kwargs}
        if isinstance(call.get("data"), dict):
            call["data"] = dict(call["data"])
        if isinstance(call.get("json"), dict):
            call["json"] = dict(call["json"])
        self.__class__.calls.append(call)
        payload = self.__class__.response_payload or {
            "data": [{"b64_json": base64.b64encode(_PNG_BYTES).decode("ascii")}],
        }
        status_code = self.__class__.response_status_codes.pop(0) if self.__class__.response_status_codes else 200
        return _FakeResponse(payload, status_code=status_code)


@pytest.fixture(autouse=True)
def reset_fake_client(monkeypatch):
    _FakeAsyncClient.calls = []
    _FakeAsyncClient.init_kwargs = []
    _FakeAsyncClient.response_payload = {}
    _FakeAsyncClient.response_status_codes = []
    monkeypatch.setattr("providers.openai.httpx.AsyncClient", _FakeAsyncClient)


def test_openai_capabilities_match_relay_limits():
    provider = OpenAIProvider({
        "api_base": "http://relay.example/v1",
        "api_key": "test-key",
        "model": "gpt-image-2-1k",
    })

    caps = provider.capabilities()

    assert caps.supports_multi_image is True
    assert caps.supports_mask is True
    assert caps.max_input_size_mb == 20


@pytest.mark.asyncio
async def test_image_edits_uses_image_array_with_main_image_first():
    provider = OpenAIProvider({
        "api_base": "http://relay.example/v1",
        "api_key": "test-key",
        "model": "gpt-image-2-1k",
        "size": "1024x1024",
        "timeout": 30,
    })
    request = EditRequest(
        main_image=_PNG_BYTES,
        reference_images=[_PNG_BYTES],
        instruction="把背景改成雪山",
        output_count=2,
    )

    response = await provider.edit(request)

    assert response.images == [_PNG_BYTES]
    assert _FakeAsyncClient.init_kwargs[0]["trust_env"] is False
    call = _FakeAsyncClient.calls[0]
    assert call["url"] == "http://relay.example/v1/images/edits"
    assert call["data"]["model"] == "gpt-image-2-1k"
    prompt = call["data"]["prompt"]
    assert "用户原始指令" in prompt
    assert "把背景改成雪山" in prompt
    assert "第1张 image[] 是主图/待编辑图" in prompt
    assert "第2张 image[] 是参考图" in prompt
    assert "不要忽略参考图" in prompt
    assert call["data"]["n"] == "2"

    files = call["files"]
    assert [field for field, _ in files] == ["image[]", "image[]"]
    assert files[0][1][0] == "image.png"
    assert files[1][1][0] == "ref_0.png"


@pytest.mark.asyncio
async def test_image_edits_sends_mask_before_reference_images():
    provider = OpenAIProvider({
        "api_base": "http://relay.example/v1",
        "api_key": "test-key",
        "model": "gpt-image-2-1k",
        "size": "1024x1024",
        "timeout": 30,
    })
    request = EditRequest(
        main_image=_PNG_BYTES,
        mask=_PNG_BYTES,
        reference_images=[_PNG_BYTES],
        instruction="把选区替换成参考图里的风扇",
    )

    await provider.edit(request)

    call = _FakeAsyncClient.calls[0]
    prompt = call["data"]["prompt"]
    assert "第1张 image[] 是主图/待编辑图" in prompt
    assert "第2张 image[] 是黑白局部遮罩" in prompt
    assert "第3张 image[] 是参考图" in prompt
    assert "白色区域可以修改，黑色区域必须保持不变" in prompt

    files = call["files"]
    assert [field for field, _ in files] == ["image[]", "image[]", "image[]"]
    assert [file_info[0] for _, file_info in files] == ["image.png", "mask.png", "ref_0.png"]


@pytest.mark.asyncio
async def test_image_1k_uses_official_16_9_size():
    provider = OpenAIProvider({
        "api_base": "http://relay.example/v1",
        "api_key": "test-key",
        "model": "gpt-image-2-1k",
        "size": "original",
        "timeout": 30,
    })
    request = EditRequest(
        main_image=_make_png(1920, 1080),
        instruction="把背景改成雪山",
    )

    await provider.edit(request)

    assert _FakeAsyncClient.calls[0]["data"]["size"] == "1376x768"


@pytest.mark.asyncio
async def test_pro4k_uses_requested_resolution_tier():
    provider = OpenAIProvider({
        "api_base": "http://relay.example/v1",
        "api_key": "test-key",
        "model": "gpt-image2-Pro4K",
        "request_mode": "image_edits",
        "default_resolution": "2k",
        "size": "original",
        "timeout": 30,
    })
    request = EditRequest(
        main_image=_make_png(1920, 1080),
        instruction="生成高分辨率版本",
        extra={"output_resolution": "4k"},
    )

    await provider.edit(request)

    assert _FakeAsyncClient.calls[0]["data"]["model"] == "gpt-image2-Pro4K"
    assert _FakeAsyncClient.calls[0]["data"]["size"] == "3584x2016"


@pytest.mark.asyncio
async def test_pro4k_gateway_error_downgrades_4k_to_2k():
    _FakeAsyncClient.response_status_codes = [502, 200]
    provider = OpenAIProvider({
        "api_base": "http://relay.example/v1",
        "api_key": "test-key",
        "model": "gpt-image2-Pro4K",
        "request_mode": "image_edits",
        "size": "original",
        "timeout": 30,
    })
    request = EditRequest(
        main_image=_make_png(1920, 1080),
        instruction="生成高分辨率版本",
        extra={"output_resolution": "4k"},
    )

    await provider.edit(request)

    assert [call["data"]["size"] for call in _FakeAsyncClient.calls] == ["3584x2016", "2048x1136"]


@pytest.mark.asyncio
async def test_chat_completions_payload_includes_n_and_expected_fields():
    provider = OpenAIProvider({
        "api_base": "http://relay.example/v1",
        "api_key": "test-key",
        "model": "gpt-image-2",
        "request_mode": "chat_completions",
        "size": "2048x1152",
        "timeout": 30,
    })
    request = EditRequest(
        main_image=_PNG_BYTES,
        reference_images=[_PNG_BYTES],
        instruction="参考图片生成自然人像",
        output_count=3,
    )

    response = await provider.edit(request)

    assert response.images == [_PNG_BYTES]
    call = _FakeAsyncClient.calls[0]
    payload = call["json"]
    assert call["url"] == "http://relay.example/v1/chat/completions"
    assert payload["model"] == "gpt-image-2"
    assert payload["stream"] is False
    assert payload["n"] == 3
    assert payload["size"] == "1536x1024"
    assert payload["messages"][0]["role"] == "user"
    content = payload["messages"][0]["content"]
    assert content[0]["type"] == "text"
    assert [part["type"] for part in content[1:]] == ["image_url", "image_url"]


@pytest.mark.asyncio
async def test_gpt_image_2_defaults_to_chat_completions_protocol():
    provider = OpenAIProvider({
        "api_base": "http://relay.example/v1",
        "api_key": "test-key",
        "model": "gpt-image-2",
        "size": "1024x1024",
        "timeout": 30,
    })
    request = EditRequest(
        main_image=_PNG_BYTES,
        instruction="参考图片生成自然人像",
        output_count=1,
    )

    response = await provider.edit(request)

    assert response.images == [_PNG_BYTES]
    call = _FakeAsyncClient.calls[0]
    assert call["url"] == "http://relay.example/v1/chat/completions"
    assert call["json"]["model"] == "gpt-image-2"
    assert call["json"]["size"] == "1254x1254"


@pytest.mark.asyncio
async def test_chat_completions_sends_mask_as_image_part():
    provider = OpenAIProvider({
        "api_base": "http://relay.example/v1",
        "api_key": "test-key",
        "model": "gpt-image-2",
        "timeout": 30,
    })
    request = EditRequest(
        main_image=_PNG_BYTES,
        instruction="只修改选区",
        mask=_PNG_BYTES,
    )

    await provider.edit(request)

    content = _FakeAsyncClient.calls[0]["json"]["messages"][0]["content"]
    assert [part["type"] for part in content] == ["text", "image_url", "image_url"]
    assert "第2张图片 是黑白局部遮罩" in content[0]["text"]


@pytest.mark.asyncio
async def test_chat_completions_extracts_images_and_usage_from_responses():
    data_url = f"data:image/png;base64,{base64.b64encode(_PNG_BYTES).decode('ascii')}"
    _FakeAsyncClient.response_payload = {
        "object": "image_generation",
        "data": [],
        "responses": [
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": f"![image]({data_url})",
                        }
                    }
                ],
                "usage": {
                    "prompt_tokens": 26,
                    "completion_tokens": 1145,
                    "total_tokens": 1171,
                },
            }
        ],
    }
    provider = OpenAIProvider({
        "api_base": "http://relay.example/v1",
        "api_key": "test-key",
        "model": "gpt-image-2",
        "timeout": 30,
    })
    request = EditRequest(
        main_image=_PNG_BYTES,
        instruction="参考图片生成自然人像",
    )

    response = await provider.edit(request)

    assert response.images == [_PNG_BYTES]
    assert response.usage.input_tokens == 26
    assert response.usage.output_tokens == 1145
    assert response.usage.total_tokens == 1171
