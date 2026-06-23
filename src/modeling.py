"""Model factory for local Ollama and DeepSeek API runtimes."""

from langchain.chat_models import init_chat_model

from config import Settings

try:
    from langchain_deepseek import ChatDeepSeek
except ImportError:
    ChatDeepSeek = None

THINKING_DISABLED_EXTRA_BODY = {"thinking": {"type": "disabled"}}


def build_chat_model(
    model_choice: str,
    settings: Settings,
    deepseek_api_key: str | None,
):
    """Create a chat model based on runtime selection."""
    choice = model_choice.strip().lower()
    if choice == "local":
        return init_chat_model(settings.local_model)

    if choice == "deepseek":
        if not deepseek_api_key:
            raise ValueError("DEEPSEEK_API_KEY is required for DeepSeek runtime.")
        if ChatDeepSeek is None:
            raise ValueError(
                "langchain-deepseek is required for DeepSeek runtime. "
                "Install it with: pip install langchain-deepseek"
            )
        return ChatDeepSeek(
            model=settings.deepseek_model,
            api_key=deepseek_api_key,
            base_url=settings.deepseek_base_url,
            extra_body=THINKING_DISABLED_EXTRA_BODY,
        )

    raise ValueError(f"Unsupported model choice: {model_choice}")
