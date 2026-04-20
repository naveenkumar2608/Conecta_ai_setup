# backend/app/config.py
from pydantic_settings import BaseSettings
from functools import lru_cache
from app.utils.keyvault import get_keyvault_manager
import os


class Settings(BaseSettings):
    """Application settings — loads from environment + Key Vault."""

    # Azure identifiers (from environment)
    azure_keyvault_url: str = os.getenv(
        "AZURE_KEYVAULT_URL", ""
    )
    azure_tenant_id: str = os.getenv("AZURE_TENANT_ID", "")
    azure_client_id: str = os.getenv("AZURE_CLIENT_ID", "")

    # Service endpoints (from environment)
    azure_openai_endpoint: str = os.getenv(
        "AZURE_OPENAI_ENDPOINT", ""
    )
    azure_search_endpoint: str = os.getenv(
        "AZURE_SEARCH_ENDPOINT", ""
    )
    azure_storage_account_url: str = os.getenv(
        "AZURE_STORAGE_ACCOUNT_URL", ""
    )
    azure_redis_host: str = os.getenv("AZURE_REDIS_HOST", "")
    azure_service_bus_namespace: str = os.getenv(
        "AZURE_SERVICE_BUS_NAMESPACE", ""
    )

    # Model configurations
    openai_chat_deployment: str = "gpt-4o"
    openai_embedding_deployment: str = "text-embedding-3-large"
    embedding_dimensions: int = 3072
    
    # Search configuration
    search_index_name: str = "connecta-coaching-index"
    search_semantic_config: str = "connecta-semantic-config"

    # CORS
    allowed_origins: list[str] = ["https://connecta.abbott.com"]

    class Config:
        env_file = ".env"
        case_sensitive = False


class SecretsManager:
    """Loads secrets from Azure Key Vault at startup."""

    def __init__(self):
        self._kv = get_keyvault_manager()

    @property
    def openai_api_key(self) -> str:
        return self._kv.get_secret("azure-openai-api-key")

    @property
    def search_api_key(self) -> str:
        return self._kv.get_secret("azure-search-api-key")

    @property
    def postgres_connection_string(self) -> str:
        return self._kv.get_secret("postgres-connection-string")

    @property
    def redis_password(self) -> str:
        return self._kv.get_secret("azure-redis-password")

    @property
    def service_bus_connection_string(self) -> str:
        return self._kv.get_secret("service-bus-connection-string")

    @property
    def content_safety_key(self) -> str:
        return self._kv.get_secret("content-safety-api-key")

    @property
    def translator_key(self) -> str:
        return self._kv.get_secret("translator-api-key")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


@lru_cache(maxsize=1)
def get_secrets() -> SecretsManager:
    return SecretsManager()
