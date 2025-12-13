"""API routers module."""

from .decks import router as decks_router
from .cards import router as cards_router
from .seed import router as seed_router
from .learn import router as learn_router

__all__ = [
    "decks_router",
    "cards_router",
    "seed_router",
    "learn_router",
]
