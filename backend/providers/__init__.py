"""Providers 包初始化 — 导入所有 provider 以触发注册"""
from .base import ImageEditorProvider
from .schemas import EditRequest, EditResponse, Capabilities, TokenUsage
from .registry import register, get_provider, list_providers, PROVIDERS
from .router import TaskRouter

# 导入所有 provider 实现（触发 @register 装饰器）
from .gemini import GeminiProvider
from .openai import OpenAIProvider
from .seededit import SeedEditProvider

__all__ = [
    "ImageEditorProvider",
    "EditRequest",
    "EditResponse",
    "Capabilities",
    "TokenUsage",
    "register",
    "get_provider",
    "list_providers",
    "PROVIDERS",
    "TaskRouter",
    "GeminiProvider",
    "OpenAIProvider",
    "SeedEditProvider",
]
