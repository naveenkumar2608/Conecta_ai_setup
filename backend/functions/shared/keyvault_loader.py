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
    """Container for all secrets needed by ingestion pipeline."""
    openai_endpoint: str
    openai_api_key: str
    search_endpoint: str
    search_api_key: str
    postgres_connection_string: str
    service_bus_connection_string: str


_cached_secrets: IngestionSecrets | None = None


def load_secrets() -> IngestionSecrets:
    """
    Load secrets from Key Vault with module-level caching.

    NOTE: This is INTENTIONALLY separate from backend/app/utils/keyvault.py.
    Reason: Functions and Backend are separate deployment units.
    - Backend: Long-running, class-based singleton with cache invalidation
    - Functions: Short-lived, simple load-once pattern
    """
    global _cached_secrets
    if _cached_secrets is not None:
        return _cached_secrets

    vault_url = os.environ["AZURE_KEYVAULT_URL"]
    credential = DefaultAzureCredential()
    client = SecretClient(vault_url=vault_url, credential=credential)

    _cached_secrets = IngestionSecrets(
        openai_endpoint=os.environ.get(
            "AZURE_OPENAI_ENDPOINT",
            _get_secret(client, "azure-openai-endpoint"),
        ),
        openai_api_key=_get_secret(client, "azure-openai-api-key"),
        search_endpoint=os.environ.get(
            "AZURE_SEARCH_ENDPOINT",
            _get_secret(client, "azure-search-endpoint"),
        ),
        search_api_key=_get_secret(client, "azure-search-api-key"),
        postgres_connection_string=_get_secret(
            client, "postgres-connection-string"
        ),
        service_bus_connection_string=_get_secret(
            client, "service-bus-connection-string"
        ),
    )

    logger.info("All secrets loaded from Key Vault successfully")
    return _cached_secrets
