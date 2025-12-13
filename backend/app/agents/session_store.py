"""TTL-based session store for agent chat state."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import TypedDict

from cachetools import TTLCache


class ChatMessage(TypedDict):
    """A single chat message."""
    role: str  # "user" or "assistant"
    content: str


@dataclass
class AgentSessionState:
    """State for an agent tutoring session.
    
    Keyed by (user_id, deck_id). Tracks chat history and grading state
    for the current card being reviewed.
    """
    card_id: str
    messages: list[ChatMessage] = field(default_factory=list)
    explicit_reveal_request_count: int = 0
    revealed: bool = False
    is_correct: bool = False
    
    @property
    def can_grade(self) -> bool:
        """Whether the learner can submit a grade."""
        return self.is_correct or self.revealed
    
    def add_message(self, role: str, content: str) -> None:
        """Add a message to the conversation history.
        
        Keeps a bounded history to prevent context overflow.
        Max 20 messages (10 exchanges).
        """
        self.messages.append(ChatMessage(role=role, content=content))
        # Keep bounded history
        if len(self.messages) > 20:
            self.messages = self.messages[-20:]
    
    def reset_for_new_card(self, new_card_id: str) -> None:
        """Reset state for a new card while keeping the session."""
        self.card_id = new_card_id
        self.messages = []
        self.explicit_reveal_request_count = 0
        self.revealed = False
        self.is_correct = False


class SessionStore:
    """Thread-safe TTL-based session store.
    
    Stores AgentSessionState keyed by (user_id, deck_id).
    Sessions expire after TTL seconds of inactivity (sliding window).
    """
    
    # Default TTL: 30 minutes
    DEFAULT_TTL_SECONDS = 30 * 60
    # Max sessions to cache
    MAX_SESSIONS = 10000
    
    def __init__(self, ttl_seconds: int = DEFAULT_TTL_SECONDS, maxsize: int = MAX_SESSIONS):
        """Initialize the session store.
        
        Args:
            ttl_seconds: Time-to-live for sessions in seconds
            maxsize: Maximum number of sessions to cache
        """
        self._cache: TTLCache[tuple[str, str], AgentSessionState] = TTLCache(
            maxsize=maxsize, ttl=ttl_seconds
        )
        self._lock = threading.Lock()
    
    def _make_key(self, user_id: str, deck_id: str) -> tuple[str, str]:
        """Create a cache key from user and deck IDs."""
        return (user_id, deck_id)
    
    def get(self, user_id: str, deck_id: str) -> AgentSessionState | None:
        """Get session state for a user and deck.
        
        Returns None if no session exists or it has expired.
        Accessing the session refreshes its TTL (sliding window).
        """
        key = self._make_key(user_id, deck_id)
        with self._lock:
            state = self._cache.get(key)
            if state is not None:
                # Re-set to refresh TTL (sliding window)
                self._cache[key] = state
            return state
    
    def get_or_create(self, user_id: str, deck_id: str, card_id: str) -> AgentSessionState:
        """Get existing session or create a new one.
        
        If the session exists but the card_id differs, resets the session
        for the new card.
        """
        key = self._make_key(user_id, deck_id)
        with self._lock:
            state = self._cache.get(key)
            if state is None:
                # Create new session
                state = AgentSessionState(card_id=card_id)
                self._cache[key] = state
            elif state.card_id != card_id:
                # Card changed, reset for new card
                state.reset_for_new_card(card_id)
                self._cache[key] = state
            else:
                # Refresh TTL
                self._cache[key] = state
            return state
    
    def update(self, user_id: str, deck_id: str, state: AgentSessionState) -> None:
        """Update session state (also refreshes TTL)."""
        key = self._make_key(user_id, deck_id)
        with self._lock:
            self._cache[key] = state
    
    def reset(self, user_id: str, deck_id: str) -> None:
        """Remove session state for a user and deck."""
        key = self._make_key(user_id, deck_id)
        with self._lock:
            self._cache.pop(key, None)
    
    def clear(self) -> None:
        """Clear all sessions (for testing)."""
        with self._lock:
            self._cache.clear()


# Singleton instance
_session_store: SessionStore | None = None


def get_session_store() -> SessionStore:
    """Get the singleton session store instance."""
    global _session_store
    if _session_store is None:
        _session_store = SessionStore()
    return _session_store


def reset_session_store() -> None:
    """Reset the session store (for testing)."""
    global _session_store
    _session_store = None
