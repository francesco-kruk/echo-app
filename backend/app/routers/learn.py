"""Learn (SRS) API router."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import CurrentUser, get_current_user
from app.models import (
    CardResponse,
    LearnNextResponse,
    LearnReviewRequest,
    LearnAgentSummary,
    LearnAgentsResponse,
    LearnChatRequest,
    LearnChatResponse,
    LearnStartRequest,
    LearnStartResponse,
)
from app.repositories import (
    CardNotFoundError,
    DeckNotFoundError,
    get_card_repository,
    get_deck_repository,
)
from app.srs.sm2 import SM2State, apply_sm2
from app.srs.time import add_days_iso, add_hours_iso, add_minutes_iso, parse_iso_z, utc_now_iso
from app.agents.personas import SUPPORTED_LANGUAGES

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/learn", tags=["learn"])


Grade = Literal["again", "hard", "good", "easy"]


_GRADE_TO_QUALITY: dict[Grade, int] = {
    "again": 0,
    "hard": 3,
    "good": 4,
    "easy": 5,
}


def _due_at_for_grade(now: datetime, grade: Grade) -> str:
    if grade == "again":
        return add_minutes_iso(now, 2)
    if grade == "hard":
        return add_minutes_iso(now, 10)
    if grade == "good":
        return add_hours_iso(now, 24)
    if grade == "easy":
        return add_days_iso(now, 4)
    raise ValueError(f"Invalid grade: {grade}")


async def _verify_deck_ownership(deck_id: str, user_id: str) -> None:
    deck_repo = get_deck_repository()
    if not deck_repo.exists(deck_id, user_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deck with ID {deck_id} not found",
        )


@router.get("/next", response_model=LearnNextResponse)
async def learn_next(
    deckId: str, user: Annotated[CurrentUser, Depends(get_current_user)]
) -> LearnNextResponse:
    """Return the next card due for a deck."""
    await _verify_deck_ownership(deckId, user.user_id)

    card_repo = get_card_repository()
    now_iso = utc_now_iso()

    card = card_repo.get_next_due_for_deck(user.user_id, deckId, now_iso)
    if card is not None:
        return LearnNextResponse(card=CardResponse(**card.model_dump()), nextDueAt=None)

    next_due_at = card_repo.get_next_due_at_for_deck(user.user_id, deckId)
    return LearnNextResponse(card=None, nextDueAt=next_due_at)


@router.post("/review", response_model=CardResponse)
async def learn_review(
    req: LearnReviewRequest, user: Annotated[CurrentUser, Depends(get_current_user)]
) -> CardResponse:
    """Apply a review grade to a card and update its SRS fields."""
    await _verify_deck_ownership(req.deckId, user.user_id)

    card_repo = get_card_repository()
    try:
        card = card_repo.get_by_id(req.cardId, user.user_id)
    except CardNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Card with ID {req.cardId} not found",
        )

    if card.deckId != req.deckId:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Card with ID {req.cardId} not found in deck {req.deckId}",
        )

    grade: Grade = req.grade
    if grade not in _GRADE_TO_QUALITY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid grade: {req.grade}",
        )

    now_dt = parse_iso_z(utc_now_iso())

    # Update SM-2 state (EF/reps/intervalDays)
    state = SM2State(
        ease_factor=card.easeFactor,
        repetitions=card.repetitions,
        interval_days=card.intervalDays,
    )
    new_state = apply_sm2(state, _GRADE_TO_QUALITY[grade])

    card.easeFactor = new_state.ease_factor
    card.repetitions = new_state.repetitions
    card.intervalDays = new_state.interval_days

    # Fixed due scheduling
    card.lastReviewedAt = utc_now_iso()
    card.dueAt = _due_at_for_grade(now_dt, grade)
    card.updatedAt = utc_now_iso()  # match the same ISO-Z style for SRS touches

    # Reset agent session state after grading
    try:
        from app.agents.session_store import get_session_store
        session_store = get_session_store()
        session_store.reset(user.user_id, req.deckId)
        logger.info(
            f"Grade submitted: user={user.user_id}, deck={req.deckId}, "
            f"card={req.cardId}, grade={req.grade}, new_due_at={card.dueAt}"
        )
    except Exception as e:
        logger.warning(f"Failed to reset agent session: {e}")

    updated = card_repo.replace(card)
    return CardResponse(**updated.model_dump())


# =============================================================================
# Agent-based learning endpoints
# =============================================================================


@router.get("/agents", response_model=LearnAgentsResponse)
async def get_available_agents(
    user: Annotated[CurrentUser, Depends(get_current_user)]
) -> LearnAgentsResponse:
    """List available tutoring agents (decks with due cards).
    
    Returns only decks that currently have at least one card due for review.
    Each deck maps to an AI tutor persona based on its language.
    """
    deck_repo = get_deck_repository()
    card_repo = get_card_repository()
    now_iso = utc_now_iso()

    # Get all user's decks
    decks = deck_repo.list_by_user(user.user_id)

    agents: list[LearnAgentSummary] = []
    for deck in decks:
        # Check if deck has due cards
        due_count = card_repo.count_due_for_deck(user.user_id, deck.id, now_iso)
        if due_count > 0:
            # Get the agent persona for this language
            language_info = SUPPORTED_LANGUAGES.get(deck.language)
            agent_name = language_info["agent_name"] if language_info else "AI Tutor"
            
            agents.append(LearnAgentSummary(
                deckId=deck.id,
                deckName=deck.name,
                language=deck.language,
                agentName=agent_name,
                dueCardCount=due_count,
            ))

    return LearnAgentsResponse(agents=agents, count=len(agents))


@router.post("/start", response_model=LearnStartResponse)
async def start_learning_session(
    req: LearnStartRequest, user: Annotated[CurrentUser, Depends(get_current_user)]
) -> LearnStartResponse:
    """Start a tutoring session for a deck.
    
    Fetches the next due card and initializes a chat session with the AI tutor.
    Returns the card prompt and an initial greeting from the tutor.
    """
    await _verify_deck_ownership(req.deckId, user.user_id)

    deck_repo = get_deck_repository()
    card_repo = get_card_repository()
    now_iso = utc_now_iso()

    # Get the deck for language info
    try:
        deck = deck_repo.get_by_id(req.deckId, user.user_id)
    except DeckNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deck with ID {req.deckId} not found",
        )

    # Get the next due card
    card = card_repo.get_next_due_for_deck(user.user_id, req.deckId, now_iso)
    if card is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No cards due for review in this deck",
        )

    # Get persona info
    language_info = SUPPORTED_LANGUAGES.get(deck.language)
    agent_name = language_info["agent_name"] if language_info else "AI Tutor"

    # Initialize session state
    from app.agents.session_store import get_session_store
    session_store = get_session_store()
    session_store.get_or_create(user.user_id, req.deckId, card.id)

    # Log session start (privacy: avoid logging card.back)
    logger.info(
        f"Chat session started: user={user.user_id}, deck={req.deckId}, "
        f"card={card.id}, language={deck.language}, agent={agent_name}"
    )

    # Generate initial greeting
    initial_message = (
        f"Hello! I'm {agent_name}, your {language_info['name'] if language_info else 'language'} tutor. "
        f"Let's practice! Here's your card:\n\n**{card.front}**\n\n"
        "What's your answer?"
    )

    return LearnStartResponse(
        cardId=card.id,
        cardFront=card.front,
        assistantMessage=initial_message,
        agentName=agent_name,
        language=deck.language,
    )


@router.post("/chat", response_model=LearnChatResponse)
async def chat_with_tutor(
    req: LearnChatRequest, user: Annotated[CurrentUser, Depends(get_current_user)]
) -> LearnChatResponse:
    """Send a message to the tutoring agent.
    
    The agent evaluates the user's answer and provides feedback.
    When canGrade is True, the user should submit a grade via POST /learn/review.
    """
    await _verify_deck_ownership(req.deckId, user.user_id)

    deck_repo = get_deck_repository()
    card_repo = get_card_repository()
    now_iso = utc_now_iso()

    # Get the deck for language info
    try:
        deck = deck_repo.get_by_id(req.deckId, user.user_id)
    except DeckNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deck with ID {req.deckId} not found",
        )

    # Get the current due card (or validate provided cardId)
    if req.cardId:
        try:
            card = card_repo.get_by_id(req.cardId, user.user_id)
            if card.deckId != req.deckId:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Card with ID {req.cardId} not found in deck {req.deckId}",
                )
        except CardNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Card with ID {req.cardId} not found",
            )
    else:
        card = card_repo.get_next_due_for_deck(user.user_id, req.deckId, now_iso)
        if card is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No cards due for review in this deck",
            )

    # Get or create session state
    from app.agents.session_store import get_session_store
    session_store = get_session_store()
    session_state = session_store.get_or_create(user.user_id, req.deckId, card.id)

    # Call the agent
    try:
        from app.agents.foundry_client import get_foundry_client
        client = get_foundry_client()
        
        # Log message send (privacy: don't log actual user message content)
        logger.info(
            f"Chat message: user={user.user_id}, deck={req.deckId}, "
            f"card={card.id}, msg_len={len(req.userMessage)}"
        )
        
        response = await client.send_message(
            user_message=req.userMessage,
            language=deck.language,
            card_front=card.front,
            card_back=card.back,
            session_state=session_state,
        )
        
        # Update session state
        session_store.update(user.user_id, req.deckId, session_state)
        
        # Log verdict (privacy: avoid feedback content in logs)
        logger.info(
            f"Chat verdict: user={user.user_id}, deck={req.deckId}, card={card.id}, "
            f"is_correct={response.is_correct}, revealed={response.revealed}, can_grade={response.can_grade}"
        )

        return LearnChatResponse(
            assistantMessage=response.feedback,
            canGrade=response.can_grade,
            revealed=response.revealed,
            isCorrect=response.is_correct,
            cardId=card.id,
            cardFront=card.front,
        )
    except EnvironmentError as e:
        # Agent framework not configured
        logger.error(f"Agent framework not configured: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI tutoring service is not configured. Please set up Azure OpenAI credentials.",
        )
    except Exception as e:
        logger.error(f"Agent call failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to communicate with the AI tutor. Please try again.",
        )
