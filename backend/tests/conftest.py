"""Pytest configuration and fixtures."""

import os
import pytest

# Ensure auth is disabled during tests by default
os.environ.setdefault("AUTH_ENABLED", "false")


@pytest.fixture
def auth_disabled_env(monkeypatch):
    """Fixture that ensures AUTH_ENABLED is false."""
    monkeypatch.setenv("AUTH_ENABLED", "false")


@pytest.fixture
def auth_enabled_env(monkeypatch):
    """Fixture that enables auth with test configuration."""
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("AZURE_TENANT_ID", "test-tenant-id")
    monkeypatch.setenv("AZURE_API_SCOPE", "api://test-backend-app")
    monkeypatch.setenv("AZURE_API_APP_ID", "test-backend-app")
