"""JWT token validator for Entra ID tokens."""

import time
from typing import Any
import httpx
import jwt
from jwt import PyJWKClient, PyJWKClientError
from cachetools import TTLCache

from .config import get_auth_settings


class TokenValidationError(Exception):
    """Raised when token validation fails."""

    def __init__(self, message: str, status_code: int = 401):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class JWKSClient:
    """
    JWKS client with caching for Entra ID public keys.
    
    This client fetches and caches the JSON Web Key Set (JWKS) from Entra ID
    to validate JWT signatures. Keys are cached for 1 hour to reduce network calls.
    """

    def __init__(self, jwks_uri: str, cache_ttl: int = 3600):
        self.jwks_uri = jwks_uri
        self._keys_cache: TTLCache[str, dict[str, Any]] = TTLCache(maxsize=10, ttl=cache_ttl)
        self._jwk_client: PyJWKClient | None = None

    def _get_client(self) -> PyJWKClient:
        """Get or create the PyJWKClient."""
        if self._jwk_client is None:
            self._jwk_client = PyJWKClient(
                self.jwks_uri,
                cache_jwk_set=True,
                lifespan=3600,  # Cache for 1 hour
            )
        return self._jwk_client

    def get_signing_key(self, token: str) -> Any:
        """
        Get the signing key for a token from the JWKS.
        
        Args:
            token: The JWT token to get the signing key for.
            
        Returns:
            The signing key for the token.
            
        Raises:
            TokenValidationError: If the key cannot be found.
        """
        try:
            client = self._get_client()
            signing_key = client.get_signing_key_from_jwt(token)
            return signing_key.key
        except PyJWKClientError as e:
            raise TokenValidationError(f"Failed to get signing key: {str(e)}")
        except jwt.exceptions.DecodeError as e:
            raise TokenValidationError(f"Invalid token format: {str(e)}")


# Global JWKS client instance (initialized lazily)
_jwks_client: JWKSClient | None = None


def get_jwks_client() -> JWKSClient:
    """Get the global JWKS client instance."""
    global _jwks_client
    if _jwks_client is None:
        settings = get_auth_settings()
        _jwks_client = JWKSClient(settings.jwks_uri)
    return _jwks_client


def validate_token(token: str) -> dict[str, Any]:
    """
    Validate an Entra ID access token.
    
    This function validates:
    - Token signature using Entra ID's public keys (JWKS)
    - Token expiration (exp claim)
    - Token issuer (iss claim) matches the expected Entra tenant (v1.0 or v2.0 format)
    - Token audience (aud claim) matches the backend API
    
    Args:
        token: The JWT access token to validate.
        
    Returns:
        The decoded token claims if valid.
        
    Raises:
        TokenValidationError: If the token is invalid.
    """
    settings = get_auth_settings()

    if not settings.is_configured():
        raise TokenValidationError(
            "Authentication not configured. Set AZURE_TENANT_ID and AZURE_API_SCOPE.",
            status_code=500,
        )

    try:
        # Get the signing key from JWKS
        jwks_client = get_jwks_client()
        signing_key = jwks_client.get_signing_key(token)

        # Decode and validate the token
        # Entra ID tokens use RS256 algorithm
        # Accept both v1.0 and v2.0 issuer formats since token version depends on
        # the accessTokenAcceptedVersion setting in the API app registration
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            audience=settings.api_audience,
            options={
                "require": ["exp", "iat", "iss", "aud", "sub"],
                "verify_exp": True,
                "verify_iat": True,
                "verify_iss": False,  # We'll validate issuer manually for multi-issuer support
                "verify_aud": True,
            },
        )

        # Manually validate issuer against valid issuers list (v1.0 and v2.0 formats)
        token_issuer = claims.get("iss", "")
        if token_issuer not in settings.valid_issuers:
            raise TokenValidationError(
                f"Invalid token issuer. Expected one of {settings.valid_issuers}, got {token_issuer}"
            )

        return claims

    except jwt.ExpiredSignatureError:
        raise TokenValidationError("Token has expired")
    except jwt.InvalidAudienceError:
        raise TokenValidationError("Invalid token audience")
    except jwt.InvalidIssuerError:
        raise TokenValidationError("Invalid token issuer")
    except jwt.InvalidTokenError as e:
        raise TokenValidationError(f"Invalid token: {str(e)}")


def clear_jwks_cache() -> None:
    """Clear the JWKS cache. Useful for testing or when keys are rotated."""
    global _jwks_client
    _jwks_client = None
