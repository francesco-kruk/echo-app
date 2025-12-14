"""Models for learn/agent endpoints."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.models.deck import LanguageCode


class LearnAgentSummary(BaseModel):
    """Summary of an available tutoring agent.
    
    Represents a deck that currently has due cards and can be studied.
    """
    deckId: str = Field(..., description="ID of the deck")
    deckName: str = Field(..., description="Name of the deck")
    language: LanguageCode = Field(..., description="Target language of the deck")
    agentName: str = Field(..., description="Name of the AI tutor persona")
    dueCardCount: int = Field(..., description="Number of cards currently due", ge=0)


class LearnAgentsResponse(BaseModel):
    """Response for GET /learn/agents."""
    agents: list[LearnAgentSummary] = Field(default_factory=list)
    count: int = Field(..., description="Total number of available agents", ge=0)


class LearnChatRequest(BaseModel):
    """Request for POST /learn/chat."""
    deckId: str = Field(..., description="ID of the deck to study")
    userMessage: str = Field(..., min_length=1, max_length=2000, description="User's message")


class LearnCardInfo(BaseModel):
    """Card information returned in learn responses."""
    id: str = Field(..., description="ID of the card")
    front: str = Field(..., description="Front of the card (question/prompt)")


LearnMode = Literal["card", "free"]


class LearnChatResponse(BaseModel):
    """Response for POST /learn/chat."""
    assistantMessage: str = Field(..., description="Tutor's response")
    mode: LearnMode = Field(..., description="Current learning mode: 'card' or 'free'")
    card: LearnCardInfo | None = Field(
        None,
        description="Current card info when in card mode, null in free mode"
    )


class LearnStartRequest(BaseModel):
    """Request for POST /learn/start."""
    deckId: str = Field(..., description="ID of the deck to start studying")


class LearnStartResponse(BaseModel):
    """Response for POST /learn/start.
    
    The response includes the current mode ('card' or 'free') and optional card info.
    Free mode is used when no cards are due; card mode when studying a specific card.
    """
    assistantMessage: str = Field(..., description="Initial greeting from the tutor")
    mode: LearnMode = Field(..., description="Current learning mode: 'card' or 'free'")
    card: LearnCardInfo | None = Field(
        None,
        description="Current card info when in card mode, null in free mode"
    )
    conversationId: str = Field(
        ...,
        description="Stable conversation ID for this user+deck session"
    )
    # Keep agentName and language for UI display purposes
    agentName: str = Field(..., description="Name of the AI tutor persona")
    language: LanguageCode = Field(..., description="Target language of the deck")
