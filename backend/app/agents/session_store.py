"""TTL-based session store for agent chat state."""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from typing import Literal, TypedDict

from cachetools import TTLCache


class ChatMessage(TypedDict):
    """A single chat message."""
    role: str  # "user" or "assistant"
    content: str


# Learning mode type
Mode = Literal["card", "free"]

# Grade type (mirrors learn.py Grade)
Grade = Literal["again", "hard", "good", "easy"]


class AddMessageResult(TypedDict):
    """Result of adding a message to the session."""
    window_rolled_over: bool  # True if trimming occurred (free mode only)


@dataclass
class AgentSessionState:
    """State for an agent tutoring session.
    
    Keyed by (user_id, deck_id). Tracks chat history and grading state
    for the current card being reviewed.
    
    Attributes:
        mode: Current learning mode ("card" or "free")
        card_id: Current card when in card mode, None in free mode
        attempt_count: Counts user turns while current card is active until first resolution
        resolved_at: ISO timestamp when card became resolved (correct or revealed)
        last_grade: The most recently applied grade
        agent_context_messages: Agent-visible conversation history
        ui_conversation_id: Stable ID for the session (deterministic UUID per user_id, deck_id, created_at)
        explicit_reveal_request_count: Number of explicit reveal requests (resets per-card)
        revealed: Whether the answer has been revealed (resets per-card)
        created_at: ISO timestamp when session was created
    """
    # Session identity
    ui_conversation_id: str
    created_at: str
    
    # Mode state
    mode: Mode = "card"
    card_id: str | None = None
    
    # Card resolution tracking
    attempt_count: int = 0
    resolved_at: str | None = None
    last_grade: Grade | None = None
    
    # Agent context (bounded history)
    agent_context_messages: list[ChatMessage] = field(default_factory=list)
    
    # Per-card reveal tracking (resets when card changes)
    explicit_reveal_request_count: int = 0
    revealed: bool = False
    
    # Legacy compatibility (will be derived from resolved_at)
    is_correct: bool = False
    
    # Card mode context limit
    CARD_MODE_MAX_MESSAGES: int = 6
    # Free mode context limit (last 10 messages)
    FREE_MODE_MAX_MESSAGES: int = 10
    
    @property
    def is_resolved(self) -> bool:
        """Whether the current card has been resolved."""
        return self.resolved_at is not None
    
    @property
    def messages(self) -> list[ChatMessage]:
        """Alias for agent_context_messages (legacy compatibility)."""
        return self.agent_context_messages
    
    def add_message(self, role: str, content: str) -> AddMessageResult:
        """Add a message to the conversation history.
        
        In card mode: bounded to CARD_MODE_MAX_MESSAGES (6 messages, 3 exchanges).
        In free mode: bounded to FREE_MODE_MAX_MESSAGES (10 messages, 5 exchanges).
        
        Returns:
            AddMessageResult with window_rolled_over=True if trimming occurred in free mode.
        """
        self.agent_context_messages.append(ChatMessage(role=role, content=content))
        
        window_rolled_over = False
        
        if self.mode == "card":
            # Card mode: smaller context, cleared between cards anyway
            max_messages = self.CARD_MODE_MAX_MESSAGES
            if len(self.agent_context_messages) > max_messages:
                self.agent_context_messages = self.agent_context_messages[-max_messages:]
        else:
            # Free mode: larger sliding window, signal when trimming occurs
            max_messages = self.FREE_MODE_MAX_MESSAGES
            if len(self.agent_context_messages) > max_messages:
                self.agent_context_messages = self.agent_context_messages[-max_messages:]
                window_rolled_over = True
        
        return AddMessageResult(window_rolled_over=window_rolled_over)
    
    def reset_agent_context(self) -> None:
        """Clear agent-visible history and reset per-card counters.
        
        Called when transitioning between cards or between modes.
        Preserves session identity and conversation ID.
        """
        self.agent_context_messages = []
        self.attempt_count = 0
        self.resolved_at = None
        self.explicit_reveal_request_count = 0
        self.revealed = False
        self.is_correct = False
    
    def start_card(self, card_id: str) -> None:
        """Start working on a new card.
        
        Sets mode to 'card', assigns the card_id, and resets per-card counters.
        Clears agent context for fresh conversation.
        
        Args:
            card_id: The ID of the card to start
        """
        self.mode = "card"
        self.card_id = card_id
        self.reset_agent_context()
    
    def start_free_mode(self) -> None:
        """Switch to free mode (no active card).
        
        Sets mode to 'free', clears card_id, and resets agent context.
        """
        self.mode = "free"
        self.card_id = None
        self.reset_agent_context()


def _generate_conversation_id(user_id: str, deck_id: str, created_at: str) -> str:
    """Generate a deterministic conversation ID for a session.
    
    Uses UUID5 with a fixed namespace to ensure the same inputs
    always produce the same conversation ID.
    
    Args:
        user_id: User ID
        deck_id: Deck ID  
        created_at: ISO timestamp when session was created
        
    Returns:
        Deterministic UUID string
    """
    namespace = uuid.UUID('6ba7b810-9dad-11d1-80b4-00c04fd430c8')
    combined = f"{user_id}:{deck_id}:{created_at}"
    return str(uuid.uuid5(namespace, combined))


def _utc_now_iso() -> str:
    """Get current UTC time as ISO string (avoid circular import from srs.time)."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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
    
    def _create_session(self, user_id: str, deck_id: str, card_id: str | None = None) -> AgentSessionState:
        """Create a new session with proper initialization.
        
        Args:
            user_id: User ID
            deck_id: Deck ID
            card_id: Optional card ID to start in card mode
            
        Returns:
            New AgentSessionState instance
        """
        created_at = _utc_now_iso()
        conversation_id = _generate_conversation_id(user_id, deck_id, created_at)
        
        state = AgentSessionState(
            ui_conversation_id=conversation_id,
            created_at=created_at,
        )
        
        # Initialize mode based on whether we have a card
        if card_id is not None:
            state.start_card(card_id)
        else:
            state.start_free_mode()
        
        return state
    
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
        """Get existing session or create a new one in card mode.
        
        If the session exists but the card_id differs, resets the session
        for the new card.
        
        Args:
            user_id: User ID
            deck_id: Deck ID
            card_id: Card ID to use (required for this method)
            
        Returns:
            Session state (existing or newly created)
        """
        key = self._make_key(user_id, deck_id)
        with self._lock:
            state = self._cache.get(key)
            if state is None:
                # Create new session in card mode
                state = self._create_session(user_id, deck_id, card_id)
                self._cache[key] = state
            elif state.card_id != card_id:
                # Card changed, reset for new card
                state.start_card(card_id)
                self._cache[key] = state
            else:
                # Refresh TTL
                self._cache[key] = state
            return state
    
    def get_or_create_session(self, user_id: str, deck_id: str, card_id: str | None = None) -> AgentSessionState:
        """Get existing session or create a new one.
        
        This is the preferred method for the new state machine. Unlike get_or_create(),
        it doesn't require a card_id and supports starting in free mode.
        
        Args:
            user_id: User ID
            deck_id: Deck ID
            card_id: Optional card ID. If provided and different from current, switches to that card.
                    If None, doesn't change current card state.
            
        Returns:
            Session state (existing or newly created)
        """
        key = self._make_key(user_id, deck_id)
        with self._lock:
            state = self._cache.get(key)
            if state is None:
                # Create new session
                state = self._create_session(user_id, deck_id, card_id)
                self._cache[key] = state
            elif card_id is not None and state.card_id != card_id:
                # Switching to a different card
                state.start_card(card_id)
                self._cache[key] = state
            else:
                # Refresh TTL only
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
