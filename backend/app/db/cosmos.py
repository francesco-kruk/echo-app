"""
Cosmos DB client and connection management.
"""

import os
from functools import lru_cache
from azure.cosmos import CosmosClient, DatabaseProxy, ContainerProxy
from azure.cosmos.exceptions import CosmosResourceNotFoundError


class CosmosDBSettings:
    """Settings for Cosmos DB connection."""

    def __init__(self):
        self.endpoint = os.getenv("COSMOS_ENDPOINT", "")
        self.key = os.getenv("COSMOS_KEY", "")
        self.database_name = os.getenv("COSMOS_DB_NAME", "echoapp")
        self.decks_container = os.getenv("COSMOS_DECKS_CONTAINER", "decks")
        self.cards_container = os.getenv("COSMOS_CARDS_CONTAINER", "cards")

    def is_configured(self) -> bool:
        """Check if Cosmos DB is configured."""
        return bool(self.endpoint and self.key)


@lru_cache()
def get_settings() -> CosmosDBSettings:
    """Get cached Cosmos DB settings."""
    return CosmosDBSettings()


_client: CosmosClient | None = None
_database: DatabaseProxy | None = None


def get_client() -> CosmosClient:
    """Get or create the Cosmos DB client."""
    global _client
    if _client is None:
        settings = get_settings()
        if not settings.is_configured():
            raise RuntimeError(
                "Cosmos DB is not configured. "
                "Set COSMOS_ENDPOINT and COSMOS_KEY environment variables."
            )
        _client = CosmosClient(settings.endpoint, settings.key)
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
