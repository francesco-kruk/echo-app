"""Card models for API requests and responses."""

from datetime import datetime
from pydantic import BaseModel, Field
from uuid import uuid4


def generate_uuid() -> str:
    """Generate a new UUID string."""
    return str(uuid4())


def now_iso() -> str:
    """Get current UTC timestamp in ISO format."""
    return datetime.utcnow().isoformat() + "Z"


class CardBase(BaseModel):
    """Base card model with common fields."""

    front: str = Field(..., min_length=1, max_length=2000, description="Front side of the card")
    back: str = Field(..., min_length=1, max_length=2000, description="Back side of the card")


class CardCreate(CardBase):
    """Model for creating a new card."""

    pass


class CardUpdate(BaseModel):
    """Model for updating an existing card."""

    front: str | None = Field(None, min_length=1, max_length=2000, description="Front side of the card")
    back: str | None = Field(None, min_length=1, max_length=2000, description="Back side of the card")


class Card(CardBase):
    """Full card model as stored in the database."""

    id: str = Field(default_factory=generate_uuid, description="Unique identifier")
    deckId: str = Field(..., description="Parent deck ID")
    userId: str = Field(..., description="Owner user ID (partition key)")
    createdAt: str = Field(default_factory=now_iso, description="Creation timestamp")
    updatedAt: str = Field(default_factory=now_iso, description="Last update timestamp")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174001",
                "deckId": "123e4567-e89b-12d3-a456-426614174000",
                "userId": "user-001",
                "front": "Hola",
                "back": "Hello",
                "createdAt": "2025-01-01T00:00:00Z",
                "updatedAt": "2025-01-01T00:00:00Z",
            }
        }


class CardResponse(CardBase):
    """Card response model returned by API."""

    id: str
    deckId: str
    userId: str
    createdAt: str
    updatedAt: str


class CardListResponse(BaseModel):
    """Response containing a list of cards."""

    cards: list[CardResponse]
    count: int
