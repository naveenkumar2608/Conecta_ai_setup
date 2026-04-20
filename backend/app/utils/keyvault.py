# backend/app/utils/keyvault.py
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)


class KeyVaultManager:
    """
    Centralized Azure Key Vault accessor.
    Uses Managed Identity in production (DefaultAzureCredential).
    Caches secrets in memory to reduce Key Vault calls.
    """

    def __init__(self, vault_url: str):
        self.vault_url = vault_url
        self.credential = DefaultAzureCredential()
        self.client = SecretClient(
            vault_url=vault_url, 
            credential=self.credential
        )
        self._cache: dict[str, str] = {}

    def get_secret(self, secret_name: str) -> str:
        """Retrieve a secret from Key Vault with in-memory caching."""
        if secret_name in self._cache:
            return self._cache[secret_name]
        
        try:
            secret = self.client.get_secret(secret_name)
            self._cache[secret_name] = secret.value
            logger.info(f"Retrieved secret: {secret_name}")
            return secret.value
        except Exception as e:
            logger.error(f"Failed to retrieve secret {secret_name}: {e}")
            raise

    def clear_cache(self):
        """Clear cached secrets (call on rotation events)."""
        self._cache.clear()


@lru_cache(maxsize=1)
def get_keyvault_manager() -> KeyVaultManager:
    """Singleton Key Vault manager."""
    import os
    vault_url = os.environ["AZURE_KEYVAULT_URL"]
    return KeyVaultManager(vault_url)
