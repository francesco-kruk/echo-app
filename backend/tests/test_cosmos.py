"""Tests for Cosmos DB connection and authentication."""

import os
import pytest
from unittest.mock import patch, MagicMock

from app.db.cosmos import (
    CosmosDBSettings,
    get_settings,
    get_client,
    get_database,
    verify_connection,
    close_client,
    EMULATOR_KEY,
    EMULATOR_ENDPOINT,
)


class TestCosmosDBSettings:
    """Tests for CosmosDBSettings configuration."""

    def test_default_settings(self, monkeypatch):
        """Test default settings values."""
        monkeypatch.delenv("COSMOS_ENDPOINT", raising=False)
        monkeypatch.delenv("COSMOS_DB_NAME", raising=False)
        monkeypatch.delenv("COSMOS_DECKS_CONTAINER", raising=False)
        monkeypatch.delenv("COSMOS_CARDS_CONTAINER", raising=False)
        monkeypatch.delenv("COSMOS_EMULATOR", raising=False)
        
        settings = CosmosDBSettings()
        
        assert settings.endpoint == ""
        assert settings.database_name == "echoapp"
        assert settings.decks_container == "decks"
        assert settings.cards_container == "cards"
        assert settings.use_emulator is False

    def test_settings_from_environment(self, monkeypatch):
        """Test settings loaded from environment variables."""
        monkeypatch.setenv("COSMOS_ENDPOINT", "https://test.documents.azure.com:443/")
        monkeypatch.setenv("COSMOS_DB_NAME", "testdb")
        monkeypatch.setenv("COSMOS_DECKS_CONTAINER", "test-decks")
        monkeypatch.setenv("COSMOS_CARDS_CONTAINER", "test-cards")
        monkeypatch.setenv("COSMOS_EMULATOR", "false")
        
        settings = CosmosDBSettings()
        
        assert settings.endpoint == "https://test.documents.azure.com:443/"
        assert settings.database_name == "testdb"
        assert settings.decks_container == "test-decks"
        assert settings.cards_container == "test-cards"
        assert settings.use_emulator is False

    def test_emulator_mode_true(self, monkeypatch):
        """Test emulator mode when COSMOS_EMULATOR=true."""
        monkeypatch.setenv("COSMOS_EMULATOR", "true")
        
        settings = CosmosDBSettings()
        
        assert settings.use_emulator is True

    def test_emulator_mode_case_insensitive(self, monkeypatch):
        """Test emulator mode is case insensitive."""
        monkeypatch.setenv("COSMOS_EMULATOR", "TRUE")
        settings = CosmosDBSettings()
        assert settings.use_emulator is True
        
        monkeypatch.setenv("COSMOS_EMULATOR", "True")
        settings = CosmosDBSettings()
        assert settings.use_emulator is True

    def test_is_configured_with_endpoint(self, monkeypatch):
        """Test is_configured returns True when endpoint is set."""
        monkeypatch.setenv("COSMOS_ENDPOINT", "https://test.documents.azure.com:443/")
        monkeypatch.setenv("COSMOS_EMULATOR", "false")
        
        settings = CosmosDBSettings()
        
        assert settings.is_configured() is True

    def test_is_configured_without_endpoint(self, monkeypatch):
        """Test is_configured returns False when endpoint is not set."""
        monkeypatch.delenv("COSMOS_ENDPOINT", raising=False)
        monkeypatch.setenv("COSMOS_EMULATOR", "false")
        
        settings = CosmosDBSettings()
        
        assert settings.is_configured() is False

    def test_is_configured_in_emulator_mode(self, monkeypatch):
        """Test is_configured returns True when emulator mode is enabled."""
        monkeypatch.delenv("COSMOS_ENDPOINT", raising=False)
        monkeypatch.setenv("COSMOS_EMULATOR", "true")
        
        settings = CosmosDBSettings()
        
        assert settings.is_configured() is True


class TestCosmosDBClient:
    """Tests for Cosmos DB client initialization."""

    @pytest.fixture(autouse=True)
    def cleanup(self):
        """Cleanup client state after each test."""
        yield
        close_client()
        # Clear the cached settings
        get_settings.cache_clear()

    @patch("app.db.cosmos.CosmosClient")
    def test_get_client_emulator_mode(self, mock_cosmos_client, monkeypatch):
        """Test client uses emulator settings when COSMOS_EMULATOR=true."""
        monkeypatch.setenv("COSMOS_EMULATOR", "true")
        monkeypatch.delenv("COSMOS_ENDPOINT", raising=False)
        
        # Clear cached settings
        get_settings.cache_clear()
        
        client = get_client()
        
        mock_cosmos_client.assert_called_once()
        call_args = mock_cosmos_client.call_args
        # CosmosClient(url, credential, **kwargs) - check positional or keyword args
        assert call_args[0][0] == EMULATOR_ENDPOINT
        # credential can be positional or keyword argument
        if len(call_args[0]) > 1:
            assert call_args[0][1] == EMULATOR_KEY
        else:
            assert call_args[1].get("credential") == EMULATOR_KEY
        assert call_args[1]["connection_verify"] is False

    @patch("app.db.cosmos.DefaultAzureCredential")
    @patch("app.db.cosmos.CosmosClient")
    def test_get_client_azure_mode(self, mock_cosmos_client, mock_credential, monkeypatch):
        """Test client uses DefaultAzureCredential when not in emulator mode."""
        monkeypatch.setenv("COSMOS_EMULATOR", "false")
        monkeypatch.setenv("COSMOS_ENDPOINT", "https://test.documents.azure.com:443/")
        
        # Clear cached settings
        get_settings.cache_clear()
        
        client = get_client()
        
        mock_credential.assert_called_once()
        mock_cosmos_client.assert_called_once()
        call_args = mock_cosmos_client.call_args
        assert call_args[0][0] == "https://test.documents.azure.com:443/"

    def test_get_client_not_configured(self, monkeypatch):
        """Test RuntimeError when Cosmos DB is not configured."""
        monkeypatch.setenv("COSMOS_EMULATOR", "false")
        monkeypatch.delenv("COSMOS_ENDPOINT", raising=False)
        
        # Clear cached settings
        get_settings.cache_clear()
        
        with pytest.raises(RuntimeError) as exc_info:
            get_client()
        
        assert "not configured" in str(exc_info.value)


class TestCosmosDBConnection:
    """Tests for Cosmos DB connection verification."""

    @pytest.fixture(autouse=True)
    def cleanup(self):
        """Cleanup client state after each test."""
        yield
        close_client()
        get_settings.cache_clear()

    @patch("app.db.cosmos.get_database")
    @patch("app.db.cosmos.get_settings")
    def test_verify_connection_success(self, mock_settings, mock_database):
        """Test verify_connection returns True on success."""
        mock_settings.return_value = MagicMock(is_configured=lambda: True)
        mock_db = MagicMock()
        mock_database.return_value = mock_db
        
        result = verify_connection()
        
        assert result is True
        mock_db.read.assert_called_once()

    @patch("app.db.cosmos.get_settings")
    def test_verify_connection_not_configured(self, mock_settings):
        """Test verify_connection returns False when not configured."""
        mock_settings.return_value = MagicMock(is_configured=lambda: False)
        
        result = verify_connection()
        
        assert result is False

    @patch("app.db.cosmos.get_database")
    @patch("app.db.cosmos.get_settings")
    def test_verify_connection_failure(self, mock_settings, mock_database):
        """Test verify_connection returns False on connection error."""
        mock_settings.return_value = MagicMock(is_configured=lambda: True)
        mock_database.side_effect = Exception("Connection failed")
        
        result = verify_connection()
        
        assert result is False
