"""Decks API router."""

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from app.models import DeckCreate, DeckUpdate, DeckResponse, DeckListResponse
from app.repositories import get_deck_repository, DeckNotFoundError, get_card_repository
from app.auth import get_current_user, CurrentUser
from app.srs.time import utc_now_iso

router = APIRouter(prefix="/decks", tags=["decks"])


@router.get("", response_model=DeckListResponse)
async def list_decks(user: Annotated[CurrentUser, Depends(get_current_user)]) -> DeckListResponse:
    """List all decks for the current user with due card metrics."""
    deck_repo = get_deck_repository()
    card_repo = get_card_repository()
    decks = deck_repo.list_by_user(user.user_id)
    now_iso = utc_now_iso()

    deck_responses = []
    for deck in decks:
        due_count = card_repo.count_due_for_deck(user.user_id, deck.id, now_iso)
        next_due_at = card_repo.get_next_due_at_for_deck(user.user_id, deck.id)
        deck_responses.append(
            DeckResponse(
                **deck.model_dump(),
                dueCardCount=due_count,
                nextDueAt=next_due_at,
            )
        )

    return DeckListResponse(
        decks=deck_responses,
        count=len(deck_responses),
    )


@router.get("/{deck_id}", response_model=DeckResponse)
async def get_deck(
    deck_id: str, user: Annotated[CurrentUser, Depends(get_current_user)]
) -> DeckResponse:
    """Get a specific deck by ID."""
    repo = get_deck_repository()
    try:
        deck = repo.get_by_id(deck_id, user.user_id)
        return DeckResponse(**deck.model_dump())
    except DeckNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deck with ID {deck_id} not found",
        )


@router.post("", response_model=DeckResponse, status_code=status.HTTP_201_CREATED)
async def create_deck(
    deck_create: DeckCreate, user: Annotated[CurrentUser, Depends(get_current_user)]
) -> DeckResponse:
    """Create a new deck."""
    repo = get_deck_repository()
    deck = repo.create(deck_create, user.user_id)
    return DeckResponse(**deck.model_dump())


@router.put("/{deck_id}", response_model=DeckResponse)
async def update_deck(
    deck_id: str,
    deck_update: DeckUpdate,
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> DeckResponse:
    """Update an existing deck."""
    repo = get_deck_repository()
    try:
        deck = repo.update(deck_id, user.user_id, deck_update)
        return DeckResponse(**deck.model_dump())
    except DeckNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deck with ID {deck_id} not found",
        )


@router.delete("/{deck_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_deck(
    deck_id: str, user: Annotated[CurrentUser, Depends(get_current_user)]
) -> None:
    """Delete a deck and all its cards."""
    deck_repo = get_deck_repository()
    card_repo = get_card_repository()

    try:
        # Delete all cards in the deck first
        card_repo.delete_by_deck(deck_id, user.user_id)
        # Then delete the deck
        deck_repo.delete(deck_id, user.user_id)
    except DeckNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deck with ID {deck_id} not found",
        )
