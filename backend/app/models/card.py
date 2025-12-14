"""Card models for API requests and responses."""

from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field
from uuid import uuid4

from app.srs.time import utc_now_iso


# Grade type for SRS grading
Grade = Literal["again", "hard", "good", "easy"]


def generate_uuid() -> str:
    """Generate a new UUID string."""
    return str(uuid4())


def now_iso() -> str:
    """Get current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


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

    # SRS fields (persisted)
    dueAt: str = Field(default_factory=utc_now_iso, description="Next due timestamp (UTC ISO Z)")
    easeFactor: float = Field(2.5, description="SM-2 ease factor (min 1.3)")
    repetitions: int = Field(0, description="Consecutive successful reviews")
    intervalDays: int = Field(0, description="SM-2 interval in days")
    lastReviewedAt: str | None = Field(None, description="Last review timestamp (UTC ISO Z)")
    lastGrade: Grade | None = Field(None, description="Most recent grade applied to this card")
    lastGradedAt: str | None = Field(None, description="Timestamp when last grade was applied (UTC ISO Z)")

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

    dueAt: str
    easeFactor: float
    repetitions: int
    intervalDays: int
    lastReviewedAt: str | None
    lastGrade: Grade | None
    lastGradedAt: str | None


class CardListResponse(BaseModel):
    """Response containing a list of cards."""

    cards: list[CardResponse]
    count: int
