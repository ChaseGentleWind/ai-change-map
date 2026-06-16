"""编辑接口上传校验测试"""

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
