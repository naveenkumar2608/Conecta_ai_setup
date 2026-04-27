# backend/app/config.py
from pydantic_settings import BaseSettings
from functools import lru_cache
from app.utils.keyvault import get_keyvault_manager
import os
from dotenv import load_dotenv

# Load .env into os.environ for local development
load_dotenv()



class Settings(BaseSettings):
    """Application settings — loads minimal config from environment."""

    # Key Vault identifier (MUST be in environment/.env)
    azure_keyvault_url: str = os.getenv("AZURE_KEYVAULT_URL", "")
    
    # Identity identifiers (optional if using System Managed Identity)
    azure_tenant_id: str = os.getenv("AZURE_TENANT_ID", "")
    azure_client_id: str = os.getenv("AZURE_CLIENT_ID", "")

    # Application Metadata
    app_name: str = "Conecta AI"
    version: str = "1.0.0"

    # Search configuration (non-secret)
    search_index_name: str = "connecta-coaching-index"
    search_semantic_config: str = "connecta-semantic-config"

    # CORS
    allowed_origins: list[str] = ["https://connecta.abbott.com", "http://localhost:3000"]

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"



class SecretsManager:
    """Loads all credentials and endpoints from Azure Key Vault at startup."""

    def __init__(self):
        settings = get_settings()
        self._kv = get_keyvault_manager(settings.azure_keyvault_url)


    def _get_env_or_kv(self, env_name: str, kv_name: str, default: str = "") -> str:
        """Helper to check environment first (for local dev) then Key Vault."""
        val = os.getenv(env_name)
        if val:
            return val
        try:
            return self._kv.get_secret(kv_name)
        except Exception:
            return default

    # --- Endpoints ---
    @property
    def azure_openai_endpoint(self) -> str:
        return self._get_env_or_kv("AZURE_OPENAI_ENDPOINT", "AzureOpenAI-embedding-Endpoint")

    @property
    def azure_search_endpoint(self) -> str:
        return self._get_env_or_kv("AZURE_SEARCH_ENDPOINT", "AZURE-SEARCH-ENDPOINT")

    @property
    def azure_storage_account_url(self) -> str:
        # Defaults to account URL if provided, but we can also handle BLOB-CONN-STR
        return self._get_env_or_kv("AZURE_STORAGE_ACCOUNT_URL", "azure-storage-account-url")

    @property
    def blob_connection_string(self) -> str:
        return self._get_env_or_kv("BLOB_CONN_STR", "BLOB-CONN-STR")

    @property
    def azure_redis_host(self) -> str:
        return self._get_env_or_kv("AZURE_REDIS_HOST", "azure-redis-host")

    # --- API Keys & Connection Strings ---
    @property
    def openai_api_key(self) -> str:
        return self._get_env_or_kv("AZURE_OPENAI_API_KEY", "AzureOpenAI-embedding-Key")

    @property
    def search_api_key(self) -> str:
        return self._get_env_or_kv("AZURE_SEARCH_API_KEY", "SEARCH-AI-KEY")

    @property
    def postgres_connection_string(self) -> str:
        return self._get_env_or_kv("POSTGRES_CONNECTION_STRING", "POSTGRES-CONN-STR")

    @property
    def redis_password(self) -> str:
        return self._get_env_or_kv("AZURE_REDIS_PASSWORD", "azure-redis-password")

    @property
    def service_bus_connection_string(self) -> str:
        return self._get_env_or_kv("SERVICE_BUS_CONNECTION_STRING", "SERVICE-BUS-CONN-STR")

    @property
    def content_safety_key(self) -> str:
        return self._get_env_or_kv("CONTENT_SAFETY_API_KEY", "content-safety-api-key")

    @property
    def translator_key(self) -> str:
        return self._get_env_or_kv("TRANSLATOR_API_KEY", "translator-api-key")

    # --- Deployment Names & Model Configuration ---
    @property
    def openai_chat_deployment(self) -> str:
        return self._get_env_or_kv("OPENAI_CHAT_DEPLOYMENT", "openai-chat-deployment", "gpt-4o")

    @property
    def openai_embedding_deployment(self) -> str:
        return self._get_env_or_kv("OPENAI_EMBEDDING_DEPLOYMENT", "AzureOpenAI-embedding-DeploymentName", "text-embedding-3-large")

    @property
    def search_index_name(self) -> str:
        return self._get_env_or_kv("SEARCH_INDEX_NAME", "SEARCH-INDEX-NAME", "connecta-coaching-index")


    @property
    def embedding_dimensions(self) -> int:
        val = self._get_env_or_kv("EMBEDDING_DIMENSIONS", "embedding-dimensions", "3072")
        return int(val)

    # --- Auth Identifiers ---
    @property
    def azure_tenant_id(self) -> str:
        return self._get_env_or_kv("AZURE_TENANT_ID", "azure-tenant-id")

    @property
    def azure_client_id(self) -> str:
        return self._get_env_or_kv("AZURE_CLIENT_ID", "azure-client-id")



@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


@lru_cache(maxsize=1)
def get_secrets() -> SecretsManager:
    return SecretsManager()
