"""Tests for the authentication module."""

import pytest
import jwt
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend

from app.auth.config import AuthSettings, get_auth_settings
from app.auth.token_validator import validate_token, TokenValidationError, clear_jwks_cache
from app.auth.dependencies import CurrentUser


# Generate a test RSA key pair for signing tokens
def generate_test_keys():
    """Generate a test RSA key pair."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    public_key = private_key.public_key()
    return private_key, public_key


TEST_PRIVATE_KEY, TEST_PUBLIC_KEY = generate_test_keys()

# Test configuration
TEST_TENANT_ID = "test-tenant-id-12345"
TEST_API_AUDIENCE = "api://test-backend-app-id"
TEST_API_APP_ID = "test-backend-app-id"


def create_test_token(
    sub: str = "test-user-id",
    aud: str = TEST_API_AUDIENCE,
    iss: str = f"https://login.microsoftonline.com/{TEST_TENANT_ID}/v2.0",
    exp_minutes: int = 60,
    private_key=None,
    additional_claims: dict = None,
) -> str:
    """Create a test JWT token."""
    if private_key is None:
        private_key = TEST_PRIVATE_KEY
    
    now = datetime.now(timezone.utc)
    claims = {
        "sub": sub,
        "aud": aud,
        "iss": iss,
        "iat": now,
        "exp": now + timedelta(minutes=exp_minutes),
        "preferred_username": "testuser@example.com",
        "name": "Test User",
        "scp": "Decks.ReadWrite Cards.ReadWrite",
    }
    
    if additional_claims:
        claims.update(additional_claims)
    
    return jwt.encode(claims, private_key, algorithm="RS256")


class TestAuthSettings:
    """Tests for AuthSettings configuration."""
    
    def test_authority_url(self):
        """Test authority URL is correctly formatted."""
        settings = AuthSettings(tenant_id="my-tenant")
        assert settings.authority == "https://login.microsoftonline.com/my-tenant"
    
    def test_issuer_url(self):
        """Test issuer URL includes v2.0 endpoint."""
        settings = AuthSettings(tenant_id="my-tenant")
        assert settings.issuer == "https://login.microsoftonline.com/my-tenant/v2.0"
    
    def test_jwks_uri(self):
        """Test JWKS URI is correctly formatted."""
        settings = AuthSettings(tenant_id="my-tenant")
        assert settings.jwks_uri == "https://login.microsoftonline.com/my-tenant/discovery/v2.0/keys"
    
    def test_is_configured_when_complete(self):
        """Test is_configured returns True when all required fields are set."""
        settings = AuthSettings(
            tenant_id="my-tenant",
            api_audience="api://my-app",
        )
        assert settings.is_configured() is True
    
    def test_is_configured_when_missing_tenant(self):
        """Test is_configured returns False when tenant_id is missing."""
        settings = AuthSettings(api_audience="api://my-app")
        assert settings.is_configured() is False
    
    def test_is_configured_when_missing_audience(self):
        """Test is_configured returns False when api_audience is missing."""
        settings = AuthSettings(tenant_id="my-tenant")
        assert settings.is_configured() is False


class TestCurrentUser:
    """Tests for CurrentUser model."""
    
    def test_from_token_claims(self):
        """Test creating CurrentUser from token claims."""
        claims = {
            "sub": "user-123",
            "name": "John Doe",
            "email": "john@example.com",
            "preferred_username": "john@example.com",
            "scp": "Decks.Read Cards.ReadWrite",
        }
        
        user = CurrentUser.from_token_claims(claims)
        
        assert user.user_id == "user-123"
        assert user.name == "John Doe"
        assert user.email == "john@example.com"
        assert user.preferred_username == "john@example.com"
        assert user.scopes == ["Decks.Read", "Cards.ReadWrite"]
    
    def test_from_token_claims_with_oid_fallback(self):
        """Test user_id falls back to oid claim if sub is missing."""
        claims = {
            "oid": "object-id-456",
            "name": "Jane Doe",
        }
        
        user = CurrentUser.from_token_claims(claims)
        
        assert user.user_id == "object-id-456"
    
    def test_from_token_claims_empty_scopes(self):
        """Test handling of missing scopes."""
        claims = {"sub": "user-123"}
        
        user = CurrentUser.from_token_claims(claims)
        
        assert user.scopes == []


class TestTokenValidation:
    """Tests for token validation logic."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Reset JWKS cache before each test."""
        clear_jwks_cache()
        yield
        clear_jwks_cache()
    
    @patch('app.auth.token_validator.get_auth_settings')
    @patch('app.auth.token_validator.get_jwks_client')
    def test_validate_valid_token(self, mock_jwks_client, mock_settings):
        """Test successful validation of a valid token."""
        # Configure mock settings
        mock_settings.return_value = AuthSettings(
            tenant_id=TEST_TENANT_ID,
            api_audience=TEST_API_AUDIENCE,
            api_app_id=TEST_API_APP_ID,
            enabled=True,
        )
        
        # Mock JWKS client to return our test public key
        mock_client = MagicMock()
        mock_client.get_signing_key.return_value = TEST_PUBLIC_KEY
        mock_jwks_client.return_value = mock_client
        
        # Create and validate token
        token = create_test_token()
        claims = validate_token(token)
        
        assert claims["sub"] == "test-user-id"
        assert claims["preferred_username"] == "testuser@example.com"
    
    @patch('app.auth.token_validator.get_auth_settings')
    @patch('app.auth.token_validator.get_jwks_client')
    def test_validate_expired_token(self, mock_jwks_client, mock_settings):
        """Test rejection of expired tokens."""
        mock_settings.return_value = AuthSettings(
            tenant_id=TEST_TENANT_ID,
            api_audience=TEST_API_AUDIENCE,
            enabled=True,
        )
        
        mock_client = MagicMock()
        mock_client.get_signing_key.return_value = TEST_PUBLIC_KEY
        mock_jwks_client.return_value = mock_client
        
        # Create an expired token
        token = create_test_token(exp_minutes=-10)  # Expired 10 minutes ago
        
        with pytest.raises(TokenValidationError) as exc_info:
            validate_token(token)
        
        assert "expired" in exc_info.value.message.lower()
    
    @patch('app.auth.token_validator.get_auth_settings')
    @patch('app.auth.token_validator.get_jwks_client')
    def test_validate_wrong_audience(self, mock_jwks_client, mock_settings):
        """Test rejection of tokens with wrong audience."""
        mock_settings.return_value = AuthSettings(
            tenant_id=TEST_TENANT_ID,
            api_audience=TEST_API_AUDIENCE,  # Expected audience
            enabled=True,
        )
        
        mock_client = MagicMock()
        mock_client.get_signing_key.return_value = TEST_PUBLIC_KEY
        mock_jwks_client.return_value = mock_client
        
        # Create token with wrong audience
        token = create_test_token(aud="api://wrong-app-id")
        
        with pytest.raises(TokenValidationError) as exc_info:
            validate_token(token)
        
        assert "audience" in exc_info.value.message.lower()
    
    @patch('app.auth.token_validator.get_auth_settings')
    @patch('app.auth.token_validator.get_jwks_client')
    def test_validate_wrong_issuer(self, mock_jwks_client, mock_settings):
        """Test rejection of tokens with wrong issuer."""
        mock_settings.return_value = AuthSettings(
            tenant_id=TEST_TENANT_ID,
            api_audience=TEST_API_AUDIENCE,
            enabled=True,
        )
        
        mock_client = MagicMock()
        mock_client.get_signing_key.return_value = TEST_PUBLIC_KEY
        mock_jwks_client.return_value = mock_client
        
        # Create token with wrong issuer
        token = create_test_token(iss="https://login.microsoftonline.com/wrong-tenant/v2.0")
        
        with pytest.raises(TokenValidationError) as exc_info:
            validate_token(token)
        
        assert "issuer" in exc_info.value.message.lower()
    
    @patch('app.auth.token_validator.get_auth_settings')
    def test_validate_unconfigured_auth(self, mock_settings):
        """Test error when auth is not configured."""
        mock_settings.return_value = AuthSettings(enabled=True)  # Missing tenant_id and api_audience
        
        token = create_test_token()
        
        with pytest.raises(TokenValidationError) as exc_info:
            validate_token(token)
        
        assert exc_info.value.status_code == 500
        assert "not configured" in exc_info.value.message.lower()
    
    @patch('app.auth.token_validator.get_auth_settings')
    @patch('app.auth.token_validator.get_jwks_client')
    def test_validate_malformed_token(self, mock_jwks_client, mock_settings):
        """Test rejection of malformed tokens."""
        mock_settings.return_value = AuthSettings(
            tenant_id=TEST_TENANT_ID,
            api_audience=TEST_API_AUDIENCE,
            enabled=True,
        )
        
        mock_client = MagicMock()
        mock_client.get_signing_key.side_effect = TokenValidationError("Invalid token format")
        mock_jwks_client.return_value = mock_client
        
        with pytest.raises(TokenValidationError):
            validate_token("not.a.valid.token")
