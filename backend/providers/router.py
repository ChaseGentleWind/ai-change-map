"""智能路由 — 根据任务类型选择最合适的 Provider"""
import re
from typing import Optional


class TaskRouter:
    """任务路由器"""

    def __init__(self, routing_config: dict):
        """
        初始化路由器

        Args:
            routing_config: routing 配置字典
        """
        self.config = routing_config

    def detect_task_type(
        self,
        instruction: str,
        has_reference_images: bool,
        has_parent: bool
    ) -> str:
        """
        检测任务类型

        Args:
            instruction: 用户指令
            has_reference_images: 是否有参考图
            has_parent: 是否是迭代编辑（有父记录）

        Returns:
            任务类型字符串
        """
        # 迭代编辑优先级最高
        if has_parent:
            return "iterative_edit"

        # 参考图编辑
        if has_reference_images:
            return "reference_edit"

        # 文字编辑关键词
        text_keywords = ["文字", "字", "text", "写", "改成", "替换", "修改文本"]
        if any(kw in instruction for kw in text_keywords):
            return "text_edit"

        # 去水印关键词
        watermark_keywords = ["水印", "logo", "标志", "去掉", "去除", "移除", "删除"]
        if any(kw in instruction for kw in watermark_keywords):
            return "watermark_remove"

        return "default"

    def select_provider(
        self,
        instruction: str,
        has_reference_images: bool = False,
        has_parent: bool = False,
        manual_provider: Optional[str] = None
    ) -> tuple[str, str]:
        """
        选择 Provider

        Args:
            instruction: 用户指令
            has_reference_images: 是否有参考图
            has_parent: 是否是迭代编辑
            manual_provider: 用户手动指定的 provider（优先级最高）

        Returns:
            (provider_name, task_type)
        """
        # 手动指定优先
        if manual_provider:
            task_type = self.detect_task_type(instruction, has_reference_images, has_parent)
            return manual_provider, task_type

        # 检测任务类型
        task_type = self.detect_task_type(instruction, has_reference_images, has_parent)

        # 根据任务类型选择 provider
        provider = self.config.get(task_type, self.config.get("default", "gemini"))

        return provider, task_type
