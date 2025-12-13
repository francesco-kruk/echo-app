"""Repository for Card CRUD operations."""

from datetime import datetime, timezone
from azure.cosmos import ContainerProxy
from azure.cosmos.exceptions import CosmosResourceNotFoundError

from app.db import get_cards_container
from app.models import Card, CardCreate, CardUpdate
from app.repositories.deck_repository import DeckNotFoundError, get_deck_repository

from app.srs.time import utc_now_iso


class CardNotFoundError(Exception):
    """Raised when a card is not found."""

    pass


class CardRepository:
    """Repository for Card database operations."""

    def __init__(self, container: ContainerProxy | None = None):
        """Initialize the repository with an optional container."""
        self._container = container

    @property
    def container(self) -> ContainerProxy:
        """Get the container, lazily initializing if needed."""
        if self._container is None:
            self._container = get_cards_container()
        return self._container

    def list_by_deck(self, deck_id: str, user_id: str) -> list[Card]:
        """List all cards in a deck."""
        query = "SELECT * FROM c WHERE c.deckId = @deckId AND c.userId = @userId ORDER BY c.createdAt DESC"
        parameters = [
            {"name": "@deckId", "value": deck_id},
            {"name": "@userId", "value": user_id},
        ]

        items = list(
            self.container.query_items(
                query=query,
                parameters=parameters,
                partition_key=user_id,
            )
        )
        return [Card(**item) for item in items]

    def get_by_id(self, card_id: str, user_id: str) -> Card:
        """Get a card by ID and user ID."""
        try:
            item = self.container.read_item(item=card_id, partition_key=user_id)
            return Card(**item)
        except CosmosResourceNotFoundError:
            raise CardNotFoundError(f"Card with ID {card_id} not found")

    def create(self, deck_id: str, user_id: str, card_create: CardCreate) -> Card:
        """Create a new card in a deck."""
        # Verify deck exists and belongs to user
        deck_repo = get_deck_repository()
        if not deck_repo.exists(deck_id, user_id):
            raise DeckNotFoundError(f"Deck with ID {deck_id} not found")

        card = Card(
            deckId=deck_id,
            userId=user_id,
            front=card_create.front,
            back=card_create.back,
        )
        created_item = self.container.create_item(body=card.model_dump())
        return Card(**created_item)

    def update(self, card_id: str, user_id: str, card_update: CardUpdate) -> Card:
        """Update an existing card."""
        # First, get the existing card
        existing = self.get_by_id(card_id, user_id)

        # Apply updates
        update_data = card_update.model_dump(exclude_unset=True)
        if update_data:
            for key, value in update_data.items():
                setattr(existing, key, value)
            existing.updatedAt = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        # Replace the item
        updated_item = self.container.replace_item(
            item=card_id,
            body=existing.model_dump(),
        )
        return Card(**updated_item)

    def replace(self, card: Card) -> Card:
        """Replace (persist) a full card document."""
        updated_item = self.container.replace_item(
            item=card.id,
            body=card.model_dump(),
        )
        return Card(**updated_item)

    def get_next_due_for_deck(self, user_id: str, deck_id: str, now_iso: str) -> Card | None:
        """Return the next due card for a deck.

        Legacy cards missing SRS fields are treated as due now and are backfilled.
        """
        # 1) Backfill legacy cards missing dueAt (treated as due now)
        legacy_query = (
            "SELECT TOP 1 * FROM c "
            "WHERE c.deckId = @deckId AND c.userId = @userId AND NOT IS_DEFINED(c.dueAt)"
        )
        legacy_params = [
            {"name": "@deckId", "value": deck_id},
            {"name": "@userId", "value": user_id},
        ]

        legacy_items = list(
            self.container.query_items(
                query=legacy_query,
                parameters=legacy_params,
                partition_key=user_id,
            )
        )
        if legacy_items:
            card = Card(**legacy_items[0])
            # Backfill defaults + touch updatedAt
            card.dueAt = utc_now_iso()
            card.updatedAt = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            return self.replace(card)

        # 2) Select due cards by dueAt ascending
        due_query = (
            "SELECT TOP 1 * FROM c "
            "WHERE c.deckId = @deckId AND c.userId = @userId AND c.dueAt <= @nowIso "
            "ORDER BY c.dueAt ASC"
        )
        due_params = [
            {"name": "@deckId", "value": deck_id},
            {"name": "@userId", "value": user_id},
            {"name": "@nowIso", "value": now_iso},
        ]

        items = list(
            self.container.query_items(
                query=due_query,
                parameters=due_params,
                partition_key=user_id,
            )
        )
        if not items:
            return None
        return Card(**items[0])

    def get_next_due_at_for_deck(self, user_id: str, deck_id: str) -> str | None:
        """Return earliest dueAt in the selected deck (or None if no cards)."""
        # If any legacy cards exist, treat them as due now.
        legacy_query = (
            "SELECT TOP 1 VALUE c.id FROM c "
            "WHERE c.deckId = @deckId AND c.userId = @userId AND NOT IS_DEFINED(c.dueAt)"
        )
        legacy_params = [
            {"name": "@deckId", "value": deck_id},
            {"name": "@userId", "value": user_id},
        ]
        legacy_items = list(
            self.container.query_items(
                query=legacy_query,
                parameters=legacy_params,
                partition_key=user_id,
            )
        )
        if legacy_items:
            return utc_now_iso()

        query = (
            "SELECT TOP 1 VALUE c.dueAt FROM c "
            "WHERE c.deckId = @deckId AND c.userId = @userId AND IS_DEFINED(c.dueAt) "
            "ORDER BY c.dueAt ASC"
        )
        parameters = [
            {"name": "@deckId", "value": deck_id},
            {"name": "@userId", "value": user_id},
        ]

        items = list(
            self.container.query_items(
                query=query,
                parameters=parameters,
                partition_key=user_id,
            )
        )
        if not items:
            return None
        return items[0]

    def count_due_for_deck(self, user_id: str, deck_id: str, now_iso: str) -> int:
        """Count the number of cards currently due for a deck.
        
        Args:
            user_id: The user ID
            deck_id: The deck ID
            now_iso: Current timestamp in ISO format
            
        Returns:
            Number of cards currently due (including legacy cards without dueAt)
        """
        # Count legacy cards without dueAt (treated as due now)
        legacy_query = (
            "SELECT VALUE COUNT(1) FROM c "
            "WHERE c.deckId = @deckId AND c.userId = @userId AND NOT IS_DEFINED(c.dueAt)"
        )
        legacy_params = [
            {"name": "@deckId", "value": deck_id},
            {"name": "@userId", "value": user_id},
        ]
        legacy_count = list(
            self.container.query_items(
                query=legacy_query,
                parameters=legacy_params,
                partition_key=user_id,
            )
        )[0]

        # Count cards with dueAt <= now
        due_query = (
            "SELECT VALUE COUNT(1) FROM c "
            "WHERE c.deckId = @deckId AND c.userId = @userId AND c.dueAt <= @nowIso"
        )
        due_params = [
            {"name": "@deckId", "value": deck_id},
            {"name": "@userId", "value": user_id},
            {"name": "@nowIso", "value": now_iso},
        ]
        due_count = list(
            self.container.query_items(
                query=due_query,
                parameters=due_params,
                partition_key=user_id,
            )
        )[0]

        return legacy_count + due_count

    def delete(self, card_id: str, user_id: str) -> None:
        """Delete a card by ID."""
        try:
            self.container.delete_item(item=card_id, partition_key=user_id)
        except CosmosResourceNotFoundError:
            raise CardNotFoundError(f"Card with ID {card_id} not found")

    def delete_by_deck(self, deck_id: str, user_id: str) -> int:
        """Delete all cards in a deck. Returns count of deleted cards."""
        cards = self.list_by_deck(deck_id, user_id)
        for card in cards:
            self.container.delete_item(item=card.id, partition_key=user_id)
        return len(cards)


# Singleton instance
_card_repository: CardRepository | None = None


def get_card_repository() -> CardRepository:
    """Get the card repository singleton."""
    global _card_repository
    if _card_repository is None:
        _card_repository = CardRepository()
    return _card_repository
