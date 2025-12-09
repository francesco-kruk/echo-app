"""Repository for Card CRUD operations."""

from datetime import datetime, timezone
from azure.cosmos import ContainerProxy
from azure.cosmos.exceptions import CosmosResourceNotFoundError

from app.db import get_cards_container
from app.models import Card, CardCreate, CardUpdate
from app.repositories.deck_repository import DeckNotFoundError, get_deck_repository


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

    async def list_by_deck(self, deck_id: str, user_id: str) -> list[Card]:
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

    async def get_by_id(self, card_id: str, user_id: str) -> Card:
        """Get a card by ID and user ID."""
        try:
            item = self.container.read_item(item=card_id, partition_key=user_id)
            return Card(**item)
        except CosmosResourceNotFoundError:
            raise CardNotFoundError(f"Card with ID {card_id} not found")

    async def create(self, deck_id: str, user_id: str, card_create: CardCreate) -> Card:
        """Create a new card in a deck."""
        # Verify deck exists and belongs to user
        deck_repo = get_deck_repository()
        if not await deck_repo.exists(deck_id, user_id):
            raise DeckNotFoundError(f"Deck with ID {deck_id} not found")

        card = Card(
            deckId=deck_id,
            userId=user_id,
            front=card_create.front,
            back=card_create.back,
        )
        created_item = self.container.create_item(body=card.model_dump())
        return Card(**created_item)

    async def update(self, card_id: str, user_id: str, card_update: CardUpdate) -> Card:
        """Update an existing card."""
        # First, get the existing card
        existing = await self.get_by_id(card_id, user_id)

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

    async def delete(self, card_id: str, user_id: str) -> None:
        """Delete a card by ID."""
        try:
            self.container.delete_item(item=card_id, partition_key=user_id)
        except CosmosResourceNotFoundError:
            raise CardNotFoundError(f"Card with ID {card_id} not found")

    async def delete_by_deck(self, deck_id: str, user_id: str) -> int:
        """Delete all cards in a deck. Returns count of deleted cards."""
        cards = await self.list_by_deck(deck_id, user_id)
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
