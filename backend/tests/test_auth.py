"""用户认证接口集成测试"""
import pytest

_REG   = "/api/auth/register"
_LOGIN = "/api/auth/login"
_ME    = "/api/auth/me"

_USER = {"username": "测试用户甲", "phone": "13800000001", "password": "Password123"}


async def test_register_returns_token(client):
    r = await client.post(_REG, json=_USER)
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body
    assert body["user"]["username"] == _USER["username"]


async def test_register_duplicate_username(client):
    await client.post(_REG, json=_USER)
    r = await client.post(_REG, json={**_USER, "phone": "13800000002"})
    assert r.status_code == 409


async def test_register_duplicate_phone(client):
    await client.post(_REG, json=_USER)
    r = await client.post(_REG, json={**_USER, "username": "其他用户乙"})
    assert r.status_code == 409


@pytest.mark.parametrize("bad_username", ["!invalid", "a" * 20, ""])
async def test_register_invalid_username(client, bad_username):
    r = await client.post(_REG, json={**_USER, "username": bad_username})
    assert r.status_code in (400, 422)


@pytest.mark.parametrize("bad_phone", ["12345", "23800000001", "1380000000a"])
async def test_register_invalid_phone(client, bad_phone):
    r = await client.post(_REG, json={**_USER, "phone": bad_phone})
    assert r.status_code in (400, 422)


async def test_login_by_username(client):
    await client.post(_REG, json=_USER)
    r = await client.post(_LOGIN, json={"username_or_phone": _USER["username"], "password": _USER["password"]})
    assert r.status_code == 200
    assert "access_token" in r.json()


async def test_login_by_phone(client):
    await client.post(_REG, json=_USER)
    r = await client.post(_LOGIN, json={"username_or_phone": _USER["phone"], "password": _USER["password"]})
    assert r.status_code == 200


async def test_login_wrong_password(client):
    await client.post(_REG, json=_USER)
    r = await client.post(_LOGIN, json={"username_or_phone": _USER["username"], "password": "WrongPass999"})
    assert r.status_code == 401


async def test_me_without_token(client):
    r = await client.get(_ME)
    assert r.status_code == 401


async def test_me_with_valid_token(client):
    reg = await client.post(_REG, json=_USER)
    token = reg.json()["access_token"]
    r = await client.get(_ME, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["username"] == _USER["username"]


async def test_me_with_invalid_token(client):
    r = await client.get(_ME, headers={"Authorization": "Bearer invalid.token.here"})
    assert r.status_code == 401
