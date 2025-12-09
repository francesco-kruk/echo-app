import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  getDecks,
  createDeck,
  updateDeck,
  deleteDeck,
  seedSampleData,
  type Deck,
  type DeckCreate,
  type DeckUpdate,
} from '../api/client';
import { DeckForm } from '../components/DeckForm';
import './DecksPage.css';

export function DecksPage() {
  const navigate = useNavigate();
  const [decks, setDecks] = useState<Deck[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [editingDeck, setEditingDeck] = useState<Deck | null>(null);
  const [seeding, setSeeding] = useState(false);

  const fetchDecks = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await getDecks();
      setDecks(response.decks);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load decks');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDecks();
  }, [fetchDecks]);

  const handleCreateDeck = async (data: DeckCreate | DeckUpdate) => {
    await createDeck(data as DeckCreate);
    setShowForm(false);
    fetchDecks();
  };

  const handleUpdateDeck = async (data: DeckCreate | DeckUpdate) => {
    if (!editingDeck) return;
    await updateDeck(editingDeck.id, data);
    setEditingDeck(null);
    fetchDecks();
  };

  const handleDeleteDeck = async (deck: Deck) => {
    if (!confirm(`Delete "${deck.name}" and all its cards?`)) return;
    try {
      await deleteDeck(deck.id);
      fetchDecks();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete deck');
    }
  };

  const handleSeedData = async () => {
    if (!confirm('This will create sample flashcard decks. Continue?')) return;
    setSeeding(true);
    setError(null);
    try {
      const result = await seedSampleData();
      alert(`${result.message}\nCreated ${result.decks_created} decks with ${result.cards_created} cards.`);
      fetchDecks();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to seed data');
    } finally {
      setSeeding(false);
    }
  };

  const openCards = (deck: Deck) => {
    navigate(`/decks/${deck.id}/cards`);
  };

  return (
    <div className="decks-page">
      <header className="page-header">
        <h1>My Decks</h1>
        <div className="header-actions">
          <button onClick={handleSeedData} className="secondary" disabled={seeding}>
            {seeding ? 'Creating...' : '📦 Create Sample Data'}
          </button>
          <button onClick={() => setShowForm(true)}>+ New Deck</button>
        </div>
      </header>

      {error && (
        <div className="error-message">
          {error}
          <button onClick={() => setError(null)} className="dismiss">×</button>
        </div>
      )}

      {loading ? (
        <div className="loading">Loading decks...</div>
      ) : decks.length === 0 ? (
        <div className="empty-state">
          <p>No decks yet. Create one to get started!</p>
          <button onClick={() => setShowForm(true)}>Create Your First Deck</button>
        </div>
      ) : (
        <div className="decks-grid">
          {decks.map((deck) => (
            <div key={deck.id} className="deck-card" onClick={() => openCards(deck)}>
              <h3>{deck.name}</h3>
              {deck.description && <p className="deck-description">{deck.description}</p>}
              <div className="deck-meta">
                <span>Created: {new Date(deck.createdAt).toLocaleDateString()}</span>
              </div>
              <div className="deck-actions" onClick={(e) => e.stopPropagation()}>
                <button
                  onClick={() => setEditingDeck(deck)}
                  className="icon-btn"
                  title="Edit deck"
                >
                  ✏️
                </button>
                <button
                  onClick={() => handleDeleteDeck(deck)}
                  className="icon-btn danger"
                  title="Delete deck"
                >
                  🗑️
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {showForm && (
        <DeckForm
          onSubmit={handleCreateDeck}
          onCancel={() => setShowForm(false)}
        />
      )}

      {editingDeck && (
        <DeckForm
          deck={editingDeck}
          onSubmit={handleUpdateDeck}
          onCancel={() => setEditingDeck(null)}
        />
      )}
    </div>
  );
}
