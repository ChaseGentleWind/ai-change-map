"""编辑接口上传校验测试"""
import pytest
from fastapi import HTTPException

from routers.edit import _MAX_TOTAL_IMAGE_SIZE, _validate_total_image_size
from services.edit_service import EditService

_REG  = "/api/auth/register"
_EDIT = "/api/edit"
_USER = {"username": "编辑测试用户", "phone": "13900000099", "password": "Password123"}


async def _token(client) -> str:
    r = await client.post(_REG, json=_USER)
    return r.json()["access_token"]


async def test_edit_requires_auth(client):
    """未携带 token 请求返回 401。"""
    r = await client.post(
        _EDIT,
        data={"instruction": "测试"},
        files={"main_image": ("t.png", b"fake", "image/png")},
    )
    assert r.status_code == 401


async def test_upload_non_image_mime_rejected(client):
    """非图片 MIME 类型返回 415。"""
    token = await _token(client)
    r = await client.post(
        _EDIT,
        data={"instruction": "测试"},
        files={"main_image": ("file.txt", b"hello world", "text/plain")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 415


async def test_upload_oversized_image_rejected(client):
    """超过 20 MB 的图片返回 413。"""
    token = await _token(client)
    oversized = b"x" * (20 * 1024 * 1024 + 1)
    r = await client.post(
        _EDIT,
        data={"instruction": "测试"},
        files={"main_image": ("big.png", oversized, "image/png")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 413


def test_total_upload_size_rejected():
    """一次请求中所有输入图片总大小超过 20 MB 时返回 413。"""
    with pytest.raises(HTTPException) as exc_info:
        _validate_total_image_size([b"x" * (_MAX_TOTAL_IMAGE_SIZE // 2 + 1)] * 2)

    assert exc_info.value.status_code == 413


def test_openai_local_edit_allows_mask_input():
    """OpenAI 图像模型可把 mask 作为多图输入传给上游，能力校验不应失败。"""
    service = EditService.__new__(EditService)

    service._validate_provider_capabilities(
        selected_provider="openai_1k",
        provider_config={
            "api_base": "http://relay.example/v1",
            "api_key": "test-key",
            "model": "gpt-image-2-1k",
            "request_mode": "image_edits",
        },
        task_mode="local_edit",
        reference_count=0,
        has_mask=True,
        output_count=1,
    )
