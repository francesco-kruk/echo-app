"""Decks API router."""

from fastapi import APIRouter, HTTPException, Header, status
from app.models import DeckCreate, DeckUpdate, DeckResponse, DeckListResponse
from app.repositories import get_deck_repository, DeckNotFoundError, get_card_repository

router = APIRouter(prefix="/decks", tags=["decks"])


def get_user_id(x_user_id: str = Header(..., description="User ID header")) -> str:
    """Extract user ID from header."""
    return x_user_id


@router.get("", response_model=DeckListResponse)
async def list_decks(x_user_id: str = Header(...)) -> DeckListResponse:
    """List all decks for the current user."""
    user_id = get_user_id(x_user_id)
    repo = get_deck_repository()
    decks = repo.list_by_user(user_id)
    return DeckListResponse(
        decks=[DeckResponse(**deck.model_dump()) for deck in decks],
        count=len(decks),
    )


@router.get("/{deck_id}", response_model=DeckResponse)
async def get_deck(deck_id: str, x_user_id: str = Header(...)) -> DeckResponse:
    """Get a specific deck by ID."""
    user_id = get_user_id(x_user_id)
    repo = get_deck_repository()
    try:
        deck = repo.get_by_id(deck_id, user_id)
        return DeckResponse(**deck.model_dump())
    except DeckNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deck with ID {deck_id} not found",
        )


@router.post("", response_model=DeckResponse, status_code=status.HTTP_201_CREATED)
async def create_deck(deck_create: DeckCreate, x_user_id: str = Header(...)) -> DeckResponse:
    """Create a new deck."""
    user_id = get_user_id(x_user_id)
    repo = get_deck_repository()
    deck = repo.create(deck_create, user_id)
    return DeckResponse(**deck.model_dump())


@router.put("/{deck_id}", response_model=DeckResponse)
async def update_deck(
    deck_id: str, deck_update: DeckUpdate, x_user_id: str = Header(...)
) -> DeckResponse:
    """Update an existing deck."""
    user_id = get_user_id(x_user_id)
    repo = get_deck_repository()
    try:
        deck = repo.update(deck_id, user_id, deck_update)
        return DeckResponse(**deck.model_dump())
    except DeckNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deck with ID {deck_id} not found",
        )


@router.delete("/{deck_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_deck(deck_id: str, x_user_id: str = Header(...)) -> None:
    """Delete a deck and all its cards."""
    user_id = get_user_id(x_user_id)
    deck_repo = get_deck_repository()
    card_repo = get_card_repository()

    try:
        # Delete all cards in the deck first
        card_repo.delete_by_deck(deck_id, user_id)
        # Then delete the deck
        deck_repo.delete(deck_id, user_id)
    except DeckNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deck with ID {deck_id} not found",
        )
