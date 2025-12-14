"""Integration-ish tests for /learn endpoints (auth disabled, stubbed repos)."""

import os
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

# Ensure auth is disabled for these tests
os.environ["AUTH_ENABLED"] = "false"

from app.main import app


@dataclass
class StubDeckRepo:
    decks: set[str]

    def exists(self, deck_id: str, user_id: str) -> bool:  # noqa: ARG002
        return deck_id in self.decks


@dataclass
class StubCardRepo:
    cards: dict[str, dict]

    def get_by_id(self, card_id: str, user_id: str):  # noqa: ARG002
        from app.models import Card

        if card_id not in self.cards:
            from app.repositories.card_repository import CardNotFoundError

            raise CardNotFoundError("not found")
        return Card(**self.cards[card_id])

    def replace(self, card):
        self.cards[card.id] = card.model_dump()
        return card

    def get_next_due_for_deck(self, user_id: str, deck_id: str, now_iso: str):
        from app.models import Card
        from app.srs.time import parse_iso_z

        now_dt = parse_iso_z(now_iso)
        due_cards = []
        for raw in self.cards.values():
            if raw.get("userId") != user_id or raw.get("deckId") != deck_id:
                continue
            card = Card(**raw)
            if parse_iso_z(card.dueAt) <= now_dt:
                due_cards.append(card)

        if not due_cards:
            return None
        due_cards.sort(key=lambda c: c.dueAt)
        return due_cards[0]

    def get_next_due_at_for_deck(self, user_id: str, deck_id: str):
        from app.models import Card

        due_ats = []
        for raw in self.cards.values():
            if raw.get("userId") != user_id or raw.get("deckId") != deck_id:
                continue
            card = Card(**raw)
            due_ats.append(card.dueAt)
        if not due_ats:
            return None
        return sorted(due_ats)[0]


@pytest.fixture
def client():
    return TestClient(app)


def test_learn_next_returns_unseen_due_now(monkeypatch, client):
    from app.routers import learn as learn_router

    user_id = "test-user"
    deck_id = "deck-1"
    card_id = "card-1"

    deck_repo = StubDeckRepo(decks={deck_id})
    card_repo = StubCardRepo(
        cards={
            card_id: {
                "id": card_id,
                "deckId": deck_id,
                "userId": user_id,
                "front": "Hola",
                "back": "Hello",
                "createdAt": "2025-12-13T00:00:00Z",
                "updatedAt": "2025-12-13T00:00:00Z",
                # Provide dueAt deterministically; remaining SRS fields should default.
                "dueAt": "2025-12-13T00:00:00Z",
            }
        }
    )

    monkeypatch.setattr(learn_router, "get_deck_repository", lambda: deck_repo)
    monkeypatch.setattr(learn_router, "get_card_repository", lambda: card_repo)
    monkeypatch.setattr(learn_router, "utc_now_iso", lambda: "2025-12-13T00:00:00Z")

    resp = client.get(f"/learn/next?deckId={deck_id}", headers={"X-User-Id": user_id})
    assert resp.status_code == 200
    data = resp.json()
    assert data["card"]["id"] == card_id
    assert data["card"]["dueAt"] == "2025-12-13T00:00:00Z"
    assert data["card"]["easeFactor"] == 2.5
    assert data["card"]["repetitions"] == 0
    assert data["card"]["intervalDays"] == 0
    assert data["card"]["lastReviewedAt"] is None
