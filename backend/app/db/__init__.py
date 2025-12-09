"""Database module for Cosmos DB integration."""

from .cosmos import (
    get_client,
    get_database,
    get_container,
    get_decks_container,
    get_cards_container,
    get_settings,
    verify_connection,
    close_client,
)

__all__ = [
    "get_client",
    "get_database",
    "get_container",
    "get_decks_container",
    "get_cards_container",
    "get_settings",
    "verify_connection",
    "close_client",
]
