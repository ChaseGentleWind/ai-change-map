"""Provider 抽象基类"""
from abc import ABC, abstractmethod
from .schemas import EditRequest, EditResponse, Capabilities


class ImageEditorProvider(ABC):
    """图像编辑 Provider 抽象基类"""

    def __init__(self, config: dict):
        """
        初始化 Provider

        Args:
            config: provider 配置字典，包含 api_base, api_key, model, timeout 等
        """
        self.config = config
        self.api_base = config.get("api_base", "").rstrip("/")
        self.api_key = config.get("api_key", "")
        self.model = config.get("model", "")
        self.timeout = config.get("timeout", 60)

    @abstractmethod
    async def edit(self, request: EditRequest) -> EditResponse:
        """
        执行图像编辑

        Args:
            request: 编辑请求

        Returns:
            EditResponse: 编辑响应
        """
        pass

    @abstractmethod
    def capabilities(self) -> Capabilities:
        """
        返回 Provider 的能力声明

        Returns:
            Capabilities: 能力对象
        """
        pass

    async def chat_edit(self, history: list, request: EditRequest) -> EditResponse:
        """
        多轮对话式编辑（默认实现：将 history 放入 request 后调用 edit）

        Args:
            history: 对话历史
            request: 当前编辑请求

        Returns:
            EditResponse: 编辑响应
        """
        request.history = history
        return await self.edit(request)
