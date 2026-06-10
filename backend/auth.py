"""用户认证工具。"""
import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import JWT_ACCESS_TOKEN_EXPIRE_MINUTES, JWT_ALGORITHM, JWT_SECRET_KEY
from database import get_db
from models.database import User


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
PBKDF2_ITERATIONS = 260000


def verify_password(plain_password: str, password_hash: str) -> bool:
    """校验用户输入密码。"""
    try:
        scheme, iterations, salt, expected_hash = password_hash.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        actual_hash = _pbkdf2_hash(plain_password, salt, int(iterations))
        return secrets.compare_digest(actual_hash, expected_hash)
    except (ValueError, TypeError):
        return False


def get_password_hash(password: str) -> str:
    """生成密码哈希。"""
    salt = secrets.token_urlsafe(24)
    password_hash = _pbkdf2_hash(password, salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${password_hash}"


def create_access_token(subject: str, expires_delta: Optional[timedelta] = None) -> str:
    """创建 HS256 JWT access token。"""
    if JWT_ALGORITHM != "HS256":
        raise RuntimeError("当前内置 JWT 实现仅支持 HS256")

    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"sub": subject, "exp": int(expire.timestamp())}
    signing_input = f"{_b64_json(header)}.{_b64_json(payload)}"
    signature = _sign(signing_input)
    return f"{signing_input}.{signature}"


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """从 Bearer token 解析当前用户。"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="登录已失效，请重新登录",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = _decode_token(token)
    if payload is None:
        raise credentials_exception

    subject = payload.get("sub")
    expires_at = payload.get("exp")
    if subject is None or not isinstance(expires_at, int):
        raise credentials_exception
    if expires_at < int(datetime.now(timezone.utc).timestamp()):
        raise credentials_exception

    try:
        user_id = int(subject)
    except ValueError:
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise credentials_exception
    return user


def _pbkdf2_hash(password: str, salt: str, iterations: int) -> str:
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    )
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def _b64_json(data: dict) -> str:
    raw = json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return _b64_encode(raw)


def _b64_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _sign(signing_input: str) -> str:
    signature = hmac.new(
        JWT_SECRET_KEY.encode("utf-8"),
        signing_input.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return _b64_encode(signature)


def _decode_token(token: str) -> Optional[dict]:
    try:
        header_b64, payload_b64, signature = token.split(".", 2)
        signing_input = f"{header_b64}.{payload_b64}"
        if not secrets.compare_digest(_sign(signing_input), signature):
            return None

        header = json.loads(_b64_decode(header_b64))
        if header.get("alg") != "HS256":
            return None

        payload = json.loads(_b64_decode(payload_b64))
        if not isinstance(payload, dict):
            return None
        return payload
    except (ValueError, json.JSONDecodeError):
        return None
