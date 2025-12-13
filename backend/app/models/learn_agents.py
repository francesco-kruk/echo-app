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
    cardId: str | None = Field(None, description="Optional card ID to study (uses current due card if not provided)")


class LearnChatResponse(BaseModel):
    """Response for POST /learn/chat."""
    assistantMessage: str = Field(..., description="Tutor's response")
    canGrade: bool = Field(..., description="Whether the user can now submit a grade")
    revealed: bool = Field(..., description="Whether the answer was revealed")
    isCorrect: bool = Field(..., description="Whether the user's answer was correct")
    cardId: str = Field(..., description="ID of the current card being studied")
    cardFront: str = Field(..., description="Front of the current card (question/prompt)")


class LearnStartRequest(BaseModel):
    """Request for POST /learn/start."""
    deckId: str = Field(..., description="ID of the deck to start studying")


class LearnStartResponse(BaseModel):
    """Response for POST /learn/start."""
    cardId: str = Field(..., description="ID of the current card to study")
    cardFront: str = Field(..., description="Front of the card (question/prompt)")
    assistantMessage: str = Field(..., description="Initial greeting from the tutor")
    agentName: str = Field(..., description="Name of the AI tutor persona")
    language: LanguageCode = Field(..., description="Target language of the deck")
