"""Tests for learn agents chat functionality with mocked Foundry client."""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure auth is disabled for these tests
os.environ["AUTH_ENABLED"] = "false"
# Prevent agent client from requiring real credentials
os.environ["AZURE_OPENAI_ENDPOINT"] = "https://test.openai.azure.com/"
os.environ["AZURE_OPENAI_RESPONSES_DEPLOYMENT_NAME"] = "test-deployment"

from fastapi.testclient import TestClient


@pytest.fixture
def mock_foundry_client():
    """Create a mock Foundry client."""
    from app.agents.foundry_client import AgentResponse, reset_foundry_client
    
    # Reset singleton before test
    reset_foundry_client()
    
    mock_client = MagicMock()
    mock_client.send_message = AsyncMock(return_value=AgentResponse(
        feedback="Good try! Think about the translation more carefully.",
        is_correct=False,
        revealed=False,
        can_grade=False,
        normalization_notes=None,
    ))
    
    with patch("app.agents.foundry_client.get_foundry_client", return_value=mock_client):
        yield mock_client
    
    # Reset after test
    reset_foundry_client()


@pytest.fixture
def mock_correct_response():
    """Mock response for correct answer."""
    from app.agents.foundry_client import AgentResponse
    return AgentResponse(
        feedback="Excellent! That's correct!",
        is_correct=True,
        revealed=False,
        can_grade=True,
        normalization_notes=None,
    )


@pytest.fixture
def mock_revealed_response():
    """Mock response when answer is revealed."""
    from app.agents.foundry_client import AgentResponse
    return AgentResponse(
        feedback="The answer is 'Hund'. Let me know when you're ready to grade.",
        is_correct=False,
        revealed=True,
        can_grade=True,
        normalization_notes=None,
    )


class TestSessionStore:
    """Tests for the TTL session store."""
    
    def test_session_store_get_or_create(self):
        """Test getting or creating a session."""
        from app.agents.session_store import SessionStore, AgentSessionState
        
        store = SessionStore(ttl_seconds=60)
        state = store.get_or_create("user1", "deck1", "card1")
        
        assert isinstance(state, AgentSessionState)
        assert state.card_id == "card1"
        assert state.messages == []
        assert state.revealed is False
        assert state.is_correct is False
    
    def test_session_store_reset(self):
        """Test resetting a session."""
        from app.agents.session_store import SessionStore
        
        store = SessionStore(ttl_seconds=60)
        state = store.get_or_create("user1", "deck1", "card1")
        state.messages.append({"role": "user", "content": "test"})
        store.update("user1", "deck1", state)
        
        store.reset("user1", "deck1")
        
        # Getting again should create a fresh session
        new_state = store.get_or_create("user1", "deck1", "card2")
        assert new_state.card_id == "card2"
        assert new_state.messages == []
    
    def test_session_store_card_change_resets(self):
        """Test that changing card resets the session."""
        from app.agents.session_store import SessionStore
        
        store = SessionStore(ttl_seconds=60)
        state1 = store.get_or_create("user1", "deck1", "card1")
        state1.messages.append({"role": "user", "content": "test"})
        store.update("user1", "deck1", state1)
        
        # Get with different card ID
        state2 = store.get_or_create("user1", "deck1", "card2")
        
        assert state2.card_id == "card2"
        assert state2.messages == []  # Should be reset


class TestExplicitRevealDetection:
    """Tests for explicit reveal request detection."""
    
    def test_reveal_patterns_detected(self):
        """Test that explicit reveal patterns are detected."""
        from app.agents.foundry_client import _is_explicit_reveal_request
        
        reveal_messages = [
            "reveal the answer",
            "Please reveal the answer",
            "show me the answer",
            "tell me the answer",
            "just tell me",
            "what is the answer",
        ]
        
        for msg in reveal_messages:
            assert _is_explicit_reveal_request(msg), f"Should detect: {msg}"
    
    def test_non_reveal_patterns_not_detected(self):
        """Test that tutoring requests are not detected as reveals."""
        from app.agents.foundry_client import _is_explicit_reveal_request
        
        non_reveal_messages = [
            "I don't know",
            "I need help",
            "I'm stuck",
            "Can you give me a hint?",
            "What does this mean?",
            "I think it's dog",
        ]
        
        for msg in non_reveal_messages:
            assert not _is_explicit_reveal_request(msg), f"Should NOT detect: {msg}"


class TestAgentVerdictParsing:
    """Tests for parsing agent JSON verdicts."""
    
    def test_parse_valid_json(self):
        """Test parsing valid JSON verdict."""
        from app.agents.foundry_client import FoundryAgentClient
        
        client = FoundryAgentClient()
        response_json = '{"isCorrect": true, "revealed": false, "canGrade": true, "feedback": "Well done!"}'
        
        result = client._parse_response(response_json, should_reveal=False)
        
        assert result.is_correct is True
        assert result.revealed is False
        assert result.can_grade is True
        assert result.feedback == "Well done!"
    
    def test_parse_json_in_markdown(self):
        """Test parsing JSON wrapped in markdown code block."""
        from app.agents.foundry_client import FoundryAgentClient
        
        client = FoundryAgentClient()
        response = '''Here's my evaluation:
```json
{"isCorrect": false, "revealed": false, "canGrade": false, "feedback": "Not quite!"}
```
'''
        
        result = client._parse_response(response, should_reveal=False)
        
        assert result.is_correct is False
        assert result.feedback == "Not quite!"
    
    def test_fallback_on_invalid_json(self):
        """Test fallback behavior when JSON is invalid."""
        from app.agents.foundry_client import FoundryAgentClient
        
        client = FoundryAgentClient()
        response = "I couldn't understand that. Please try again."
        
        result = client._parse_response(response, should_reveal=False)
        
        assert result.is_correct is False
        assert result.can_grade is False
        assert result.feedback == response  # Uses raw response as feedback


class TestPersonasAndPrompts:
    """Tests for persona configuration and prompt building."""
    
    def test_all_languages_have_personas(self):
        """Test that all supported languages have persona configs."""
        from app.agents.personas import SUPPORTED_LANGUAGES
        
        expected_languages = ["es-ES", "de-DE", "fr-FR", "it-IT"]
        
        for lang in expected_languages:
            assert lang in SUPPORTED_LANGUAGES
            config = SUPPORTED_LANGUAGES[lang]
            assert "name" in config
            assert "agent_name" in config
            assert "country" in config
    
    def test_build_system_prompt_includes_card_context(self):
        """Test that system prompt includes card context."""
        from app.agents.personas import build_system_prompt
        
        prompt = build_system_prompt("de-DE", "dog", "Hund")
        
        assert "dog" in prompt
        # Note: card back (Hund) should be in the prompt for the agent to know the answer
        assert "Hund" in prompt
        assert "German" in prompt or "Goethe" in prompt
    
    def test_build_system_prompt_includes_json_instructions(self):
        """Test that system prompt includes JSON output instructions."""
        from app.agents.personas import build_system_prompt
        
        prompt = build_system_prompt("es-ES", "hello", "hola")
        
        assert "JSON" in prompt or "json" in prompt
        assert "isCorrect" in prompt
        assert "canGrade" in prompt
