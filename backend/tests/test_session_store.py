"""Tests for the TTL session store and AgentSessionState."""

import pytest

from app.agents.session_store import (
    AgentSessionState,
    AddMessageResult,
    ChatMessage,
    SessionStore,
    _generate_conversation_id,
)


class TestAgentSessionState:
    """Tests for AgentSessionState dataclass."""
    
    def test_initial_state(self):
        """Test initial state values."""
        state = AgentSessionState(
            ui_conversation_id="test-conv-id",
            created_at="2024-01-01T00:00:00Z",
        )
        
        assert state.mode == "card"
        assert state.card_id is None
        assert state.attempt_count == 0
        assert state.resolved_at is None
        assert state.last_grade is None
        assert state.agent_context_messages == []
        assert state.explicit_reveal_request_count == 0
        assert state.revealed is False
        assert state.is_correct is False
    
    def test_messages_property_alias(self):
        """Test that messages property is an alias for agent_context_messages."""
        state = AgentSessionState(
            ui_conversation_id="test-conv-id",
            created_at="2024-01-01T00:00:00Z",
        )
        
        state.agent_context_messages.append(ChatMessage(role="user", content="hello"))
        
        # messages should be the same as agent_context_messages
        assert state.messages == state.agent_context_messages
        assert len(state.messages) == 1
        assert state.messages[0]["content"] == "hello"
    
    def test_is_resolved_property(self):
        """Test is_resolved property."""
        state = AgentSessionState(
            ui_conversation_id="test-conv-id",
            created_at="2024-01-01T00:00:00Z",
        )
        
        assert state.is_resolved is False
        
        state.resolved_at = "2024-01-01T00:01:00Z"
        assert state.is_resolved is True


class TestAgentSessionStateHelpers:
    """Tests for AgentSessionState helper methods."""
    
    def test_start_card(self):
        """Test start_card method."""
        state = AgentSessionState(
            ui_conversation_id="test-conv-id",
            created_at="2024-01-01T00:00:00Z",
        )
        
        # Add some state
        state.mode = "free"
        state.card_id = None
        state.attempt_count = 5
        state.resolved_at = "2024-01-01T00:01:00Z"
        state.agent_context_messages.append(ChatMessage(role="user", content="hello"))
        state.explicit_reveal_request_count = 2
        state.revealed = True
        state.is_correct = True
        
        # Start a new card
        state.start_card("new-card-id")
        
        assert state.mode == "card"
        assert state.card_id == "new-card-id"
        assert state.attempt_count == 0
        assert state.resolved_at is None
        assert state.agent_context_messages == []
        assert state.explicit_reveal_request_count == 0
        assert state.revealed is False
        assert state.is_correct is False
    
    def test_start_free_mode(self):
        """Test start_free_mode method."""
        state = AgentSessionState(
            ui_conversation_id="test-conv-id",
            created_at="2024-01-01T00:00:00Z",
        )
        
        # Set up card mode state
        state.mode = "card"
        state.card_id = "card-123"
        state.attempt_count = 3
        state.agent_context_messages.append(ChatMessage(role="user", content="hello"))
        
        # Switch to free mode
        state.start_free_mode()
        
        assert state.mode == "free"
        assert state.card_id is None
        assert state.attempt_count == 0
        assert state.agent_context_messages == []
    
    def test_reset_agent_context(self):
        """Test reset_agent_context method."""
        state = AgentSessionState(
            ui_conversation_id="test-conv-id",
            created_at="2024-01-01T00:00:00Z",
        )
        
        # Set up some state
        state.attempt_count = 3
        state.resolved_at = "2024-01-01T00:01:00Z"
        state.agent_context_messages = [ChatMessage(role="user", content="hello")]
        state.explicit_reveal_request_count = 2
        state.revealed = True
        state.is_correct = True
        
        # Reset context
        state.reset_agent_context()
        
        assert state.attempt_count == 0
        assert state.resolved_at is None
        assert state.agent_context_messages == []
        assert state.explicit_reveal_request_count == 0
        assert state.revealed is False
        assert state.is_correct is False


class TestAddMessage:
    """Tests for add_message method with mode-specific behavior."""
    
    def test_add_message_basic(self):
        """Test basic message addition."""
        state = AgentSessionState(
            ui_conversation_id="test-conv-id",
            created_at="2024-01-01T00:00:00Z",
        )
        
        result = state.add_message("user", "hello")
        
        assert len(state.agent_context_messages) == 1
        assert state.agent_context_messages[0]["role"] == "user"
        assert state.agent_context_messages[0]["content"] == "hello"
        assert result["window_rolled_over"] is False
    
    def test_add_message_card_mode_bounds(self):
        """Test card mode message bounding (max 6 messages)."""
        state = AgentSessionState(
            ui_conversation_id="test-conv-id",
            created_at="2024-01-01T00:00:00Z",
            mode="card",
        )
        
        # Add 8 messages
        for i in range(8):
            state.add_message("user", f"message {i}")
        
        # Should be bounded to 6
        assert len(state.agent_context_messages) == 6
        # Should keep the latest messages
        assert state.agent_context_messages[0]["content"] == "message 2"
        assert state.agent_context_messages[-1]["content"] == "message 7"
    
    def test_add_message_free_mode_bounds(self):
        """Test free mode message bounding (max 10 messages)."""
        state = AgentSessionState(
            ui_conversation_id="test-conv-id",
            created_at="2024-01-01T00:00:00Z",
        )
        state.mode = "free"
        
        # Add 12 messages
        for i in range(12):
            state.add_message("user", f"message {i}")
        
        # Should be bounded to 10
        assert len(state.agent_context_messages) == 10
        # Should keep the latest messages
        assert state.agent_context_messages[0]["content"] == "message 2"
        assert state.agent_context_messages[-1]["content"] == "message 11"
    
    def test_add_message_free_mode_window_rollover_signal(self):
        """Test that window_rolled_over is True when trimming in free mode."""
        state = AgentSessionState(
            ui_conversation_id="test-conv-id",
            created_at="2024-01-01T00:00:00Z",
        )
        state.mode = "free"
        
        # Add 10 messages (at limit)
        for i in range(10):
            result = state.add_message("user", f"message {i}")
            assert result["window_rolled_over"] is False
        
        # Add 11th message - should trigger rollover
        result = state.add_message("user", "message 10")
        assert result["window_rolled_over"] is True
    
    def test_add_message_card_mode_no_rollover_signal(self):
        """Test that card mode doesn't signal rollover (it's cleared between cards)."""
        state = AgentSessionState(
            ui_conversation_id="test-conv-id",
            created_at="2024-01-01T00:00:00Z",
            mode="card",
        )
        
        # Add messages to exceed limit
        for i in range(8):
            result = state.add_message("user", f"message {i}")
            # Card mode should never signal rollover
            assert result["window_rolled_over"] is False


class TestSessionStore:
    """Tests for the TTL session store."""
    
    def test_session_store_get_or_create(self):
        """Test getting or creating a session."""
        store = SessionStore(ttl_seconds=60)
        state = store.get_or_create("user1", "deck1", "card1")
        
        assert isinstance(state, AgentSessionState)
        assert state.card_id == "card1"
        assert state.mode == "card"
        assert state.messages == []
        assert state.revealed is False
        assert state.is_correct is False
        assert state.ui_conversation_id is not None
        assert state.created_at is not None
    
    def test_session_store_get_or_create_session_with_card(self):
        """Test get_or_create_session with a card ID."""
        store = SessionStore(ttl_seconds=60)
        state = store.get_or_create_session("user1", "deck1", "card1")
        
        assert state.mode == "card"
        assert state.card_id == "card1"
    
    def test_session_store_get_or_create_session_without_card(self):
        """Test get_or_create_session without a card ID (free mode)."""
        store = SessionStore(ttl_seconds=60)
        state = store.get_or_create_session("user1", "deck1", None)
        
        assert state.mode == "free"
        assert state.card_id is None
    
    def test_session_store_reset(self):
        """Test resetting a session."""
        store = SessionStore(ttl_seconds=60)
        state = store.get_or_create("user1", "deck1", "card1")
        state.add_message("user", "test")
        store.update("user1", "deck1", state)
        
        store.reset("user1", "deck1")
        
        # Getting again should create a fresh session
        new_state = store.get_or_create("user1", "deck1", "card2")
        assert new_state.card_id == "card2"
        assert new_state.messages == []
    
    def test_session_store_card_change_resets(self):
        """Test that changing card resets the session via start_card."""
        store = SessionStore(ttl_seconds=60)
        state1 = store.get_or_create("user1", "deck1", "card1")
        state1.add_message("user", "test")
        state1.attempt_count = 5
        store.update("user1", "deck1", state1)
        
        # Get with different card ID
        state2 = store.get_or_create("user1", "deck1", "card2")
        
        assert state2.card_id == "card2"
        assert state2.messages == []  # Should be reset
        assert state2.attempt_count == 0  # Should be reset
    
    def test_session_store_same_card_preserves_state(self):
        """Test that getting with same card preserves state."""
        store = SessionStore(ttl_seconds=60)
        state1 = store.get_or_create("user1", "deck1", "card1")
        state1.add_message("user", "test")
        state1.attempt_count = 3
        store.update("user1", "deck1", state1)
        
        # Get with same card ID
        state2 = store.get_or_create("user1", "deck1", "card1")
        
        assert state2.card_id == "card1"
        assert len(state2.messages) == 1
        assert state2.attempt_count == 3
    
    def test_session_store_get_returns_none_for_missing(self):
        """Test that get returns None for missing session."""
        store = SessionStore(ttl_seconds=60)
        
        state = store.get("user1", "deck1")
        assert state is None
    
    def test_session_store_get_returns_existing(self):
        """Test that get returns existing session."""
        store = SessionStore(ttl_seconds=60)
        
        # Create a session
        created = store.get_or_create("user1", "deck1", "card1")
        created.attempt_count = 5
        store.update("user1", "deck1", created)
        
        # Get should return it
        fetched = store.get("user1", "deck1")
        assert fetched is not None
        assert fetched.attempt_count == 5
    
    def test_session_store_clear(self):
        """Test clearing all sessions."""
        store = SessionStore(ttl_seconds=60)
        
        store.get_or_create("user1", "deck1", "card1")
        store.get_or_create("user2", "deck2", "card2")
        
        store.clear()
        
        assert store.get("user1", "deck1") is None
        assert store.get("user2", "deck2") is None


class TestGenerateConversationId:
    """Tests for conversation ID generation."""
    
    def test_deterministic_generation(self):
        """Test that same inputs produce same conversation ID."""
        id1 = _generate_conversation_id("user1", "deck1", "2024-01-01T00:00:00Z")
        id2 = _generate_conversation_id("user1", "deck1", "2024-01-01T00:00:00Z")
        
        assert id1 == id2
    
    def test_different_inputs_produce_different_ids(self):
        """Test that different inputs produce different IDs."""
        id1 = _generate_conversation_id("user1", "deck1", "2024-01-01T00:00:00Z")
        id2 = _generate_conversation_id("user2", "deck1", "2024-01-01T00:00:00Z")
        id3 = _generate_conversation_id("user1", "deck2", "2024-01-01T00:00:00Z")
        id4 = _generate_conversation_id("user1", "deck1", "2024-01-01T00:01:00Z")
        
        # All should be different
        ids = {id1, id2, id3, id4}
        assert len(ids) == 4
    
    def test_returns_valid_uuid(self):
        """Test that returned value is a valid UUID string."""
        import uuid
        
        conv_id = _generate_conversation_id("user1", "deck1", "2024-01-01T00:00:00Z")
        
        # Should not raise
        parsed = uuid.UUID(conv_id)
        assert str(parsed) == conv_id
