"""Foundry Agent Framework client wrapper for tutoring agents."""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import BaseModel, ValidationError

from app.agents.personas import LanguageCode, build_system_prompt
from app.agents.session_store import AgentSessionState, ChatMessage

if TYPE_CHECKING:
    from agent_framework import ChatAgent

logger = logging.getLogger(__name__)


class AgentVerdict(BaseModel):
    """Structured verdict from the tutoring agent."""
    isCorrect: bool
    revealed: bool
    canGrade: bool
    feedback: str
    normalizationNotes: str | None = None


@dataclass
class AgentResponse:
    """Response from the tutoring agent."""
    feedback: str
    is_correct: bool
    revealed: bool
    can_grade: bool
    normalization_notes: str | None = None
    
    @classmethod
    def from_verdict(cls, verdict: AgentVerdict) -> "AgentResponse":
        """Create from a parsed verdict."""
        return cls(
            feedback=verdict.feedback,
            is_correct=verdict.isCorrect,
            revealed=verdict.revealed,
            can_grade=verdict.canGrade,
            normalization_notes=verdict.normalizationNotes,
        )
    
    @classmethod
    def error_response(cls, message: str) -> "AgentResponse":
        """Create an error response when agent fails."""
        return cls(
            feedback=message,
            is_correct=False,
            revealed=False,
            can_grade=False,
            normalization_notes=None,
        )


def _is_explicit_reveal_request(message: str) -> bool:
    """Check if the user message is an explicit reveal request.
    
    Explicit reveal wording (triggers reveal count):
    - "reveal the answer" / "please reveal the answer"
    - "show me the answer" / "tell me the answer"
    
    Non-triggering wording (requests tutoring, not reveal):
    - "I don't know" / "I need help" / "I'm stuck"
    """
    message_lower = message.lower().strip()
    
    reveal_patterns = [
        r"\breveal\b.*\banswer\b",
        r"\bshow\b.*\bme\b.*\banswer\b",
        r"\btell\b.*\bme\b.*\banswer\b",
        r"\bgive\b.*\bme\b.*\banswer\b",
        r"\bjust\b.*\btell\b.*\bme\b",
        r"\bwhat\b.*\bis\b.*\bthe\b.*\banswer\b",
    ]
    
    for pattern in reveal_patterns:
        if re.search(pattern, message_lower):
            return True
    
    return False


class FoundryAgentClient:
    """Client for interacting with the Microsoft Agent Framework.
    
    Uses Azure OpenAI Responses API for structured tutoring responses.
    """
    
    # Environment variable names
    ENV_ENDPOINT = "AZURE_OPENAI_ENDPOINT"
    ENV_DEPLOYMENT = "AZURE_OPENAI_RESPONSES_DEPLOYMENT_NAME"
    ENV_API_VERSION = "AZURE_OPENAI_API_VERSION"
    
    # Reveal threshold: require 2 explicit reveal requests
    REVEAL_THRESHOLD = 2
    
    def __init__(self):
        """Initialize the Foundry Agent client.
        
        Reads configuration from environment variables.
        Raises EnvironmentError if required variables are not set.
        """
        self._endpoint = os.environ.get(self.ENV_ENDPOINT)
        self._deployment = os.environ.get(self.ENV_DEPLOYMENT)
        # Agent Framework Azure Responses client currently requires api_version="preview"
        # Allow override via env, but default to the supported preview value
        self._api_version = os.environ.get(self.ENV_API_VERSION, "preview")
        
        # Validate required config
        if not self._endpoint:
            raise EnvironmentError(f"Missing required environment variable: {self.ENV_ENDPOINT}")
        if not self._deployment:
            raise EnvironmentError(f"Missing required environment variable: {self.ENV_DEPLOYMENT}")
        
        self._agent: ChatAgent | None = None
    
    def _get_agent(self, system_prompt: str) -> "ChatAgent":
        """Get a new agent instance configured with the given system prompt.
        
        Uses the documented `AzureOpenAIResponsesClient.create_agent(...)` factory.
        """
        # Lazy import to allow testing without agent-framework installed
        from agent_framework.azure import AzureOpenAIResponsesClient
        from azure.identity import DefaultAzureCredential

        client = AzureOpenAIResponsesClient(
            endpoint=self._endpoint,
            deployment_name=self._deployment,
            api_version=self._api_version,
            credential=DefaultAzureCredential(),
        )

        # Create the agent using the factory per official samples
        return client.create_agent(
            name="TutoringAgent",
            instructions=system_prompt,
        )
    
    async def send_message(
        self,
        user_message: str,
        language: LanguageCode,
        card_front: str,
        card_back: str,
        session_state: AgentSessionState,
    ) -> AgentResponse:
        """Send a message to the tutoring agent and get a response.
        
        Args:
            user_message: The learner's message
            language: The deck's target language
            card_front: The front of the current card
            card_back: The back of the current card (expected answer)
            session_state: The current session state (will be mutated)
            
        Returns:
            AgentResponse with the tutoring feedback and verdict
        """
        # Check for explicit reveal request
        if _is_explicit_reveal_request(user_message):
            session_state.explicit_reveal_request_count += 1
            logger.info(
                f"Explicit reveal request detected. Count: {session_state.explicit_reveal_request_count}"
            )
        
        # Determine if we should reveal
        should_reveal = session_state.explicit_reveal_request_count >= self.REVEAL_THRESHOLD
        
        # Build system prompt
        system_prompt = build_system_prompt(language, card_front, card_back)
        
        # Add reveal context if threshold reached
        if should_reveal and not session_state.revealed:
            system_prompt += "\n\nIMPORTANT: The learner has requested reveal twice. Set revealed=true and include the answer in your feedback."
        
        # Build conversation history for context
        messages_for_context = self._build_context_messages(session_state.messages)
        
        try:
            agent = self._get_agent(system_prompt)
            
            # Create thread with existing messages for context
            thread = agent.get_new_thread()

            # Add previous messages to thread (user-side turns for lightweight context)
            for msg in messages_for_context:
                if msg["role"] == "user":
                    await agent.run(msg["content"], thread=thread)

            # Send current message and get raw string response per docs
            raw_response = await agent.run(user_message, thread=thread)
            
            # Parse the JSON response
            response = self._parse_response(raw_response, should_reveal)
            
            # Update session state
            session_state.add_message("user", user_message)
            session_state.add_message("assistant", response.feedback)
            session_state.is_correct = response.is_correct
            session_state.revealed = response.revealed
            
            return response
            
        except Exception as e:
            logger.error(f"Agent call failed: {e}")
            return AgentResponse.error_response(
                "I'm having trouble processing your response. Please try again."
            )
    
    def _build_context_messages(self, messages: list[ChatMessage]) -> list[ChatMessage]:
        """Build context messages for the agent.
        
        Returns the last N message pairs to stay within context limits.
        """
        # Keep last 6 messages (3 exchanges) for context
        return messages[-6:] if len(messages) > 6 else messages
    
    def _parse_response(self, raw_response: object, should_reveal: bool) -> AgentResponse:
        """Parse the agent's JSON response.
        
        Args:
            raw_response: Raw response from the agent (may be a framework object)
            should_reveal: Whether reveal was triggered by threshold
            
        Returns:
            Parsed AgentResponse
        """
        # Normalize to text if the framework returns an object
        if not isinstance(raw_response, str):
            # Common attribute names across agent frameworks
            text_value = None
            for attr in ("output_text", "text", "content"):
                try:
                    val = getattr(raw_response, attr, None)
                    # Handle both attribute and callable forms
                    if callable(val):
                        val = val()
                    if isinstance(val, str) and val.strip():
                        text_value = val
                        break
                except Exception:
                    pass

            # As a last resort, try JSON/dict dumps or str()
            if text_value is None:
                try:
                    # Pydantic model style
                    if hasattr(raw_response, "model_dump"):
                        import json as _json
                        text_value = _json.dumps(raw_response.model_dump())
                    elif hasattr(raw_response, "to_json"):
                        text_value = raw_response.to_json()  # may return str
                    elif hasattr(raw_response, "__dict__"):
                        import json as _json
                        text_value = _json.dumps(raw_response.__dict__)
                except Exception:
                    pass

            if text_value is None:
                text_value = str(raw_response)

            raw_response = text_value

        # Try to extract JSON from the response
        try:
            # Try direct parse first
            data = json.loads(raw_response)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code block
            json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_response, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse JSON from code block: {raw_response[:200]}")
                    return self._fallback_response(raw_response, should_reveal)
            else:
                # Try to find any JSON object in the response
                json_match = re.search(r"\{[^{}]*\}", raw_response, re.DOTALL)
                if json_match:
                    try:
                        data = json.loads(json_match.group(0))
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse extracted JSON: {raw_response[:200]}")
                        return self._fallback_response(raw_response, should_reveal)
                else:
                    logger.warning(f"No JSON found in response: {raw_response[:200]}")
                    return self._fallback_response(raw_response, should_reveal)
        
        # Validate with Pydantic
        try:
            verdict = AgentVerdict(**data)
            return AgentResponse.from_verdict(verdict)
        except ValidationError as e:
            logger.warning(f"Invalid verdict structure: {e}")
            return self._fallback_response(raw_response, should_reveal)
    
    def _fallback_response(self, raw_response: str, should_reveal: bool) -> AgentResponse:
        """Create a fallback response when JSON parsing fails.
        
        Uses the raw response as feedback and defaults to safe values.
        """
        # Extract any meaningful text for feedback
        feedback = raw_response.strip()
        if len(feedback) > 500:
            feedback = feedback[:500] + "..."
        
        if not feedback:
            feedback = "Please try again with your answer."
        
        return AgentResponse(
            feedback=feedback,
            is_correct=False,
            revealed=should_reveal,
            can_grade=should_reveal,
            normalization_notes="Fallback: could not parse structured response",
        )


# Singleton instance
_foundry_client: FoundryAgentClient | None = None


def get_foundry_client() -> FoundryAgentClient:
    """Get the singleton Foundry client instance.
    
    Raises EnvironmentError if required config is missing.
    """
    global _foundry_client
    if _foundry_client is None:
        _foundry_client = FoundryAgentClient()
    return _foundry_client


def reset_foundry_client() -> None:
    """Reset the Foundry client (for testing)."""
    global _foundry_client
    _foundry_client = None
