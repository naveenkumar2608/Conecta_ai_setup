# backend/app/config.py
from pydantic_settings import BaseSettings
from functools import lru_cache
from app.utils.keyvault import get_secret
import os
from dotenv import load_dotenv

# Load .env into os.environ for local development
load_dotenv()


class Settings(BaseSettings):
    """Application settings (Pydantic-aware)."""

    # --- Identity & Key Vault ---
    azure_keyvault_url: str = os.getenv("AZURE_KEYVAULT_URL", "")
    azure_tenant_id: str = os.getenv("AZURE_TENANT_ID", "")
    azure_client_id: str = os.getenv("AZURE_CLIENT_ID", "")

    # --- Storage & Database ---
    blob_conn_str: str | None = None
    postgres_conn_str: str | None = None

    # --- Azure AI Search ---
    search_endpoint: str | None = None
    search_api_key: str | None = None
    search_index_name: str = "connecta-coaching-index"
    search_semantic_config: str = "connecta-semantic-config"

    # --- Azure OpenAI (Chat) ---
    openai_chat_deployment: str = "gpt-4o"
    openai_endpoint: str | None = None
    openai_api_key: str | None = None

    # --- Azure OpenAI (Embedding) ---
    openai_embedding_deployment: str = "text-embedding-3-large"
    openai_embedding_endpoint: str | None = None
    openai_embedding_api_key: str | None = None

    # --- Communication & Other Services ---
    service_bus_connection_string: str | None = None
    azure_redis_host: str | None = None
    redis_password: str | None = None
    content_safety_key: str | None = None
    translator_key: str | None = None

    # --- Application Metadata ---
    app_name: str = "Conecta AI"
    version: str = "1.0.0"
    allowed_origins: list[str] = ["https://connecta.abbott.com", "http://localhost:3000"]

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Load settings from Key Vault with fallback to environment variables.
    """
    settings = Settings()

    def safe_get(secret_name: str, env_key: str, default: str | None = None) -> str | None:
        # Priority: 1. Key Vault, 2. Env Var, 3. Default
        try:
            val = get_secret(secret_name)
            if val:
                print(f"INFO: Loaded '{secret_name}' from Key Vault.")
                return val
        except Exception:
            pass
        
        env_val = os.getenv(env_key)
        if env_val:
            print(f"INFO: Loaded '{env_key}' from Environment Variables.")
            return env_val
            
        if default:
            print(f"INFO: Using default value for '{env_key}'.")
        return default

    # ── Populate Secret Fields ───────────────────────
    
    # Storage
    settings.blob_conn_str = safe_get("BLOB-CONN-STR", "BLOB_CONN_STR")
    
    # Priority: Local .env for Postgres (requested by user)
    settings.postgres_conn_str = os.getenv("POSTGRES_CONNECTION_STRING") or safe_get("POSTGRES-CONN-STR", "POSTGRES_CONNECTION_STRING")

    # Azure Search
    settings.search_endpoint = safe_get("AZURE-SEARCH-ENDPOINT", "AZURE_SEARCH_ENDPOINT")
    settings.search_api_key = safe_get("SEARCH-AI-KEY", "AZURE_SEARCH_API_KEY")
    settings.search_index_name = safe_get("SEARCH-INDEX-NAME", "SEARCH_INDEX_NAME", settings.search_index_name)

    # OpenAI Chat (NANO)
    settings.openai_endpoint = safe_get("AZURE-OPENAI-ENDPOINT-NANO", "AZURE_OPENAI_ENDPOINT")
    settings.openai_api_key = safe_get("AZURE-OPENAI-KEY-NANO", "AZURE_OPENAI_API_KEY")
    settings.openai_chat_deployment = safe_get("AZURE-OPENAI-DEPLOYMENT-NAME-NANO", "OPENAI_CHAT_DEPLOYMENT", settings.openai_chat_deployment)

    # OpenAI Embedding
    settings.openai_embedding_endpoint = safe_get("AzureOpenAI-embedding-Endpoint", "AZURE_OPENAI_EMBEDDING_ENDPOINT")
    settings.openai_embedding_api_key = safe_get("AzureOpenAI-embedding-Key", "AZURE_OPENAI_EMBEDDING_API_KEY")
    settings.openai_embedding_deployment = safe_get("AzureOpenAI-embedding-DeploymentName", "OPENAI_EMBEDDING_DEPLOYMENT", settings.openai_embedding_deployment)

    # Secondary Services (Currently unused - disabled to avoid Key Vault errors)
    settings.service_bus_connection_string = safe_get("SERVICE-BUS-CONN-STR", "SERVICE_BUS_CONNECTION_STRING")
    # settings.azure_redis_host = safe_get("azure-redis-host", "AZURE_REDIS_HOST")
    # settings.redis_password = safe_get("azure-redis-password", "AZURE_REDIS_PASSWORD")
    # settings.content_safety_key = safe_get("content-safety-api-key", "CONTENT_SAFETY_API_KEY")
    # settings.translator_key = safe_get("translator-api-key", "TRANSLATOR_API_KEY")

    return settings
