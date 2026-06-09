"""文件存储服务"""
import uuid
import json
from pathlib import Path
from typing import List, Optional
from config import UPLOAD_DIR, OUTPUT_DIR


def save_upload(file_bytes: bytes, suffix: str = ".jpg") -> tuple[str, str]:
    """
    保存上传的图片

    Returns:
        (file_id, relative_url)
    """
    file_id = str(uuid.uuid4())
    filename = f"{file_id}{suffix}"
    path = UPLOAD_DIR / filename
    path.write_bytes(file_bytes)
    return file_id, f"/uploads/{filename}"


def save_output(file_bytes: bytes, prefix: str = "result") -> str:
    """
    保存生成的结果图

    Returns:
        relative_url
    """
    filename = f"{prefix}_{uuid.uuid4().hex[:8]}.png"
    path = OUTPUT_DIR / filename
    path.write_bytes(file_bytes)
    return f"/outputs/{filename}"


def save_outputs(images: List[bytes], prefix: str = "result") -> List[str]:
    """批量保存结果图"""
    return [save_output(img, prefix) for img in images]


def get_file_bytes(relative_url: str) -> Optional[bytes]:
    """
    根据相对 URL 读取文件内容

    Args:
        relative_url: 如 /uploads/xxx.jpg 或 /outputs/xxx.png

    Returns:
        文件字节，不存在则返回 None
    """
    if relative_url.startswith("/uploads/"):
        path = UPLOAD_DIR / relative_url[len("/uploads/"):]
    elif relative_url.startswith("/outputs/"):
        path = OUTPUT_DIR / relative_url[len("/outputs/"):]
    else:
        return None

    if path.exists():
        return path.read_bytes()
    return None


def delete_file(relative_url: str) -> bool:
    """删除文件，返回是否成功"""
    if relative_url.startswith("/uploads/"):
        path = UPLOAD_DIR / relative_url[len("/uploads/"):]
    elif relative_url.startswith("/outputs/"):
        path = OUTPUT_DIR / relative_url[len("/outputs/"):]
    else:
        return False

    if path.exists():
        path.unlink()
        return True
    return False
