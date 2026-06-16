"""配置管理模块"""
import os
from pathlib import Path
from typing import Dict, Any
import yaml
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 项目根目录
BASE_DIR = Path(__file__).parent.parent

# 数据库配置
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./db/app.db")

# 文件存储路径
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# API 配置
RELAY_API_BASE = os.getenv("RELAY_API_BASE", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", os.getenv("AINX_API_KEY", ""))
OPENAI_BASE_URL = os.getenv(
    "OPENAI_BASE_URL",
    os.getenv("AINX_API_BASE", RELAY_API_BASE or "https://ainx.chat/v1"),
)
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-image-2")
AINX_API_BASE = os.getenv("AINX_API_BASE", OPENAI_BASE_URL)
AINX_API_KEY = os.getenv("AINX_API_KEY", OPENAI_API_KEY)
YUNWU_API_BASE = os.getenv("YUNWU_API_BASE", "https://yunwu.ai/v1")
YUNWU_GEMINI_API_BASE = os.getenv("YUNWU_GEMINI_API_BASE", "https://yunwu.ai/v1beta")
YUNWU_API_KEY = os.getenv("YUNWU_API_KEY", GEMINI_API_KEY)
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-secret-change-me")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "10080"))
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "").strip()
ADMIN_PHONE = os.getenv("ADMIN_PHONE", "").strip()
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
ADMIN_USERNAMES = [item.strip() for item in os.getenv("ADMIN_USERNAMES", "").split(",") if item.strip()]
ADMIN_PHONES = [item.strip() for item in os.getenv("ADMIN_PHONES", "").split(",") if item.strip()]
if ADMIN_USERNAME and ADMIN_USERNAME not in ADMIN_USERNAMES:
    ADMIN_USERNAMES.append(ADMIN_USERNAME)
if ADMIN_PHONE and ADMIN_PHONE not in ADMIN_PHONES:
    ADMIN_PHONES.append(ADMIN_PHONE)

CORS_ALLOWED_ORIGINS_RAW = os.getenv("CORS_ALLOWED_ORIGINS", "")
CORS_ALLOWED_ORIGINS = (
    [o.strip() for o in CORS_ALLOWED_ORIGINS_RAW.split(",") if o.strip()]
    or ["*"]
)

_INSECURE_JWT_DEFAULTS = {"dev-secret-change-me", "please_change_this_secret_in_production", ""}


def validate_startup_config() -> None:
    """启动时校验安全敏感配置，不合格直接抛错阻止启动。"""
    if JWT_SECRET_KEY in _INSECURE_JWT_DEFAULTS or len(JWT_SECRET_KEY) < 32:
        raise RuntimeError(
            "JWT_SECRET_KEY 不安全：请在 .env 中设置长度 ≥ 32 的随机字符串，"
            "可用 `python -c \"import secrets; print(secrets.token_hex(32))\"` 生成"
        )

ENV_DEFAULTS = {
    "RELAY_API_BASE": RELAY_API_BASE,
    "GEMINI_API_KEY": GEMINI_API_KEY,
    "OPENAI_API_KEY": OPENAI_API_KEY,
    "OPENAI_BASE_URL": OPENAI_BASE_URL,
    "OPENAI_MODEL": OPENAI_MODEL,
    "AINX_API_BASE": AINX_API_BASE,
    "AINX_API_KEY": AINX_API_KEY,
    "YUNWU_API_BASE": YUNWU_API_BASE,
    "YUNWU_GEMINI_API_BASE": YUNWU_GEMINI_API_BASE,
    "YUNWU_API_KEY": YUNWU_API_KEY,
}


def load_providers_config() -> Dict[str, Any]:
    """加载 providers 配置文件"""
    config_path = Path(__file__).parent / "config" / "providers.yaml"
    if not config_path.exists():
        # 返回默认配置
        return {
            "default_provider": "gemini",
            "providers": {
                "gemini": {
                    "enabled": True,
                    "api_base": RELAY_API_BASE,
                    "api_key": GEMINI_API_KEY,
                    "model": "gemini-2.5-flash-image",
                    "timeout": 60
                },
                "openai": {
                    "enabled": True,
                    "api_base": OPENAI_BASE_URL,
                    "api_key": OPENAI_API_KEY,
                    "model": OPENAI_MODEL,
                    "timeout": 240
                }
            },
            "routing": {
                "text_edit": "openai",
                "watermark_remove": "openai",
                "reference_edit": "openai",
                "iterative_edit": "openai",
                "default": "openai"
            },
            "fallback": {
                "enabled": True,
                "chain": {
                    "gemini": ["openai"],
                    "openai": ["gemini"]
                },
                "max_retries": 1
            },
            "session": {
                "max_context_turns": 10
            }
        }

    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    # 替换环境变量占位符
    def replace_env_vars(obj):
        if isinstance(obj, dict):
            return {k: replace_env_vars(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [replace_env_vars(item) for item in obj]
        elif isinstance(obj, str) and obj.startswith("${") and obj.endswith("}"):
            env_var = obj[2:-1]
            return os.getenv(env_var, ENV_DEFAULTS.get(env_var, ""))
        return obj

    return replace_env_vars(config)


# 加载 providers 配置
PROVIDERS_CONFIG = load_providers_config()
