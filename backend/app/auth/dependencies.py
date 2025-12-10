"""FastAPI dependencies for authentication."""

from typing import Annotated
from fastapi import Depends, HTTPException, Header, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from .config import get_auth_settings
from .token_validator import validate_token, TokenValidationError


# HTTP Bearer security scheme
bearer_scheme = HTTPBearer(
    scheme_name="Bearer",
    description="Enter your Entra ID access token",
    auto_error=False,  # Don't auto-error; we handle it for better error messages
)


class CurrentUser(BaseModel):
    """
    Represents the authenticated user extracted from the token.
    
    Attributes:
        user_id: The unique identifier (sub claim) from the token.
        name: The user's display name if available.
        email: The user's email address if available.
        preferred_username: The user's preferred username (usually email).
        scopes: List of scopes granted to the token.
    """

    user_id: str
    name: str | None = None
    email: str | None = None
    preferred_username: str | None = None
    scopes: list[str] = []

    @classmethod
    def from_token_claims(cls, claims: dict) -> "CurrentUser":
        """Create a CurrentUser from decoded token claims."""
        # Extract scopes from the 'scp' claim (space-separated string)
        scopes_str = claims.get("scp", "")
        scopes = scopes_str.split() if scopes_str else []

        return cls(
            user_id=claims.get("sub", claims.get("oid", "")),
            name=claims.get("name"),
            email=claims.get("email"),
            preferred_username=claims.get("preferred_username"),
            scopes=scopes,
        )


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    x_user_id: str | None = Header(None, description="User ID header (dev fallback)"),
) -> CurrentUser:
    """
    FastAPI dependency that validates the Bearer token and returns the current user.
    
    This dependency:
    1. Extracts the Bearer token from the Authorization header
    2. Validates the token against Entra ID
    3. Returns a CurrentUser object with user information
    
    For local development without Entra, set AUTH_ENABLED=false and provide X-User-Id header.
    
    Raises:
        HTTPException: 401 if token is missing or invalid, 403 if insufficient permissions.
    """
    settings = get_auth_settings()

    # If auth is disabled (local dev mode), use the X-User-Id header fallback
    if not settings.enabled:
        if x_user_id:
            return CurrentUser(
                user_id=x_user_id,
                name="Local Dev User",
                preferred_username=x_user_id,
                scopes=["Decks.ReadWrite", "Cards.ReadWrite"],
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication disabled but no X-User-Id header provided",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check for Bearer token
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        # Validate the token
        claims = validate_token(credentials.credentials)
        return CurrentUser.from_token_claims(claims)

    except TokenValidationError as e:
        raise HTTPException(
            status_code=e.status_code,
            detail=e.message,
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_scope(*required_scopes: str):
    """
    Factory function that creates a dependency to require specific scopes.
    
    Usage:
        @router.get("/protected", dependencies=[Depends(require_scope("Decks.Read"))])
        async def protected_route(user: CurrentUser = Depends(get_current_user)):
            ...
    
    Args:
        required_scopes: One or more scopes that must be present in the token.
    
    Returns:
        A dependency function that validates the required scopes.
    """

    async def check_scopes(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        settings = get_auth_settings()

        # Skip scope checking if auth is disabled
        if not settings.enabled:
            return user

        # Check if user has any of the required scopes
        user_scopes = set(user.scopes)
        required = set(required_scopes)

        if not user_scopes.intersection(required):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required scopes: {', '.join(required_scopes)}",
            )

        return user

    return check_scopes


# Convenience dependency aliases
require_auth = Depends(get_current_user)
