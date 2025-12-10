"""
Cosmos DB client and connection management.

Authentication modes:
1. Azure Managed Identity (production): Uses DefaultAzureCredential for passwordless auth
2. Azure CLI credential (local dev with Azure): Uses your `az login` session
3. Cosmos DB Emulator (local dev): Uses emulator key for local development

The authentication mode is automatically selected based on environment:
- If COSMOS_EMULATOR=true, uses emulator with default key
- Otherwise, uses DefaultAzureCredential (works with Managed Identity in Azure,
  Azure CLI locally, or other credential providers)
"""

import os
import logging
from functools import lru_cache
from azure.cosmos import CosmosClient, DatabaseProxy, ContainerProxy
from azure.cosmos.exceptions import CosmosResourceNotFoundError
from azure.identity import DefaultAzureCredential

logger = logging.getLogger(__name__)

# Cosmos DB Emulator well-known key (public, not a secret)
# https://learn.microsoft.com/en-us/azure/cosmos-db/emulator#authentication
EMULATOR_KEY = "C2y6yDjf5/R+ob0N8A7Cgv30VRDJIWEHLM+4QDU5DE2nQ9nDuVTqobD4b8mGGyPMbIZnqyMsEcaGQy67XIw/Jw=="
EMULATOR_ENDPOINT = "https://localhost:8081"


class CosmosDBSettings:
    """Settings for Cosmos DB connection."""

    def __init__(self):
        self.endpoint = os.getenv("COSMOS_ENDPOINT", "")
        self.database_name = os.getenv("COSMOS_DB_NAME", "echoapp")
        self.decks_container = os.getenv("COSMOS_DECKS_CONTAINER", "decks")
        self.cards_container = os.getenv("COSMOS_CARDS_CONTAINER", "cards")
        # Emulator mode for local development
        self.use_emulator = os.getenv("COSMOS_EMULATOR", "false").lower() == "true"

    def is_configured(self) -> bool:
        """Check if Cosmos DB is configured."""
        if self.use_emulator:
            return True  # Emulator always uses well-known endpoint
        return bool(self.endpoint)


@lru_cache()
def get_settings() -> CosmosDBSettings:
    """Get cached Cosmos DB settings."""
    return CosmosDBSettings()


_client: CosmosClient | None = None
_database: DatabaseProxy | None = None


def get_client() -> CosmosClient:
    """
    Get or create the Cosmos DB client.
    
    Uses DefaultAzureCredential for authentication, which automatically tries:
    1. Environment credentials (AZURE_CLIENT_ID, etc.)
    2. Managed Identity (in Azure)
    3. Azure CLI credential (local dev)
    4. Other credential providers in the chain
    
    For local development with the emulator, set COSMOS_EMULATOR=true.
    """
    global _client
    if _client is None:
        settings = get_settings()
        if not settings.is_configured():
            raise RuntimeError(
                "Cosmos DB is not configured. "
                "Set COSMOS_ENDPOINT environment variable, or COSMOS_EMULATOR=true for local emulator."
            )
        
        if settings.use_emulator:
            # Use emulator with well-known key (not a real secret)
            logger.info("Using Cosmos DB Emulator at %s", EMULATOR_ENDPOINT)
            _client = CosmosClient(
                EMULATOR_ENDPOINT,
                credential=EMULATOR_KEY,
                connection_verify=False  # Emulator uses self-signed cert
            )
        else:
            # Use DefaultAzureCredential for Managed Identity / Azure CLI
            logger.info("Using DefaultAzureCredential for Cosmos DB at %s", settings.endpoint)
            credential = DefaultAzureCredential()
            _client = CosmosClient(settings.endpoint, credential=credential)
    
    return _client


def get_database() -> DatabaseProxy:
    """Get or create the database proxy."""
    global _database
    if _database is None:
        settings = get_settings()
        client = get_client()
        _database = client.get_database_client(settings.database_name)
    return _database


def get_container(container_name: str) -> ContainerProxy:
    """Get a container proxy by name."""
    database = get_database()
    return database.get_container_client(container_name)


def get_decks_container() -> ContainerProxy:
    """Get the decks container."""
    settings = get_settings()
    return get_container(settings.decks_container)


def get_cards_container() -> ContainerProxy:
    """Get the cards container."""
    settings = get_settings()
    return get_container(settings.cards_container)


def verify_connection() -> bool:
    """Verify the Cosmos DB connection is working."""
    try:
        settings = get_settings()
        if not settings.is_configured():
            return False
        database = get_database()
        # Try to read database properties to verify connection
        database.read()
        return True
    except CosmosResourceNotFoundError:
        return False
    except Exception:
        return False


def close_client():
    """Close the Cosmos DB client."""
    global _client, _database
    # CosmosClient doesn't have a close() method - it manages connections internally
    # Just clear the references to allow garbage collection
    _client = None
    _database = None
