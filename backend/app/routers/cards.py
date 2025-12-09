"""Cards API router."""

from fastapi import APIRouter, HTTPException, Header, status
from app.models import CardCreate, CardUpdate, CardResponse, CardListResponse
from app.repositories import (
    get_card_repository,
    get_deck_repository,
    CardNotFoundError,
    DeckNotFoundError,
)

router = APIRouter(prefix="/decks/{deck_id}/cards", tags=["cards"])


def get_user_id(x_user_id: str = Header(..., description="User ID header")) -> str:
    """Extract user ID from header."""
    return x_user_id


async def verify_deck_ownership(deck_id: str, user_id: str) -> None:
    """Verify that the deck exists and belongs to the user."""
    deck_repo = get_deck_repository()
    if not await deck_repo.exists(deck_id, user_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deck with ID {deck_id} not found",
        )


@router.get("", response_model=CardListResponse)
async def list_cards(deck_id: str, x_user_id: str = Header(...)) -> CardListResponse:
    """List all cards in a deck."""
    user_id = get_user_id(x_user_id)
    await verify_deck_ownership(deck_id, user_id)

    repo = get_card_repository()
    cards = await repo.list_by_deck(deck_id, user_id)
    return CardListResponse(
        cards=[CardResponse(**card.model_dump()) for card in cards],
        count=len(cards),
    )


@router.get("/{card_id}", response_model=CardResponse)
async def get_card(deck_id: str, card_id: str, x_user_id: str = Header(...)) -> CardResponse:
    """Get a specific card by ID."""
    user_id = get_user_id(x_user_id)
    await verify_deck_ownership(deck_id, user_id)

    repo = get_card_repository()
    try:
        card = await repo.get_by_id(card_id, user_id)
        # Verify card belongs to the specified deck
        if card.deckId != deck_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Card with ID {card_id} not found in deck {deck_id}",
            )
        return CardResponse(**card.model_dump())
    except CardNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Card with ID {card_id} not found",
        )


@router.post("", response_model=CardResponse, status_code=status.HTTP_201_CREATED)
async def create_card(
    deck_id: str, card_create: CardCreate, x_user_id: str = Header(...)
) -> CardResponse:
    """Create a new card in a deck."""
    user_id = get_user_id(x_user_id)
    repo = get_card_repository()

    try:
        card = await repo.create(deck_id, user_id, card_create)
        return CardResponse(**card.model_dump())
    except DeckNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deck with ID {deck_id} not found",
        )


@router.put("/{card_id}", response_model=CardResponse)
async def update_card(
    deck_id: str, card_id: str, card_update: CardUpdate, x_user_id: str = Header(...)
) -> CardResponse:
    """Update an existing card."""
    user_id = get_user_id(x_user_id)
    await verify_deck_ownership(deck_id, user_id)

    repo = get_card_repository()
    try:
        # Verify card belongs to the specified deck
        existing = await repo.get_by_id(card_id, user_id)
        if existing.deckId != deck_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Card with ID {card_id} not found in deck {deck_id}",
            )

        card = await repo.update(card_id, user_id, card_update)
        return CardResponse(**card.model_dump())
    except CardNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Card with ID {card_id} not found",
        )


@router.delete("/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_card(deck_id: str, card_id: str, x_user_id: str = Header(...)) -> None:
    """Delete a card."""
    user_id = get_user_id(x_user_id)
    await verify_deck_ownership(deck_id, user_id)

    repo = get_card_repository()
    try:
        # Verify card belongs to the specified deck
        existing = await repo.get_by_id(card_id, user_id)
        if existing.deckId != deck_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Card with ID {card_id} not found in deck {deck_id}",
            )

        await repo.delete(card_id, user_id)
    except CardNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Card with ID {card_id} not found",
        )
