"""llm — 统一创建 OpenAI、DeepSeek 与 Anthropic 兼容 ChatModel

所属层：config
依赖：langchain_openai, langchain_anthropic, src.config.settings
对接算法层：外部大模型服务
"""
import os
from typing import Any, Optional

from src.config.settings import settings


def message_content_text(content: Any) -> str:
    """把 Anthropic 内容块统一转换为纯文本。

    Args:
        content: LangChain 消息 content，可能是字符串或内容块列表。

    Returns:
        仅包含最终文本块的内容；thinking 块会被忽略。
    """
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return str(content or "")

    parts = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
            continue
        if isinstance(block, dict):
            if block.get("type") == "thinking":
                continue
            text = block.get("text")
            if text:
                parts.append(str(text))
            continue
        text = getattr(block, "text", None)
        if text:
            parts.append(str(text))
    return "\n".join(parts)


def _timeout_seconds() -> float:
    """读取 API_TIMEOUT_MS 并转换为秒。"""
    raw = os.getenv("API_TIMEOUT_MS", "120000")
    try:
        return max(1.0, int(raw) / 1000)
    except ValueError:
        return 120.0


def build_chat_model(
    *,
    streaming: bool,
    temperature: Optional[float] = None,
) -> Any:
    """按环境配置创建聊天模型。

    Args:
        streaming: 是否启用流式输出。
        temperature: 可选温度覆盖。

    Returns:
        LangChain ChatModel 实例。

    Raises:
        ValueError: API 凭据缺失。
        ImportError: 对应供应商依赖未安装。
    """
    provider = os.getenv("LLM_PROVIDER", settings.model.provider).strip().lower()
    model_name = settings.model.name
    resolved_temperature = settings.model.temperature if temperature is None else temperature

    if provider == "deepseek":
        from langchain_openai import ChatOpenAI

        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("缺少 DEEPSEEK_API_KEY")
        return ChatOpenAI(
            model=model_name,
            temperature=resolved_temperature,
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
            api_key=api_key,
            streaming=streaming,
            timeout=_timeout_seconds(),
            max_tokens=settings.model.max_tokens,
            extra_body={"thinking": {"type": "disabled"}},
        )

    if provider in {"anthropic", "ark", "anthropic-compatible"}:
        from langchain_anthropic import ChatAnthropic

        auth_token = os.getenv("ANTHROPIC_AUTH_TOKEN")
        api_key = os.getenv("ANTHROPIC_API_KEY") or auth_token
        if not api_key:
            raise ValueError("缺少 ANTHROPIC_AUTH_TOKEN 或 ANTHROPIC_API_KEY")

        base_url = os.getenv("ANTHROPIC_BASE_URL") or settings.model.base_url or None
        default_headers = {}
        if auth_token:
            default_headers["Authorization"] = f"Bearer {auth_token}"

        return ChatAnthropic(
            model=model_name,
            temperature=resolved_temperature,
            streaming=streaming,
            timeout=_timeout_seconds(),
            max_tokens_to_sample=settings.model.max_tokens,
            api_key=api_key,
            base_url=base_url,
            default_headers=default_headers or None,
        )

    from langchain_openai import ChatOpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("缺少 OPENAI_API_KEY")
    return ChatOpenAI(
        model=model_name,
        temperature=resolved_temperature,
        api_key=api_key,
        base_url=os.getenv("OPENAI_BASE_URL") or settings.model.base_url or None,
        streaming=streaming,
        timeout=_timeout_seconds(),
        max_tokens=settings.model.max_tokens,
    )
