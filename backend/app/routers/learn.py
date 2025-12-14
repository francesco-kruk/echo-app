"""Learn (SRS) API router."""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import CurrentUser, get_current_user
from app.models import (
    Card,
    CardResponse,
    Grade,
    LearnNextResponse,
    LearnAgentSummary,
    LearnAgentsResponse,
    LearnCardInfo,
    LearnChatRequest,
    LearnChatResponse,
    LearnMode,
    LearnStartRequest,
    LearnStartResponse,
)
from app.srs.grading import compute_grade
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


def apply_review_grade(card: Card, grade: Grade) -> Card:
    """Apply a review grade to a card and update its SRS fields.

    This is a shared function used by:
    - POST /learn/review (manual review, kept for compatibility)
    - Agent-driven grading in /learn/chat

    Updates:
    - SM-2 state (easeFactor, repetitions, intervalDays)
    - Due scheduling (dueAt, lastReviewedAt)
    - Grade tracking (lastGrade, lastGradedAt)
    - updatedAt timestamp

    Args:
        card: The Card model to update (mutated in place)
        grade: The grade to apply

    Returns:
        The updated card (same reference)
    """
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
    now_iso = utc_now_iso()
    card.lastReviewedAt = now_iso
    card.dueAt = _due_at_for_grade(now_dt, grade)
    card.updatedAt = now_iso

    # Track grade history
    card.lastGrade = grade
    card.lastGradedAt = now_iso

    return card


def submit_card_review_grade(
    card: Card,
    revealed: bool,
    attempt_count: int,
    card_repo,
    user_id: str,
    deck_id: str,
) -> Card:
    """Apply an agent-driven review grade to a card.

    This is the internal "tool-like" function called when the agent verdict
    resolves a card. The grade is computed deterministically from session state
    (revealed, attempt_count) via the grading heuristic - the model only
    provides resolution signals, not the grade itself.

    Args:
        card: The Card model to update
        revealed: Whether the answer was revealed to the user
        attempt_count: Number of attempts before resolution
        card_repo: The card repository for persistence
        user_id: User ID for logging
        deck_id: Deck ID for logging

    Returns:
        The updated and persisted card
    """
    # Compute grade deterministically from session state
    grade = compute_grade(revealed=revealed, attempt_count=attempt_count)

    # Apply the grade using shared function
    apply_review_grade(card, grade)

    # Persist the updated card
    updated = card_repo.replace(card)

    logger.info(
        f"Agent-driven grade applied: user={user_id}, deck={deck_id}, "
        f"card={card.id}, grade={grade}, revealed={revealed}, "
        f"attempts={attempt_count}, new_due_at={card.dueAt}"
    )

    return updated


async def _verify_deck_ownership(deck_id: str, user_id: str) -> None:
    deck_repo = get_deck_repository()
    if not deck_repo.exists(deck_id, user_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deck with ID {deck_id} not found",
        )


def _generate_conversation_id(user_id: str, deck_id: str) -> str:
    """Generate a stable conversation ID for a user+deck session.
    
    Uses a deterministic UUID based on user_id and deck_id.
    This ensures the same conversation ID is returned for the same session.
    """
    # Create a deterministic namespace UUID from user_id and deck_id
    namespace = uuid.UUID('6ba7b810-9dad-11d1-80b4-00c04fd430c8')  # UUID namespace
    combined = f"{user_id}:{deck_id}"
    return str(uuid.uuid5(namespace, combined))


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
    
    If cards are due, starts in card mode with the next due card.
    If no cards are due, starts in free mode for general tutoring.
    Never 404s just because no cards are due.
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

    # Get persona info
    language_info = SUPPORTED_LANGUAGES.get(deck.language)
    agent_name = language_info["agent_name"] if language_info else "AI Tutor"

    # Get the next due card (may be None)
    card = card_repo.get_next_due_for_deck(user.user_id, req.deckId, now_iso)

    # Initialize session state using the new state machine
    from app.agents.session_store import get_session_store
    from app.agents.foundry_client import get_foundry_client
    session_store = get_session_store()
    
    if card is not None:
        # Card mode: start with the due card
        session_state = session_store.get_or_create_session(user.user_id, req.deckId, card.id)
        session_state.start_card(card.id)
        mode: LearnMode = "card"
        card_info = LearnCardInfo(id=card.id, front=card.front)
    else:
        # Free mode: no cards due
        session_state = session_store.get_or_create_session(user.user_id, req.deckId, None)
        session_state.start_free_mode()
        mode = "free"
        card_info = None
    
    # Call the agent for the initial assistant message
    try:
        client = get_foundry_client()
        greeting_response = await client.generate_greeting(
            language=deck.language,
            session_state=session_state,
            card_front=card.front if card else None,
            card_back=card.back if card else None,
        )
        initial_message = greeting_response.feedback
    except EnvironmentError as e:
        # Agent not configured, use fallback greeting
        logger.warning(f"Agent not configured for greeting, using fallback: {e}")
        if card is not None:
            initial_message = (
                f"Hello! I'm {agent_name}, your {language_info['name'] if language_info else 'language'} tutor. "
                f"Let's practice! Here's your card:\n\n**{card.front}**\n\n"
                "What's your answer?"
            )
        else:
            initial_message = (
                f"Hello! I'm {agent_name}, your {language_info['name'] if language_info else 'language'} tutor. "
                f"You don't have any cards due for review right now. "
                f"Feel free to ask me anything about {language_info['name'] if language_info else 'the language'} - "
                f"vocabulary, grammar, expressions, or anything else you'd like to practice!"
            )
    except Exception as e:
        # Other errors, use fallback greeting
        logger.error(f"Agent greeting generation failed: {e}")
        if card is not None:
            initial_message = (
                f"Hello! I'm {agent_name}, your {language_info['name'] if language_info else 'language'} tutor. "
                f"Let's practice! Here's your card:\n\n**{card.front}**\n\n"
                "What's your answer?"
            )
        else:
            initial_message = (
                f"Hello! I'm {agent_name}, your {language_info['name'] if language_info else 'language'} tutor. "
                f"You don't have any cards due for review right now. "
                f"Feel free to ask me anything about {language_info['name'] if language_info else 'the language'} - "
                f"vocabulary, grammar, expressions, or anything else you'd like to practice!"
            )
    
    session_store.update(user.user_id, req.deckId, session_state)

    # Log session start
    logger.info(
        f"Chat session started: user={user.user_id}, deck={req.deckId}, "
        f"mode={mode}, card={card.id if card else None}, language={deck.language}, agent={agent_name}"
    )

    return LearnStartResponse(
        assistantMessage=initial_message,
        mode=mode,
        card=card_info,
        conversationId=session_state.ui_conversation_id,
        agentName=agent_name,
        language=deck.language,
    )


@router.post("/chat", response_model=LearnChatResponse)
async def chat_with_tutor(
    req: LearnChatRequest, user: Annotated[CurrentUser, Depends(get_current_user)]
) -> LearnChatResponse:
    """Send a message to the tutoring agent.
    
    Implements a state machine with two modes:
    - Card mode: working on a specific due card
    - Free mode: general tutoring when no cards are due
    
    Mode transitions are fully server-driven; clients do not need to pass cardId.
    Never 404s just because no cards are due.
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

    # Get or create session state
    from app.agents.session_store import get_session_store
    session_store = get_session_store()
    session_state = session_store.get_or_create_session(user.user_id, req.deckId, None)
    
    # Determine current card based on session mode
    card = None
    
    if session_state.mode == "card" and session_state.card_id:
        # We have an active card in the session - use it
        try:
            card = card_repo.get_by_id(session_state.card_id, user.user_id)
            if card.deckId != req.deckId:
                # Card doesn't belong to this deck anymore, clear it
                card = None
        except CardNotFoundError:
            # Card was deleted, clear it
            card = None
    
    if card is None:
        # No active card in session, try to get the next due card
        card = card_repo.get_next_due_for_deck(user.user_id, req.deckId, now_iso)
        if card is not None:
            # Start card mode with this card
            session_state.start_card(card.id)
        else:
            # No due cards, switch to free mode if not already
            if session_state.mode != "free":
                session_state.start_free_mode()
    
    # Process based on current mode
    if session_state.mode == "card" and card is not None:
        # === CARD MODE ===
        return await _handle_card_mode_chat(
            req=req,
            user=user,
            deck=deck,
            card=card,
            session_state=session_state,
            session_store=session_store,
            card_repo=card_repo,
        )
    else:
        # === FREE MODE ===
        return await _handle_free_mode_chat(
            req=req,
            user=user,
            deck=deck,
            session_state=session_state,
            session_store=session_store,
            card_repo=card_repo,
        )


async def _handle_card_mode_chat(
    req: LearnChatRequest,
    user: CurrentUser,
    deck,  # DeckResponse
    card,  # Card
    session_state,  # AgentSessionState
    session_store,  # SessionStore
    card_repo,  # CardRepository
) -> LearnChatResponse:
    """Handle chat in card mode.
    
    - Increments attempt_count if card not yet resolved
    - Calls agent with card context
    - If agent resolves the card (correct or revealed):
      - Sets resolved_at
      - Computes and applies grade (Phase 2)
      - Resets agent context
      - Advances to next due card or switches to free mode
    """
    # Increment attempt_count only if not yet resolved
    if not session_state.is_resolved:
        session_state.attempt_count += 1
    
    # Call the agent
    try:
        from app.agents.foundry_client import get_foundry_client
        client = get_foundry_client()
        
        # Log message send (privacy: don't log actual user message content)
        logger.info(
            f"Chat message (card mode): user={user.user_id}, deck={req.deckId}, "
            f"card={card.id}, attempt={session_state.attempt_count}, msg_len={len(req.userMessage)}"
        )
        
        response = await client.send_message(
            user_message=req.userMessage,
            language=deck.language,
            card_front=card.front,
            card_back=card.back,
            session_state=session_state,
        )
        
        # Log verdict
        logger.info(
            f"Chat verdict (card mode): user={user.user_id}, deck={req.deckId}, card={card.id}, "
            f"is_correct={response.is_correct}, revealed={response.revealed}, "
            f"attempt={session_state.attempt_count}"
        )
        
        # Check if this resolves the card for the first time
        card_resolved_now = False
        if not session_state.is_resolved and (response.is_correct or response.revealed):
            card_resolved_now = True
            session_state.resolved_at = utc_now_iso()
            session_state.is_correct = response.is_correct
            session_state.revealed = response.revealed
            
            # Apply grade using deterministic heuristic (Phase 2)
            # The grade is computed from session state, not from the model
            submit_card_review_grade(
                card=card,
                revealed=response.revealed,
                attempt_count=session_state.attempt_count,
                card_repo=card_repo,
                user_id=user.user_id,
                deck_id=req.deckId,
            )
            
            logger.info(
                f"Card resolved: user={user.user_id}, deck={req.deckId}, card={card.id}, "
                f"correct={response.is_correct}, revealed={response.revealed}, "
                f"attempts={session_state.attempt_count}"
            )
        
        # Prepare response
        result_mode: LearnMode = "card"
        result_card_info = LearnCardInfo(id=card.id, front=card.front)
        
        # If card was just resolved, advance to next card or switch to free mode
        if card_resolved_now:
            # Reset agent context for the next card
            session_state.reset_agent_context()
            
            # Try to get next due card
            now_iso = utc_now_iso()
            next_card = card_repo.get_next_due_for_deck(user.user_id, req.deckId, now_iso)
            
            if next_card is not None:
                # Start next card
                session_state.start_card(next_card.id)
                result_card_info = LearnCardInfo(id=next_card.id, front=next_card.front)
            else:
                # No more due cards, switch to free mode
                session_state.start_free_mode()
                result_mode = "free"
                result_card_info = None
        
        # Update session state
        session_store.update(user.user_id, req.deckId, session_state)
        
        return LearnChatResponse(
            assistantMessage=response.feedback,
            mode=result_mode,
            card=result_card_info,
        )
        
    except EnvironmentError as e:
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


async def _handle_free_mode_chat(
    req: LearnChatRequest,
    user: CurrentUser,
    deck,  # DeckResponse
    session_state,  # AgentSessionState
    session_store,  # SessionStore
    card_repo,  # CardRepository
) -> LearnChatResponse:
    """Handle chat in free mode.
    
    - Calls agent without card context
    - Adds messages to agent context with last-10 sliding window
    - When context window rolls over (trimming occurs), re-checks due cards
    - If a due card exists, switches to card mode
    """
    try:
        from app.agents.foundry_client import get_foundry_client
        
        client = get_foundry_client()
        
        # Log message send
        logger.info(
            f"Chat message (free mode): user={user.user_id}, deck={req.deckId}, "
            f"msg_len={len(req.userMessage)}"
        )
        
        # Call agent with free mode system prompt (no card context)
        response = await client.send_free_mode_message(
            user_message=req.userMessage,
            language=deck.language,
            session_state=session_state,
        )
        
        feedback = response.feedback
        
        # Check if window rolled over (send_free_mode_message already adds messages)
        # We need to check the session state's message count to detect rollover
        add_result = {"window_rolled_over": len(session_state.agent_context_messages) >= session_state.FREE_MODE_MAX_MESSAGES}
        
        # Check if we should re-check due cards (window rolled over)
        result_mode: LearnMode = "free"
        result_card_info = None
        
        if add_result["window_rolled_over"]:
            # Window trimmed, re-check for due cards
            now_iso = utc_now_iso()
            due_card = card_repo.get_next_due_for_deck(user.user_id, req.deckId, now_iso)
            
            if due_card is not None:
                # Switch to card mode
                session_state.start_card(due_card.id)
                result_mode = "card"
                result_card_info = LearnCardInfo(id=due_card.id, front=due_card.front)
                
                logger.info(
                    f"Free mode -> card mode transition: user={user.user_id}, "
                    f"deck={req.deckId}, card={due_card.id}"
                )
        
        # Update session state
        session_store.update(user.user_id, req.deckId, session_state)
        
        logger.info(
            f"Chat response (free mode): user={user.user_id}, deck={req.deckId}, "
            f"mode={result_mode}"
        )
        
        return LearnChatResponse(
            assistantMessage=feedback,
            mode=result_mode,
            card=result_card_info,
        )
        
    except EnvironmentError as e:
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
