"""Providers 信息接口"""
from fastapi import APIRouter
from models.schemas import ProvidersListSchema, ProviderInfoSchema, ProviderCapabilitiesSchema
from providers import PROVIDERS, get_provider
from config import PROVIDERS_CONFIG

router = APIRouter(prefix="/api", tags=["Providers"])


@router.get("/providers", response_model=ProvidersListSchema)
async def list_providers():
    """列出所有可用的 providers 及其能力"""
    providers_list = []

    for name, provider_class in PROVIDERS.items():
        config = PROVIDERS_CONFIG["providers"].get(name, {})
        if not config:
            continue

        # 实例化获取能力
        try:
            instance = provider_class(config)
            caps = instance.capabilities()

            providers_list.append(ProviderInfoSchema(
                name=name,
                model=config.get("model", ""),
                display_name=_get_display_name(name),
                enabled=config.get("enabled", False),
                capabilities=ProviderCapabilitiesSchema(
                    supports_multi_image=caps.supports_multi_image,
                    supports_mask=caps.supports_mask,
                    supports_chat=caps.supports_chat,
                    max_input_size_mb=caps.max_input_size_mb,
                    max_output_count=caps.max_output_count
                )
            ))
        except Exception:
            continue

    return ProvidersListSchema(
        default=PROVIDERS_CONFIG.get("default_provider", "gemini"),
        providers=providers_list
    )


def _get_display_name(provider_name: str) -> str:
    """获取 provider 的显示名称"""
    display_names = {
        "gemini": "Gemini 2.5 Flash Image",
        "openai": "GPT-Image-2",
        "openai_1k": "GPT-Image-2 1K 稳定编辑",
        "openai_pro4k": "GPT-Image2 Pro 4K",
        "openai_chat": "GPT-Image-2 对话 1K",
        "seededit": "SeedEdit 3.0 (豆包)",
        "tongyi": "通义万相",
        "flux": "FLUX.1 Kontext"
    }
    return display_names.get(provider_name, provider_name.title())
