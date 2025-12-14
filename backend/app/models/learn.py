"""Models for deck-scoped learning endpoints."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.models.card import CardResponse


Grade = Literal["again", "hard", "good", "easy"]


class LearnNextResponse(BaseModel):
    """Response for GET /learn/next."""

    card: CardResponse | None = Field(None, description="A card due now (or treated as due now)")
    nextDueAt: str | None = Field(
        None,
        description="Earliest upcoming dueAt when no card is due now",
    )
