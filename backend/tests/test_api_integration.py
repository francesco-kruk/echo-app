"""Integration tests for the API with authentication."""

import pytest
from fastapi.testclient import TestClient
import os

# Ensure auth is disabled for these tests
os.environ["AUTH_ENABLED"] = "false"

from app.main import app


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


def cosmos_available():
    """Check if Cosmos DB is available for integration tests."""
    try:
        from app.db.cosmos import verify_connection
        return verify_connection()
    except Exception:
        return False


class TestHealthEndpoint:
    """Tests for the health endpoint (public)."""
    
    def test_healthz_no_auth_required(self, client):
        """Test that /healthz doesn't require authentication."""
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}
    
    def test_root_no_auth_required(self, client):
        """Test that / doesn't require authentication."""
        response = client.get("/")
        assert response.status_code == 200
        assert "name" in response.json()


class TestAuthDisabledMode:
    """Tests for API behavior when auth is disabled (dev mode)."""
    
    def test_decks_requires_user_id_header(self, client):
        """Test that /decks requires X-User-Id header when auth is disabled."""
        response = client.get("/decks")
        assert response.status_code == 401
        assert "X-User-Id" in response.json()["detail"]
    
    @pytest.mark.skipif(not cosmos_available(), reason="Cosmos DB not available")
    def test_decks_works_with_user_id_header(self, client):
        """Test that /decks works with X-User-Id header when auth is disabled."""
        response = client.get("/decks", headers={"X-User-Id": "test-user-123"})
        assert response.status_code == 200
        assert "decks" in response.json()
        assert "count" in response.json()
