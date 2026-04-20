# backend/app/services/llm_service.py
from langchain_openai import AzureChatOpenAI
from app.config import get_settings, get_secrets
import logging

logger = logging.getLogger(__name__)


class LLMService:
    """
    Wrapper around Azure OpenAI GPT-4o.
    Provides pre-configured LangChain chat model instances
    with different temperature/token settings for each agent's needs.
    
    All calls go through this service — no direct LLM calls outside agents.
    """

    def __init__(self):
        self._settings = get_settings()
        self._secrets = get_secrets()
        self._base_kwargs = {
            "azure_endpoint": self._settings.azure_openai_endpoint,
            "api_key": self._secrets.openai_api_key,
            "api_version": "2024-06-01",
            "azure_deployment": self._settings.openai_chat_deployment,
        }

    def get_chat_model(
        self,
        temperature: float = 0.3,
        max_tokens: int = 2000,
        streaming: bool = False,
    ) -> AzureChatOpenAI:
        """
        Return a configured AzureChatOpenAI instance.
        
        Args:
            temperature: Controls randomness (0.0 = deterministic, 1.0 = creative)
            max_tokens: Maximum response tokens
            streaming: Whether to enable token-by-token streaming
        """
        return AzureChatOpenAI(
            **self._base_kwargs,
            temperature=temperature,
            max_tokens=max_tokens,
            streaming=streaming,
        )

    def get_streaming_model(
        self,
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> AzureChatOpenAI:
        """Return a streaming-enabled chat model for SSE endpoints."""
        return self.get_chat_model(
            temperature=temperature,
            max_tokens=max_tokens,
            streaming=True,
        )