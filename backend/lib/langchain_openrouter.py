import os
from typing import Optional

from langchain_openai import ChatOpenAI
from pydantic import Field, SecretStr
from langchain_core.utils.utils import secret_from_env


class ChatOpenRouter(ChatOpenAI):
    """
    Custom LangChain wrapper for OpenRouter API.
    """

    openai_api_key: Optional[SecretStr] = Field(
        alias="api_key",
        default_factory=secret_from_env("OPENROUTER_API_KEY", default=None),
    )

    @property
    def lc_secrets(self) -> dict[str, str]:
        return {"openai_api_key": "OPENROUTER_API_KEY"}

    def __init__(self, openai_api_key: Optional[str] = None, **kwargs):
        openai_api_key = openai_api_key or os.environ.get("OPENROUTER_API_KEY")
        super().__init__(
            base_url="https://openrouter.ai/api/v1",
            openai_api_key=openai_api_key,
            **kwargs,
        )


def get_llm(model_name: str | None = None, temperature: float = 0.6):
    model = model_name or os.getenv("DEFAULT_MODEL", "anthropic/claude-sonnet-4")
    return ChatOpenRouter(
        model_name=model,
        temperature=temperature,
        max_tokens=1600,
    )
