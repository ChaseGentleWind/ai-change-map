"""Provider 注册器与工厂"""
from typing import Dict, Type
from .base import ImageEditorProvider

# 全局注册表
PROVIDERS: Dict[str, Type[ImageEditorProvider]] = {}


def register(name: str):
    """
    Provider 注册装饰器

    用法:
        @register("gemini")
        class GeminiProvider(ImageEditorProvider):
            ...
    """
    def decorator(cls: Type[ImageEditorProvider]):
        PROVIDERS[name] = cls
        return cls
    return decorator


def get_provider(name: str, config: dict) -> ImageEditorProvider:
    """
    获取 Provider 实例

    Args:
        name: provider 名称
        config: provider 配置

    Returns:
        ImageEditorProvider 实例

    Raises:
        KeyError: 如果 provider 未注册
    """
    if name not in PROVIDERS:
        raise KeyError(f"Provider '{name}' 未注册。可用: {list(PROVIDERS.keys())}")

    return PROVIDERS[name](config)


def list_providers() -> list:
    """列出所有已注册的 provider 名称"""
    return list(PROVIDERS.keys())
