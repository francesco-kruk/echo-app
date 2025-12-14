"""Tests for deck language field (immutability and validation)."""

import os
import pytest

# Ensure auth is disabled for these tests
os.environ["AUTH_ENABLED"] = "false"

from app.models.deck import DeckCreate, DeckUpdate, LanguageCode


class TestLanguageCodeType:
    """Tests for the LanguageCode type definition."""
    
    def test_valid_language_codes(self):
        """Test that all expected language codes are valid."""
        valid_codes: list[LanguageCode] = ["es-ES", "de-DE", "fr-FR", "it-IT"]
        for code in valid_codes:
            deck = DeckCreate(name="Test Deck", language=code)
            assert deck.language == code
    
    def test_language_required_on_create(self):
        """Test that language is required when creating a deck."""
        with pytest.raises(Exception):  # Pydantic validation error
            DeckCreate(name="Test Deck")  # Missing language


class TestDeckLanguageImmutability:
    """Tests for deck language immutability on update."""
    
    def test_deck_update_does_not_have_language(self):
        """Test that DeckUpdate model does not include language field."""
        update = DeckUpdate(name="Updated Name")
        model_fields = update.model_fields
        assert "language" not in model_fields
    
    def test_deck_update_ignores_extra_fields(self):
        """Test that extra fields like language are ignored in DeckUpdate."""
        # This should not raise, but language should be ignored
        update = DeckUpdate.model_validate({"name": "Updated Name", "language": "de-DE"})
        # The language field should not be in the model dump
        dump = update.model_dump(exclude_unset=True)
        assert "language" not in dump


class TestDeckCreateValidation:
    """Tests for DeckCreate validation."""
    
    def test_create_with_valid_language(self):
        """Test creating a deck with a valid language."""
        deck = DeckCreate(name="German Vocabulary", language="de-DE")
        assert deck.name == "German Vocabulary"
        assert deck.language == "de-DE"
    
    def test_create_rejects_invalid_language(self):
        """Test that invalid language codes are rejected."""
        with pytest.raises(Exception):  # Pydantic validation error
            DeckCreate(name="Test", language="invalid-lang")
    
    def test_create_rejects_empty_language(self):
        """Test that empty language is rejected."""
        with pytest.raises(Exception):
            DeckCreate(name="Test", language="")
