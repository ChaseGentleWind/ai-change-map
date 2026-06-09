"""Provider 数据契约 — 统一的请求/响应格式"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class EditRequest:
    """编辑请求"""
    main_image: bytes                          # 主图（必填）
    instruction: str                           # 自然语言编辑指令
    reference_images: List[bytes] = field(default_factory=list)  # 参考图（可选）
    mask: Optional[bytes] = None               # 涂抹 mask（可选）
    history: List[Dict[str, Any]] = field(default_factory=list)  # 多轮对话历史
    output_count: int = 1                      # 生成数量
    extra: Dict[str, Any] = field(default_factory=dict)  # 扩展字段


@dataclass
class TokenUsage:
    """Token 用量统计"""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


@dataclass
class EditResponse:
    """编辑响应"""
    images: List[bytes]                        # 编辑结果图片
    usage: TokenUsage                          # token 用量
    provider: str                              # 实际使用的 provider
    model: str                                 # 实际使用的模型
    raw_response: Dict[str, Any] = field(default_factory=dict)  # 原始响应（调试用）


@dataclass
class Capabilities:
    """Provider 能力声明"""
    supports_multi_image: bool = False         # 是否支持参考图
    supports_mask: bool = False                # 是否支持 mask
    supports_chat: bool = False                # 是否支持多轮对话
    max_input_size_mb: int = 20                # 最大输入图片大小
    max_output_count: int = 4                  # 单次最多生成几张
