"""Learn (SRS) API router."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import CurrentUser, get_current_user
from app.models import CardResponse, LearnNextResponse, LearnReviewRequest
from app.repositories import (
    CardNotFoundError,
    DeckNotFoundError,
    get_card_repository,
    get_deck_repository,
)
from app.srs.sm2 import SM2State, apply_sm2
from app.srs.time import add_days_iso, add_hours_iso, add_minutes_iso, parse_iso_z, utc_now_iso


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

    updated = card_repo.replace(card)
    return CardResponse(**updated.model_dump())
