"""TaskRouter 单元测试"""
import pytest
from providers.router import TaskRouter

_ROUTING = {
    "text_edit": "openai",
    "watermark_remove": "openai",
    "reference_edit": "openai",
    "iterative_edit": "openai",
    "default": "openai",
}


@pytest.fixture
def router():
    return TaskRouter(_ROUTING)


@pytest.mark.parametrize("instruction,has_ref,has_parent,expected", [
    ("普通编辑改下背景", False, True,  "iterative_edit"),  # parent 优先级最高
    ("换成参考图风格",  True,  False, "reference_edit"),
    ("把文字改成Hello", False, False, "text_edit"),
    ("text style",      False, False, "text_edit"),
    ("修改文本内容",    False, False, "text_edit"),
    ("去掉水印",        False, False, "watermark_remove"),
    ("移除logo标志",    False, False, "watermark_remove"),
    ("修改背景为蓝色",  False, False, "default"),
])
def test_detect_task_type(router, instruction, has_ref, has_parent, expected):
    assert router.detect_task_type(instruction, has_ref, has_parent) == expected


def test_parent_beats_reference(router):
    """有 parent 时即使有参考图也路由到 iterative_edit。"""
    assert router.detect_task_type("换参考图", has_reference_images=True, has_parent=True) == "iterative_edit"


def test_select_provider_returns_config_value(router):
    provider, task_type = router.select_provider("修改背景颜色")
    assert provider == "openai"
    assert task_type == "default"


def test_manual_provider_overrides_routing(router):
    provider, _ = router.select_provider("修改背景颜色", manual_provider="gemini")
    assert provider == "gemini"


def test_missing_task_key_falls_back_to_default(router):
    """routing 表中不存在 task_type 时回落到 default。"""
    r = TaskRouter({"default": "seededit"})
    provider, _ = r.select_provider("修改背景颜色")
    assert provider == "seededit"
