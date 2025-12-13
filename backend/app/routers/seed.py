"""Seed API router for populating sample data."""

from typing import Annotated
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from app.models import DeckCreate, CardCreate
from app.repositories import get_deck_repository, get_card_repository
from app.auth import get_current_user, CurrentUser

router = APIRouter(prefix="/seed", tags=["seed"])


# Sample data
SAMPLE_DECKS = [
    DeckCreate(
        name="Spanish Basics",
        description="Essential Spanish words and phrases for beginners",
        language="es-ES",  # Spanish deck
    ),
    DeckCreate(
        name="French Essentials",
        description="Common French vocabulary for everyday conversations",
        language="fr-FR",  # French deck
    ),
    DeckCreate(
        name="German Fundamentals",
        description="Core German words and expressions",
        language="de-DE",  # German deck
    ),
]

SAMPLE_CARDS = {
    "Spanish Basics": [
        CardCreate(front="Hola", back="Hello"),
        CardCreate(front="Adiós", back="Goodbye"),
        CardCreate(front="Gracias", back="Thank you"),
        CardCreate(front="Por favor", back="Please"),
        CardCreate(front="Buenos días", back="Good morning"),
        CardCreate(front="Buenas noches", back="Good night"),
        CardCreate(front="¿Cómo estás?", back="How are you?"),
        CardCreate(front="Me llamo...", back="My name is..."),
        CardCreate(front="¿Cuánto cuesta?", back="How much does it cost?"),
        CardCreate(front="No entiendo", back="I don't understand"),
    ],
    "French Essentials": [
        CardCreate(front="Bonjour", back="Hello / Good morning"),
        CardCreate(front="Bonsoir", back="Good evening"),
        CardCreate(front="Au revoir", back="Goodbye"),
        CardCreate(front="Merci", back="Thank you"),
        CardCreate(front="S'il vous plaît", back="Please"),
        CardCreate(front="Excusez-moi", back="Excuse me"),
        CardCreate(front="Comment allez-vous?", back="How are you? (formal)"),
        CardCreate(front="Je m'appelle...", back="My name is..."),
        CardCreate(front="Parlez-vous anglais?", back="Do you speak English?"),
        CardCreate(front="Je ne comprends pas", back="I don't understand"),
    ],
    "German Fundamentals": [
        CardCreate(front="Guten Tag", back="Good day / Hello"),
        CardCreate(front="Guten Morgen", back="Good morning"),
        CardCreate(front="Auf Wiedersehen", back="Goodbye"),
        CardCreate(front="Danke", back="Thank you"),
        CardCreate(front="Bitte", back="Please / You're welcome"),
        CardCreate(front="Entschuldigung", back="Excuse me / Sorry"),
        CardCreate(front="Wie geht es Ihnen?", back="How are you? (formal)"),
        CardCreate(front="Ich heiße...", back="My name is..."),
        CardCreate(front="Sprechen Sie Englisch?", back="Do you speak English?"),
        CardCreate(front="Ich verstehe nicht", back="I don't understand"),
    ],
}


class SeedResponse(BaseModel):
    """Response from seed operation."""

    message: str
    decks_created: int
    cards_created: int


@router.post("", response_model=SeedResponse, status_code=status.HTTP_201_CREATED)
async def seed_sample_data(
    user: Annotated[CurrentUser, Depends(get_current_user)]
) -> SeedResponse:
    """Seed the database with sample data for the current user."""
    deck_repo = get_deck_repository()
    card_repo = get_card_repository()

    decks_created = 0
    cards_created = 0

    for deck_create in SAMPLE_DECKS:
        # Create deck
        deck = deck_repo.create(deck_create, user.user_id)
        decks_created += 1

        # Add cards to deck
        cards_for_deck = SAMPLE_CARDS.get(deck_create.name, [])
        for card_create in cards_for_deck:
            card_repo.create(deck.id, user.user_id, card_create)
            cards_created += 1

    return SeedResponse(
        message="Sample data created successfully",
        decks_created=decks_created,
        cards_created=cards_created,
    )
