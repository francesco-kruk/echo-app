"""Deck models for API requests and responses."""

from datetime import datetime
from pydantic import BaseModel, Field
from uuid import uuid4


def generate_uuid() -> str:
    """Generate a new UUID string."""
    return str(uuid4())


def now_iso() -> str:
    """Get current UTC timestamp in ISO format."""
    return datetime.utcnow().isoformat() + "Z"


class DeckBase(BaseModel):
    """Base deck model with common fields."""

    name: str = Field(..., min_length=1, max_length=200, description="Name of the deck")
    description: str | None = Field(None, max_length=1000, description="Optional description")


class DeckCreate(DeckBase):
    """Model for creating a new deck."""

    pass


class DeckUpdate(BaseModel):
    """Model for updating an existing deck."""

    name: str | None = Field(None, min_length=1, max_length=200, description="Name of the deck")
    description: str | None = Field(None, max_length=1000, description="Optional description")


class Deck(DeckBase):
    """Full deck model as stored in the database."""

    id: str = Field(default_factory=generate_uuid, description="Unique identifier")
    userId: str = Field(..., description="Owner user ID (partition key)")
    createdAt: str = Field(default_factory=now_iso, description="Creation timestamp")
    updatedAt: str = Field(default_factory=now_iso, description="Last update timestamp")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "userId": "user-001",
                "name": "Spanish Vocabulary",
                "description": "Basic Spanish words and phrases",
                "createdAt": "2025-01-01T00:00:00Z",
                "updatedAt": "2025-01-01T00:00:00Z",
            }
        }


class DeckResponse(DeckBase):
    """Deck response model returned by API."""

    id: str
    userId: str
    createdAt: str
    updatedAt: str


class DeckListResponse(BaseModel):
    """Response containing a list of decks."""

    decks: list[DeckResponse]
    count: int
