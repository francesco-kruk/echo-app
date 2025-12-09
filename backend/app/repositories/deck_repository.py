"""Repository for Deck CRUD operations."""

from datetime import datetime
from azure.cosmos import ContainerProxy
from azure.cosmos.exceptions import CosmosResourceNotFoundError

from app.db import get_decks_container
from app.models import Deck, DeckCreate, DeckUpdate


class DeckNotFoundError(Exception):
    """Raised when a deck is not found."""

    pass


class DeckRepository:
    """Repository for Deck database operations."""

    def __init__(self, container: ContainerProxy | None = None):
        """Initialize the repository with an optional container."""
        self._container = container

    @property
    def container(self) -> ContainerProxy:
        """Get the container, lazily initializing if needed."""
        if self._container is None:
            self._container = get_decks_container()
        return self._container

    async def list_by_user(self, user_id: str) -> list[Deck]:
        """List all decks for a user."""
        query = "SELECT * FROM c WHERE c.userId = @userId ORDER BY c.createdAt DESC"
        parameters = [{"name": "@userId", "value": user_id}]

        items = list(
            self.container.query_items(
                query=query,
                parameters=parameters,
                partition_key=user_id,
            )
        )
        return [Deck(**item) for item in items]

    async def get_by_id(self, deck_id: str, user_id: str) -> Deck:
        """Get a deck by ID and user ID."""
        try:
            item = self.container.read_item(item=deck_id, partition_key=user_id)
            return Deck(**item)
        except CosmosResourceNotFoundError:
            raise DeckNotFoundError(f"Deck with ID {deck_id} not found")

    async def create(self, deck_create: DeckCreate, user_id: str) -> Deck:
        """Create a new deck."""
        deck = Deck(
            userId=user_id,
            name=deck_create.name,
            description=deck_create.description,
        )
        created_item = self.container.create_item(body=deck.model_dump())
        return Deck(**created_item)

    async def update(self, deck_id: str, user_id: str, deck_update: DeckUpdate) -> Deck:
        """Update an existing deck."""
        # First, get the existing deck
        existing = await self.get_by_id(deck_id, user_id)

        # Apply updates
        update_data = deck_update.model_dump(exclude_unset=True)
        if update_data:
            for key, value in update_data.items():
                setattr(existing, key, value)
            existing.updatedAt = datetime.utcnow().isoformat() + "Z"
            # Replace the item only if there are updates
            updated_item = self.container.replace_item(
                item=deck_id,
                body=existing.model_dump(),
            )
            return Deck(**updated_item)
        else:
            # No changes, return the existing deck
            return existing
    async def delete(self, deck_id: str, user_id: str) -> None:
        """Delete a deck by ID."""
        try:
            self.container.delete_item(item=deck_id, partition_key=user_id)
        except CosmosResourceNotFoundError:
            raise DeckNotFoundError(f"Deck with ID {deck_id} not found")

    async def exists(self, deck_id: str, user_id: str) -> bool:
        """Check if a deck exists."""
        try:
            await self.get_by_id(deck_id, user_id)
            return True
        except DeckNotFoundError:
            return False


# Singleton instance
_deck_repository: DeckRepository | None = None


def get_deck_repository() -> DeckRepository:
    """Get the deck repository singleton."""
    global _deck_repository
    if _deck_repository is None:
        _deck_repository = DeckRepository()
    return _deck_repository
