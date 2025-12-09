import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  getCardsForDeck,
  getDeck,
  createCard,
  updateCard,
  deleteCard,
  type Card,
  type Deck,
  type CardCreate,
  type CardUpdate,
} from '../api/client';
import { CardForm } from '../components/CardForm';
import './CardsPage.css';

export function CardsPage() {
  const { deckId } = useParams<{ deckId: string }>();
  const navigate = useNavigate();
  
  const [deck, setDeck] = useState<Deck | null>(null);
  const [cards, setCards] = useState<Card[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [editingCard, setEditingCard] = useState<Card | null>(null);
  const [flippedCards, setFlippedCards] = useState<Set<string>>(new Set());

  const fetchData = useCallback(async () => {
    if (!deckId) return;
    
    setLoading(true);
    setError(null);
    try {
      const [deckData, cardsData] = await Promise.all([
        getDeck(deckId),
        getCardsForDeck(deckId),
      ]);
      setDeck(deckData);
      setCards(cardsData.cards);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load cards');
    } finally {
      setLoading(false);
    }
  }, [deckId]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleCreateCard = async (data: CardCreate | CardUpdate) => {
    if (!deckId) return;
    await createCard(deckId, data as CardCreate);
    setShowForm(false);
    fetchData();
  };

  const handleUpdateCard = async (data: CardCreate | CardUpdate) => {
    if (!deckId || !editingCard) return;
    await updateCard(deckId, editingCard.id, data);
    setEditingCard(null);
    fetchData();
  };

  const handleDeleteCard = async (card: Card) => {
    if (!deckId) return;
    if (!confirm(`Delete this card?`)) return;
    try {
      await deleteCard(deckId, card.id);
      fetchData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete card');
    }
  };

  const toggleCardFlip = (cardId: string) => {
    setFlippedCards((prev) => {
      const next = new Set(prev);
      if (next.has(cardId)) {
        next.delete(cardId);
      } else {
        next.add(cardId);
      }
      return next;
    });
  };

  return (
    <div className="cards-page">
      <header className="page-header">
        <div className="header-left">
          <button onClick={() => navigate('/decks')} className="back-btn">
            ← Back to Decks
          </button>
          <div className="header-title">
            <h1>{deck?.name || 'Loading...'}</h1>
            {deck?.description && <p className="deck-description">{deck.description}</p>}
          </div>
        </div>
        <div className="header-actions">
          <button onClick={() => setShowForm(true)}>+ New Card</button>
        </div>
      </header>

      {error && (
        <div className="error-message">
          {error}
          <button onClick={() => setError(null)} className="dismiss">×</button>
        </div>
      )}

      {loading ? (
        <div className="loading">Loading cards...</div>
      ) : cards.length === 0 ? (
        <div className="empty-state">
          <p>No cards in this deck yet. Add some flashcards!</p>
          <button onClick={() => setShowForm(true)}>Add Your First Card</button>
        </div>
      ) : (
        <>
          <div className="cards-count">{cards.length} card{cards.length !== 1 ? 's' : ''}</div>
          <div className="cards-grid">
            {cards.map((card) => (
              <div
                key={card.id}
                className={`flashcard ${flippedCards.has(card.id) ? 'flipped' : ''}`}
                onClick={() => toggleCardFlip(card.id)}
              >
                <div className="flashcard-inner">
                  <div className="flashcard-front">
                    <div className="card-content">{card.front}</div>
                    <div className="flip-hint">Click to flip</div>
                  </div>
                  <div className="flashcard-back">
                    <div className="card-content">{card.back}</div>
                    <div className="flip-hint">Click to flip</div>
                  </div>
                </div>
                <div className="card-actions" onClick={(e) => e.stopPropagation()}>
                  <button
                    onClick={() => setEditingCard(card)}
                    className="icon-btn"
                    title="Edit card"
                  >
                    ✏️
                  </button>
                  <button
                    onClick={() => handleDeleteCard(card)}
                    className="icon-btn danger"
                    title="Delete card"
                  >
                    🗑️
                  </button>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {showForm && (
        <CardForm
          onSubmit={handleCreateCard}
          onCancel={() => setShowForm(false)}
        />
      )}

      {editingCard && (
        <CardForm
          card={editingCard}
          onSubmit={handleUpdateCard}
          onCancel={() => setEditingCard(null)}
        />
      )}
    </div>
  );
}
