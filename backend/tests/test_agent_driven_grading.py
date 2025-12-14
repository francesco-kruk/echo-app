"""Integration tests for agent-driven grading persistence.

These tests verify that when the agent returns resolution signals (isCorrect=True or revealed=True),
the card's lastGrade and lastGradedAt fields are correctly updated according to the deterministic
grading heuristic:
- revealed=True → grade is "again"
- attempt_count=1 → grade is "easy"
- attempt_count=2 or 3 → grade is "good"
- attempt_count=4+ → grade is "hard"

All tests stub the FoundryAgentClient.send_message to return deterministic AgentResponse values,
so they do not require Azure credentials to run.
"""

import os
from dataclasses import dataclass
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Ensure auth is disabled for these tests
os.environ["AUTH_ENABLED"] = "false"
# Prevent agent client from requiring real credentials
os.environ["AZURE_OPENAI_ENDPOINT"] = "https://test.openai.azure.com/"
os.environ["AZURE_OPENAI_RESPONSES_DEPLOYMENT_NAME"] = "test-deployment"

from app.main import app
from app.agents.foundry_client import AgentResponse


@dataclass
class StubDeckRepo:
    """Stub deck repository for testing."""
    decks: dict  # {deck_id: deck_data}

    def exists(self, deck_id: str, user_id: str) -> bool:
        if deck_id not in self.decks:
            return False
        return self.decks[deck_id].get("userId") == user_id

    def get_by_id(self, deck_id: str, user_id: str):
        from app.models import Deck

        if deck_id not in self.decks:
            from app.repositories.deck_repository import DeckNotFoundError
            raise DeckNotFoundError("not found")

        deck_data = self.decks[deck_id]
        if deck_data.get("userId") != user_id:
            from app.repositories.deck_repository import DeckNotFoundError
            raise DeckNotFoundError("not found")

        return Deck(**deck_data)

    def list_by_user(self, user_id: str):
        from app.models import Deck
        return [
            Deck(**data) for data in self.decks.values()
            if data.get("userId") == user_id
        ]


@dataclass
class StubCardRepo:
    """Stub card repository for testing."""
    cards: dict[str, dict]

    def get_by_id(self, card_id: str, user_id: str):
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

    def count_due_for_deck(self, user_id: str, deck_id: str, now_iso: str) -> int:
        from app.srs.time import parse_iso_z

        now_dt = parse_iso_z(now_iso)
        count = 0
        for raw in self.cards.values():
            if raw.get("userId") != user_id or raw.get("deckId") != deck_id:
                continue
            if parse_iso_z(raw["dueAt"]) <= now_dt:
                count += 1
        return count


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def reset_session_store():
    """Reset the session store before and after each test."""
    from app.agents.session_store import get_session_store
    
    store = get_session_store()
    # Clear all sessions by resetting the internal cache
    store._cache = type(store._cache)(store._cache.maxsize, store._cache.ttl)
    
    yield store
    
    # Clear again after test
    store._cache = type(store._cache)(store._cache.maxsize, store._cache.ttl)


def create_mock_foundry_client(responses: list[AgentResponse]):
    """Create a mock Foundry client that returns responses in sequence.
    
    Args:
        responses: List of AgentResponse objects to return in order.
                   If more calls are made than responses, the last response is repeated.
    """
    from app.agents.foundry_client import reset_foundry_client
    
    reset_foundry_client()
    
    call_count = [0]  # Use list to allow mutation in nested function
    
    async def mock_send_message(*args, **kwargs):
        idx = min(call_count[0], len(responses) - 1)
        call_count[0] += 1
        return responses[idx]
    
    async def mock_generate_greeting(*args, **kwargs):
        return AgentResponse(
            feedback="Hello! Let's practice!",
            is_correct=False,
            revealed=False,
            can_grade=False,
            normalization_notes=None,
        )
    
    mock_client = MagicMock()
    mock_client.send_message = mock_send_message
    mock_client.generate_greeting = mock_generate_greeting
    mock_client.send_free_mode_message = mock_send_message
    
    return mock_client, reset_foundry_client


class TestAgentDrivenGradingCorrectAnswer:
    """Tests for agent-driven grading when the user gets the answer correct."""

    def test_correct_on_first_attempt_grades_easy(self, client, monkeypatch, reset_session_store):
        """When user gets correct on first attempt, grade should be 'easy'."""
        from app.routers import learn as learn_router
        
        user_id = "test-user"
        deck_id = "deck-1"
        card_id = "card-1"
        
        deck_repo = StubDeckRepo(
            decks={
                deck_id: {
                    "id": deck_id,
                    "userId": user_id,
                    "name": "Spanish Basics",
                    "language": "es-ES",
                    "createdAt": "2025-12-13T00:00:00Z",
                    "updatedAt": "2025-12-13T00:00:00Z",
                }
            }
        )
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
                    "dueAt": "2025-12-13T00:00:00Z",
                    "easeFactor": 2.5,
                    "repetitions": 0,
                    "intervalDays": 0,
                    "lastReviewedAt": None,
                    "lastGrade": None,
                    "lastGradedAt": None,
                }
            }
        )
        
        # Create mock client that returns correct on first attempt
        mock_client, reset_fn = create_mock_foundry_client([
            AgentResponse(
                feedback="Excellent! That's correct!",
                is_correct=True,
                revealed=False,
                can_grade=True,
                normalization_notes=None,
            )
        ])
        
        monkeypatch.setattr(learn_router, "get_deck_repository", lambda: deck_repo)
        monkeypatch.setattr(learn_router, "get_card_repository", lambda: card_repo)
        monkeypatch.setattr(learn_router, "utc_now_iso", lambda: "2025-12-13T00:00:00Z")
        
        with patch("app.agents.foundry_client.get_foundry_client", return_value=mock_client):
            # Start a session
            start_resp = client.post(
            "/learn/start",
            headers={"X-User-Id": user_id},
            json={"deckId": deck_id},
            )
            assert start_resp.status_code == 200
            assert start_resp.json()["mode"] == "card"
            
            # Send user's answer (first attempt, correct)
            chat_resp = client.post(
            "/learn/chat",
            headers={"X-User-Id": user_id},
            json={"deckId": deck_id, "userMessage": "Hello"},
            )
            assert chat_resp.status_code == 200
        
        # Verify the card was graded as "easy" (first attempt correct)
        updated_card = card_repo.cards[card_id]
        assert updated_card["lastGrade"] == "easy"
        assert updated_card["lastGradedAt"] is not None
        
        reset_fn()

    def test_correct_on_second_attempt_grades_good(self, client, monkeypatch, reset_session_store):
        """When user gets correct on second attempt, grade should be 'good'."""
        from app.routers import learn as learn_router
        
        user_id = "test-user"
        deck_id = "deck-1"
        card_id = "card-1"
        
        deck_repo = StubDeckRepo(
            decks={
                deck_id: {
                    "id": deck_id,
                    "userId": user_id,
                    "name": "German Basics",
                    "language": "de-DE",
                    "createdAt": "2025-12-13T00:00:00Z",
                    "updatedAt": "2025-12-13T00:00:00Z",
                }
            }
        )
        card_repo = StubCardRepo(
            cards={
                card_id: {
                    "id": card_id,
                    "deckId": deck_id,
                    "userId": user_id,
                    "front": "dog",
                    "back": "Hund",
                    "createdAt": "2025-12-13T00:00:00Z",
                    "updatedAt": "2025-12-13T00:00:00Z",
                    "dueAt": "2025-12-13T00:00:00Z",
                    "easeFactor": 2.5,
                    "repetitions": 0,
                    "intervalDays": 0,
                    "lastReviewedAt": None,
                    "lastGrade": None,
                    "lastGradedAt": None,
                }
            }
        )
        
        # Create mock client: first attempt wrong, second attempt correct
        mock_client, reset_fn = create_mock_foundry_client([
            AgentResponse(
                feedback="Not quite right. Think about it again.",
                is_correct=False,
                revealed=False,
                can_grade=False,
                normalization_notes=None,
            ),
            AgentResponse(
                feedback="Yes! That's correct!",
                is_correct=True,
                revealed=False,
                can_grade=True,
                normalization_notes=None,
            ),
        ])
        
        monkeypatch.setattr(learn_router, "get_deck_repository", lambda: deck_repo)
        monkeypatch.setattr(learn_router, "get_card_repository", lambda: card_repo)
        monkeypatch.setattr(learn_router, "utc_now_iso", lambda: "2025-12-13T00:00:00Z")
        
        with patch("app.agents.foundry_client.get_foundry_client", return_value=mock_client):
            # Start a session
            start_resp = client.post(
                "/learn/start",
                headers={"X-User-Id": user_id},
                json={"deckId": deck_id},
            )
            assert start_resp.status_code == 200
                
            # First attempt (wrong)
            chat_resp1 = client.post(
                "/learn/chat",
                headers={"X-User-Id": user_id},
                json={"deckId": deck_id, "userMessage": "Dog"},
            )
            assert chat_resp1.status_code == 200
            # Card should not be graded yet
            assert card_repo.cards[card_id]["lastGrade"] is None
                
            # Second attempt (correct)
            chat_resp2 = client.post(
                "/learn/chat",
                headers={"X-User-Id": user_id},
                json={"deckId": deck_id, "userMessage": "Hund"},
            )
            assert chat_resp2.status_code == 200
        
        # Verify the card was graded as "good" (second attempt correct)
        updated_card = card_repo.cards[card_id]
        assert updated_card["lastGrade"] == "good"
        assert updated_card["lastGradedAt"] is not None
        
        reset_fn()

    def test_correct_on_third_attempt_grades_good(self, client, monkeypatch, reset_session_store):
        """When user gets correct on third attempt, grade should be 'good'."""
        from app.routers import learn as learn_router
        
        user_id = "test-user"
        deck_id = "deck-1"
        card_id = "card-1"
        
        deck_repo = StubDeckRepo(
            decks={
                deck_id: {
                    "id": deck_id,
                    "userId": user_id,
                    "name": "French Basics",
                    "language": "fr-FR",
                    "createdAt": "2025-12-13T00:00:00Z",
                    "updatedAt": "2025-12-13T00:00:00Z",
                }
            }
        )
        card_repo = StubCardRepo(
            cards={
                card_id: {
                    "id": card_id,
                    "deckId": deck_id,
                    "userId": user_id,
                    "front": "cat",
                    "back": "chat",
                    "createdAt": "2025-12-13T00:00:00Z",
                    "updatedAt": "2025-12-13T00:00:00Z",
                    "dueAt": "2025-12-13T00:00:00Z",
                    "easeFactor": 2.5,
                    "repetitions": 0,
                    "intervalDays": 0,
                    "lastReviewedAt": None,
                    "lastGrade": None,
                    "lastGradedAt": None,
                }
            }
        )
        
        # Create mock client: first two attempts wrong, third attempt correct
        mock_client, reset_fn = create_mock_foundry_client([
            AgentResponse(
                feedback="Not quite. Try again.",
                is_correct=False,
                revealed=False,
                can_grade=False,
                normalization_notes=None,
            ),
            AgentResponse(
                feedback="Still not right. Here's a hint: it sounds like 'sha'.",
                is_correct=False,
                revealed=False,
                can_grade=False,
                normalization_notes=None,
            ),
            AgentResponse(
                feedback="Correct! 'Chat' is the French word for cat.",
                is_correct=True,
                revealed=False,
                can_grade=True,
                normalization_notes=None,
            ),
        ])
        
        monkeypatch.setattr(learn_router, "get_deck_repository", lambda: deck_repo)
        monkeypatch.setattr(learn_router, "get_card_repository", lambda: card_repo)
        monkeypatch.setattr(learn_router, "utc_now_iso", lambda: "2025-12-13T00:00:00Z")
        
        with patch("app.agents.foundry_client.get_foundry_client", return_value=mock_client):
            # Start a session
            start_resp = client.post(
                "/learn/start",
                headers={"X-User-Id": user_id},
                json={"deckId": deck_id},
            )
            assert start_resp.status_code == 200
                
            # First attempt (wrong)
            client.post(
                "/learn/chat",
                headers={"X-User-Id": user_id},
                json={"deckId": deck_id, "userMessage": "gato"},
            )
                
            # Second attempt (wrong)
            client.post(
                "/learn/chat",
                headers={"X-User-Id": user_id},
                json={"deckId": deck_id, "userMessage": "katze"},
            )
                
            # Third attempt (correct)
            client.post(
                "/learn/chat",
                headers={"X-User-Id": user_id},
                json={"deckId": deck_id, "userMessage": "chat"},
            )
        
        # Verify the card was graded as "good" (third attempt correct)
        updated_card = card_repo.cards[card_id]
        assert updated_card["lastGrade"] == "good"
        assert updated_card["lastGradedAt"] is not None
        
        reset_fn()

    def test_correct_on_fourth_attempt_grades_hard(self, client, monkeypatch, reset_session_store):
        """When user gets correct on fourth attempt, grade should be 'hard'."""
        from app.routers import learn as learn_router
        
        user_id = "test-user"
        deck_id = "deck-1"
        card_id = "card-1"
        
        deck_repo = StubDeckRepo(
            decks={
                deck_id: {
                    "id": deck_id,
                    "userId": user_id,
                    "name": "Italian Basics",
                    "language": "it-IT",
                    "createdAt": "2025-12-13T00:00:00Z",
                    "updatedAt": "2025-12-13T00:00:00Z",
                }
            }
        )
        card_repo = StubCardRepo(
            cards={
                card_id: {
                    "id": card_id,
                    "deckId": deck_id,
                    "userId": user_id,
                    "front": "water",
                    "back": "acqua",
                    "createdAt": "2025-12-13T00:00:00Z",
                    "updatedAt": "2025-12-13T00:00:00Z",
                    "dueAt": "2025-12-13T00:00:00Z",
                    "easeFactor": 2.5,
                    "repetitions": 0,
                    "intervalDays": 0,
                    "lastReviewedAt": None,
                    "lastGrade": None,
                    "lastGradedAt": None,
                }
            }
        )
        
        # Create mock client: three wrong attempts, fourth correct
        wrong_response = AgentResponse(
            feedback="Not quite. Try again.",
            is_correct=False,
            revealed=False,
            can_grade=False,
            normalization_notes=None,
        )
        correct_response = AgentResponse(
            feedback="Correct! 'Acqua' is water in Italian.",
            is_correct=True,
            revealed=False,
            can_grade=True,
            normalization_notes=None,
        )
        mock_client, reset_fn = create_mock_foundry_client([
            wrong_response,
            wrong_response,
            wrong_response,
            correct_response,
        ])
        
        monkeypatch.setattr(learn_router, "get_deck_repository", lambda: deck_repo)
        monkeypatch.setattr(learn_router, "get_card_repository", lambda: card_repo)
        monkeypatch.setattr(learn_router, "utc_now_iso", lambda: "2025-12-13T00:00:00Z")
        
        with patch("app.agents.foundry_client.get_foundry_client", return_value=mock_client):
            # Start a session
            client.post(
                "/learn/start",
                headers={"X-User-Id": user_id},
                json={"deckId": deck_id},
            )
                
            # Four attempts: 3 wrong, then 1 correct
            for i in range(4):
                client.post(
                    "/learn/chat",
                    headers={"X-User-Id": user_id},
                    json={"deckId": deck_id, "userMessage": f"attempt {i+1}"},
                )
        
        # Verify the card was graded as "hard" (fourth attempt correct)
        updated_card = card_repo.cards[card_id]
        assert updated_card["lastGrade"] == "hard"
        assert updated_card["lastGradedAt"] is not None
        
        reset_fn()

    def test_correct_on_many_attempts_grades_hard(self, client, monkeypatch, reset_session_store):
        """When user gets correct after many attempts (>3), grade should be 'hard'."""
        from app.routers import learn as learn_router
        
        user_id = "test-user"
        deck_id = "deck-1"
        card_id = "card-1"
        
        deck_repo = StubDeckRepo(
            decks={
                deck_id: {
                    "id": deck_id,
                    "userId": user_id,
                    "name": "Spanish Basics",
                    "language": "es-ES",
                    "createdAt": "2025-12-13T00:00:00Z",
                    "updatedAt": "2025-12-13T00:00:00Z",
                }
            }
        )
        card_repo = StubCardRepo(
            cards={
                card_id: {
                    "id": card_id,
                    "deckId": deck_id,
                    "userId": user_id,
                    "front": "book",
                    "back": "libro",
                    "createdAt": "2025-12-13T00:00:00Z",
                    "updatedAt": "2025-12-13T00:00:00Z",
                    "dueAt": "2025-12-13T00:00:00Z",
                    "easeFactor": 2.5,
                    "repetitions": 0,
                    "intervalDays": 0,
                    "lastReviewedAt": None,
                    "lastGrade": None,
                    "lastGradedAt": None,
                }
            }
        )
        
        # Create mock client: 9 wrong attempts, then correct on 10th
        wrong_response = AgentResponse(
            feedback="Not quite. Try again.",
            is_correct=False,
            revealed=False,
            can_grade=False,
            normalization_notes=None,
        )
        correct_response = AgentResponse(
            feedback="Finally! 'Libro' is correct!",
            is_correct=True,
            revealed=False,
            can_grade=True,
            normalization_notes=None,
        )
        mock_client, reset_fn = create_mock_foundry_client([
            *[wrong_response for _ in range(9)],
            correct_response,
        ])
        
        monkeypatch.setattr(learn_router, "get_deck_repository", lambda: deck_repo)
        monkeypatch.setattr(learn_router, "get_card_repository", lambda: card_repo)
        monkeypatch.setattr(learn_router, "utc_now_iso", lambda: "2025-12-13T00:00:00Z")
        
        with patch("app.agents.foundry_client.get_foundry_client", return_value=mock_client):
            # Start a session
            client.post(
                "/learn/start",
                headers={"X-User-Id": user_id},
                json={"deckId": deck_id},
            )
                
            # 10 attempts: 9 wrong, then 1 correct
            for i in range(10):
                client.post(
                    "/learn/chat",
                    headers={"X-User-Id": user_id},
                    json={"deckId": deck_id, "userMessage": f"attempt {i+1}"},
                )
        
        # Verify the card was graded as "hard" (10th attempt correct)
        updated_card = card_repo.cards[card_id]
        assert updated_card["lastGrade"] == "hard"
        assert updated_card["lastGradedAt"] is not None
        
        reset_fn()


class TestAgentDrivenGradingReveal:
    """Tests for agent-driven grading when the answer is revealed."""

    def test_revealed_on_first_attempt_grades_again(self, client, monkeypatch, reset_session_store):
        """When answer is revealed on first attempt, grade should be 'again'."""
        from app.routers import learn as learn_router
        
        user_id = "test-user"
        deck_id = "deck-1"
        card_id = "card-1"
        
        deck_repo = StubDeckRepo(
            decks={
                deck_id: {
                    "id": deck_id,
                    "userId": user_id,
                    "name": "German Basics",
                    "language": "de-DE",
                    "createdAt": "2025-12-13T00:00:00Z",
                    "updatedAt": "2025-12-13T00:00:00Z",
                }
            }
        )
        card_repo = StubCardRepo(
            cards={
                card_id: {
                    "id": card_id,
                    "deckId": deck_id,
                    "userId": user_id,
                    "front": "house",
                    "back": "Haus",
                    "createdAt": "2025-12-13T00:00:00Z",
                    "updatedAt": "2025-12-13T00:00:00Z",
                    "dueAt": "2025-12-13T00:00:00Z",
                    "easeFactor": 2.5,
                    "repetitions": 0,
                    "intervalDays": 0,
                    "lastReviewedAt": None,
                    "lastGrade": None,
                    "lastGradedAt": None,
                }
            }
        )
        
        # Create mock client that reveals the answer on first attempt
        mock_client, reset_fn = create_mock_foundry_client([
            AgentResponse(
                feedback="The answer is 'Haus'. Let me know when you're ready for the next card.",
                is_correct=False,
                revealed=True,
                can_grade=True,
                normalization_notes=None,
            )
        ])
        
        monkeypatch.setattr(learn_router, "get_deck_repository", lambda: deck_repo)
        monkeypatch.setattr(learn_router, "get_card_repository", lambda: card_repo)
        monkeypatch.setattr(learn_router, "utc_now_iso", lambda: "2025-12-13T00:00:00Z")
        
        with patch("app.agents.foundry_client.get_foundry_client", return_value=mock_client):
            # Start a session
            client.post(
                "/learn/start",
                headers={"X-User-Id": user_id},
                json={"deckId": deck_id},
            )
                
            # User asks to reveal the answer
            client.post(
                "/learn/chat",
                headers={"X-User-Id": user_id},
                json={"deckId": deck_id, "userMessage": "I don't know, please reveal the answer"},
            )
        
        # Verify the card was graded as "again" (revealed)
        updated_card = card_repo.cards[card_id]
        assert updated_card["lastGrade"] == "again"
        assert updated_card["lastGradedAt"] is not None
        # Verify due scheduling for "again" (2 minutes later)
        assert updated_card["dueAt"] == "2025-12-13T00:02:00Z"
        
        reset_fn()

    def test_revealed_after_multiple_attempts_grades_again(self, client, monkeypatch, reset_session_store):
        """When answer is revealed after multiple wrong attempts, grade should be 'again'."""
        from app.routers import learn as learn_router
        
        user_id = "test-user"
        deck_id = "deck-1"
        card_id = "card-1"
        
        deck_repo = StubDeckRepo(
            decks={
                deck_id: {
                    "id": deck_id,
                    "userId": user_id,
                    "name": "French Basics",
                    "language": "fr-FR",
                    "createdAt": "2025-12-13T00:00:00Z",
                    "updatedAt": "2025-12-13T00:00:00Z",
                }
            }
        )
        card_repo = StubCardRepo(
            cards={
                card_id: {
                    "id": card_id,
                    "deckId": deck_id,
                    "userId": user_id,
                    "front": "book",
                    "back": "livre",
                    "createdAt": "2025-12-13T00:00:00Z",
                    "updatedAt": "2025-12-13T00:00:00Z",
                    "dueAt": "2025-12-13T00:00:00Z",
                    "easeFactor": 2.5,
                    "repetitions": 0,
                    "intervalDays": 0,
                    "lastReviewedAt": None,
                    "lastGrade": None,
                    "lastGradedAt": None,
                }
            }
        )
        
        # Create mock client: 3 wrong attempts, then reveal
        wrong_response = AgentResponse(
            feedback="Not quite. Try again.",
            is_correct=False,
            revealed=False,
            can_grade=False,
            normalization_notes=None,
        )
        reveal_response = AgentResponse(
            feedback="The answer is 'livre'.",
            is_correct=False,
            revealed=True,
            can_grade=True,
            normalization_notes=None,
        )
        mock_client, reset_fn = create_mock_foundry_client([
            wrong_response,
            wrong_response,
            wrong_response,
            reveal_response,
        ])
        
        monkeypatch.setattr(learn_router, "get_deck_repository", lambda: deck_repo)
        monkeypatch.setattr(learn_router, "get_card_repository", lambda: card_repo)
        monkeypatch.setattr(learn_router, "utc_now_iso", lambda: "2025-12-13T00:00:00Z")
        
        with patch("app.agents.foundry_client.get_foundry_client", return_value=mock_client):
            # Start a session
            client.post(
                "/learn/start",
                headers={"X-User-Id": user_id},
                json={"deckId": deck_id},
            )
                
            # 3 wrong attempts
            for i in range(3):
                client.post(
                    "/learn/chat",
                    headers={"X-User-Id": user_id},
                    json={"deckId": deck_id, "userMessage": f"wrong answer {i+1}"},
                )
                
            # 4th attempt: ask for reveal
            client.post(
                "/learn/chat",
                headers={"X-User-Id": user_id},
                json={"deckId": deck_id, "userMessage": "reveal the answer"},
            )
        
        # Verify the card was graded as "again" (revealed, regardless of attempt count)
        updated_card = card_repo.cards[card_id]
        assert updated_card["lastGrade"] == "again"
        assert updated_card["lastGradedAt"] is not None
        
        reset_fn()

    def test_revealed_after_many_attempts_grades_again(self, client, monkeypatch, reset_session_store):
        """Even after many attempts, revealed should always grade as 'again'."""
        from app.routers import learn as learn_router
        
        user_id = "test-user"
        deck_id = "deck-1"
        card_id = "card-1"
        
        deck_repo = StubDeckRepo(
            decks={
                deck_id: {
                    "id": deck_id,
                    "userId": user_id,
                    "name": "Italian Basics",
                    "language": "it-IT",
                    "createdAt": "2025-12-13T00:00:00Z",
                    "updatedAt": "2025-12-13T00:00:00Z",
                }
            }
        )
        card_repo = StubCardRepo(
            cards={
                card_id: {
                    "id": card_id,
                    "deckId": deck_id,
                    "userId": user_id,
                    "front": "sun",
                    "back": "sole",
                    "createdAt": "2025-12-13T00:00:00Z",
                    "updatedAt": "2025-12-13T00:00:00Z",
                    "dueAt": "2025-12-13T00:00:00Z",
                    "easeFactor": 2.5,
                    "repetitions": 0,
                    "intervalDays": 0,
                    "lastReviewedAt": None,
                    "lastGrade": None,
                    "lastGradedAt": None,
                }
            }
        )
        
        # Create mock client: 9 wrong attempts, then reveal on 10th
        wrong_response = AgentResponse(
            feedback="Not quite. Try again.",
            is_correct=False,
            revealed=False,
            can_grade=False,
            normalization_notes=None,
        )
        reveal_response = AgentResponse(
            feedback="The answer is 'sole'.",
            is_correct=False,
            revealed=True,
            can_grade=True,
            normalization_notes=None,
        )
        mock_client, reset_fn = create_mock_foundry_client([
            *[wrong_response for _ in range(9)],
            reveal_response,
        ])
        
        monkeypatch.setattr(learn_router, "get_deck_repository", lambda: deck_repo)
        monkeypatch.setattr(learn_router, "get_card_repository", lambda: card_repo)
        monkeypatch.setattr(learn_router, "utc_now_iso", lambda: "2025-12-13T00:00:00Z")
        
        with patch("app.agents.foundry_client.get_foundry_client", return_value=mock_client):
            # Start a session
            client.post(
                "/learn/start",
                headers={"X-User-Id": user_id},
                json={"deckId": deck_id},
            )
                
            # 10 attempts: 9 wrong, then reveal on 10th
            for i in range(10):
                client.post(
                    "/learn/chat",
                    headers={"X-User-Id": user_id},
                    json={"deckId": deck_id, "userMessage": f"attempt {i+1}"},
                )
        
        # Verify the card was graded as "again" (revealed always = again)
        updated_card = card_repo.cards[card_id]
        assert updated_card["lastGrade"] == "again"
        assert updated_card["lastGradedAt"] is not None
        
        reset_fn()


class TestGradePersistenceFields:
    """Tests for lastGrade and lastGradedAt field persistence."""

    def test_lastgrade_is_persisted_after_grading(self, client, monkeypatch, reset_session_store):
        """Verify lastGrade field is persisted in the card after grading."""
        from app.routers import learn as learn_router
        
        user_id = "test-user"
        deck_id = "deck-1"
        card_id = "card-1"
        
        deck_repo = StubDeckRepo(
            decks={
                deck_id: {
                    "id": deck_id,
                    "userId": user_id,
                    "name": "Spanish Basics",
                    "language": "es-ES",
                    "createdAt": "2025-12-13T00:00:00Z",
                    "updatedAt": "2025-12-13T00:00:00Z",
                }
            }
        )
        card_repo = StubCardRepo(
            cards={
                card_id: {
                    "id": card_id,
                    "deckId": deck_id,
                    "userId": user_id,
                    "front": "apple",
                    "back": "manzana",
                    "createdAt": "2025-12-13T00:00:00Z",
                    "updatedAt": "2025-12-13T00:00:00Z",
                    "dueAt": "2025-12-13T00:00:00Z",
                    "easeFactor": 2.5,
                    "repetitions": 0,
                    "intervalDays": 0,
                    "lastReviewedAt": None,
                    "lastGrade": None,
                    "lastGradedAt": None,
                }
            }
        )
        
        # Verify initial state
        assert card_repo.cards[card_id]["lastGrade"] is None
        assert card_repo.cards[card_id]["lastGradedAt"] is None
        
        mock_client, reset_fn = create_mock_foundry_client([
            AgentResponse(
                feedback="Correct!",
                is_correct=True,
                revealed=False,
                can_grade=True,
                normalization_notes=None,
            )
        ])
        
        monkeypatch.setattr(learn_router, "get_deck_repository", lambda: deck_repo)
        monkeypatch.setattr(learn_router, "get_card_repository", lambda: card_repo)
        monkeypatch.setattr(learn_router, "utc_now_iso", lambda: "2025-12-13T12:34:56Z")
        
        with patch("app.agents.foundry_client.get_foundry_client", return_value=mock_client):
            client.post(
                "/learn/start",
                headers={"X-User-Id": user_id},
                json={"deckId": deck_id},
            )
                
            client.post(
                "/learn/chat",
                headers={"X-User-Id": user_id},
                json={"deckId": deck_id, "userMessage": "manzana"},
            )
        
        # Verify fields are now set
        updated_card = card_repo.cards[card_id]
        assert updated_card["lastGrade"] == "easy"
        assert updated_card["lastGradedAt"] == "2025-12-13T12:34:56Z"
        # Also verify lastReviewedAt is set
        assert updated_card["lastReviewedAt"] == "2025-12-13T12:34:56Z"
        
        reset_fn()

    def test_grading_updates_srs_fields(self, client, monkeypatch, reset_session_store):
        """Verify SM-2 fields are updated along with grade fields."""
        from app.routers import learn as learn_router
        
        user_id = "test-user"
        deck_id = "deck-1"
        card_id = "card-1"
        
        deck_repo = StubDeckRepo(
            decks={
                deck_id: {
                    "id": deck_id,
                    "userId": user_id,
                    "name": "German Basics",
                    "language": "de-DE",
                    "createdAt": "2025-12-13T00:00:00Z",
                    "updatedAt": "2025-12-13T00:00:00Z",
                }
            }
        )
        card_repo = StubCardRepo(
            cards={
                card_id: {
                    "id": card_id,
                    "deckId": deck_id,
                    "userId": user_id,
                    "front": "tree",
                    "back": "Baum",
                    "createdAt": "2025-12-13T00:00:00Z",
                    "updatedAt": "2025-12-13T00:00:00Z",
                    "dueAt": "2025-12-13T00:00:00Z",
                    "easeFactor": 2.5,
                    "repetitions": 0,
                    "intervalDays": 0,
                    "lastReviewedAt": None,
                    "lastGrade": None,
                    "lastGradedAt": None,
                }
            }
        )
        
        mock_client, reset_fn = create_mock_foundry_client([
            AgentResponse(
                feedback="Correct!",
                is_correct=True,
                revealed=False,
                can_grade=True,
                normalization_notes=None,
            )
        ])
        
        monkeypatch.setattr(learn_router, "get_deck_repository", lambda: deck_repo)
        monkeypatch.setattr(learn_router, "get_card_repository", lambda: card_repo)
        monkeypatch.setattr(learn_router, "utc_now_iso", lambda: "2025-12-13T00:00:00Z")
        
        with patch("app.agents.foundry_client.get_foundry_client", return_value=mock_client):
            client.post(
                "/learn/start",
                headers={"X-User-Id": user_id},
                json={"deckId": deck_id},
            )
                
            client.post(
                "/learn/chat",
                headers={"X-User-Id": user_id},
                json={"deckId": deck_id, "userMessage": "Baum"},
            )
        
        updated_card = card_repo.cards[card_id]
        
        # Verify grade fields
        assert updated_card["lastGrade"] == "easy"
        assert updated_card["lastGradedAt"] is not None
        
        # Verify SM-2 fields were updated
        assert updated_card["repetitions"] >= 1  # Incremented from 0
        assert updated_card["dueAt"] != "2025-12-13T00:00:00Z"  # Changed from original
        
        reset_fn()

    def test_card_not_graded_until_resolved(self, client, monkeypatch, reset_session_store):
        """Verify card is not graded until agent returns isCorrect=True or revealed=True."""
        from app.routers import learn as learn_router
        
        user_id = "test-user"
        deck_id = "deck-1"
        card_id = "card-1"
        
        deck_repo = StubDeckRepo(
            decks={
                deck_id: {
                    "id": deck_id,
                    "userId": user_id,
                    "name": "Spanish Basics",
                    "language": "es-ES",
                    "createdAt": "2025-12-13T00:00:00Z",
                    "updatedAt": "2025-12-13T00:00:00Z",
                }
            }
        )
        card_repo = StubCardRepo(
            cards={
                card_id: {
                    "id": card_id,
                    "deckId": deck_id,
                    "userId": user_id,
                    "front": "red",
                    "back": "rojo",
                    "createdAt": "2025-12-13T00:00:00Z",
                    "updatedAt": "2025-12-13T00:00:00Z",
                    "dueAt": "2025-12-13T00:00:00Z",
                    "easeFactor": 2.5,
                    "repetitions": 0,
                    "intervalDays": 0,
                    "lastReviewedAt": None,
                    "lastGrade": None,
                    "lastGradedAt": None,
                }
            }
        )
        
        # Create mock that never resolves (always returns wrong, not revealed)
        wrong_response = AgentResponse(
            feedback="Not quite. Try again.",
            is_correct=False,
            revealed=False,
            can_grade=False,
            normalization_notes=None,
        )
        mock_client, reset_fn = create_mock_foundry_client([wrong_response])
        
        monkeypatch.setattr(learn_router, "get_deck_repository", lambda: deck_repo)
        monkeypatch.setattr(learn_router, "get_card_repository", lambda: card_repo)
        monkeypatch.setattr(learn_router, "utc_now_iso", lambda: "2025-12-13T00:00:00Z")
        
        with patch("app.agents.foundry_client.get_foundry_client", return_value=mock_client):
            client.post(
                "/learn/start",
                headers={"X-User-Id": user_id},
                json={"deckId": deck_id},
            )
                
            # Send 5 wrong attempts
            for i in range(5):
                resp = client.post(
                    "/learn/chat",
                    headers={"X-User-Id": user_id},
                    json={"deckId": deck_id, "userMessage": f"wrong {i+1}"},
                )
                assert resp.status_code == 200
                    
                # Card should not be graded yet
                assert card_repo.cards[card_id]["lastGrade"] is None
                assert card_repo.cards[card_id]["lastGradedAt"] is None
        
        reset_fn()
