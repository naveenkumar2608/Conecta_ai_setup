# functions/shared/keyvault_loader.py
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from dataclasses import dataclass
import os
import logging

logger = logging.getLogger(__name__)


def _get_secret(client: SecretClient, name: str) -> str:
    """Get a single secret from Key Vault."""
    try:
        return client.get_secret(name).value
    except Exception as e:
        logger.error(f"Failed to get secret '{name}': {e}")
        raise


@dataclass
class IngestionSecrets:
    """Container for all configuration needed by ingestion pipeline."""
    openai_endpoint: str
    openai_api_key: str
    openai_embedding_deployment: str
    search_endpoint: str
    search_api_key: str
    search_index_name: str
    postgres_connection_string: str
    service_bus_connection_string: str
    storage_account_url: str


_cached_secrets: IngestionSecrets | None = None


def load_secrets() -> IngestionSecrets:
    """Load config from Key Vault with environment fallback."""
    global _cached_secrets
    if _cached_secrets is not None:
        return _cached_secrets

    vault_url = os.getenv("AZURE_KEYVAULT_URL")
    if not vault_url:
        logger.warning("AZURE_KEYVAULT_URL not set. Falling back to environment variables.")
        # Minimal mock for local dev if KV is missing
        _cached_secrets = IngestionSecrets(
            openai_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
            openai_api_key=os.getenv("AZURE_OPENAI_API_KEY", ""),
            openai_embedding_deployment=os.getenv("OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-large"),
            search_endpoint=os.getenv("AZURE_SEARCH_ENDPOINT", ""),
            search_api_key=os.getenv("AZURE_SEARCH_API_KEY", ""),
            search_index_name=os.getenv("SEARCH_INDEX_NAME", "connecta-coaching-index"),
            postgres_connection_string=os.getenv("POSTGRES_CONNECTION_STRING", ""),
            service_bus_connection_string=os.getenv("SERVICE_BUS_CONNECTION_STRING", ""),
            storage_account_url=os.getenv("AZURE_STORAGE_ACCOUNT_URL", ""),
        )
        return _cached_secrets

    credential = DefaultAzureCredential()
    client = SecretClient(vault_url=vault_url, credential=credential)

    def _get(env_name: str, kv_name: str, default: str = "") -> str:
        val = os.getenv(env_name)
        if val: return val
        try:
            return client.get_secret(kv_name).value
        except Exception:
            return default

    _cached_secrets = IngestionSecrets(
        openai_endpoint=_get("AZURE_OPENAI_ENDPOINT", "azure-openai-endpoint"),
        openai_api_key=client.get_secret("azure-openai-api-key").value,
        openai_embedding_deployment=_get("OPENAI_EMBEDDING_DEPLOYMENT", "openai-embedding-deployment", "text-embedding-3-large"),
        search_endpoint=_get("AZURE_SEARCH_ENDPOINT", "azure-search-endpoint"),
        search_api_key=client.get_secret("azure-search-api-key").value,
        search_index_name=_get("SEARCH_INDEX_NAME", "search-index-name", "connecta-coaching-index"),
        postgres_connection_string=client.get_secret("postgres-connection-string").value,
        service_bus_connection_string=client.get_secret("service-bus-connection-string").value,
        storage_account_url=_get("AZURE_STORAGE_ACCOUNT_URL", "azure-storage-account-url"),
    )


    logger.info("All secrets loaded from Key Vault successfully")
    return _cached_secrets
