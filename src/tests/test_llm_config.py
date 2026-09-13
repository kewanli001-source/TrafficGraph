"""test_llm_config — 本地 Anthropic 兼容模型配置测试

所属层：tests
依赖：pytest, langchain_anthropic
对接算法层：外部大模型服务（仅实例化，不发起网络请求）
"""
from langchain_anthropic import ChatAnthropic

from src.config.llm import build_chat_model, message_content_text
from src.config.settings import settings


def test_anthropic_compatible_local_config(monkeypatch):
    """ANTHROPIC_AUTH_TOKEN 与 BASE_URL 能构造本地模型实例。"""
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "local-test-token")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://example.invalid/api/plan")
    monkeypatch.setenv("API_TIMEOUT_MS", "120000")
    monkeypatch.setattr(settings.model, "name", "test-model")

    model = build_chat_model(streaming=False, temperature=0)

    assert isinstance(model, ChatAnthropic)
    assert str(model.anthropic_api_url).rstrip("/") == "https://example.invalid/api/plan"


def test_message_content_text_extracts_final_text_blocks():
    """Anthropic 内容块只提取最终文本，忽略 thinking。"""
    content = [
        {"type": "thinking", "thinking": "内部推理"},
        {"type": "text", "text": "最终回答"},
    ]
    assert message_content_text(content) == "最终回答"


def test_message_content_text_keeps_plain_string():
    """OpenAI/DeepSeek 字符串内容保持原样。"""
    assert message_content_text("OK") == "OK"
