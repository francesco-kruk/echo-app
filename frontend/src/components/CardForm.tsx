import { useState, useEffect } from 'react';
import type { Card, CardCreate, CardUpdate } from '../api/client';
import './CardForm.css';

interface CardFormProps {
  card?: Card | null;
  onSubmit: (data: CardCreate | CardUpdate) => Promise<void>;
  onCancel: () => void;
}

export function CardForm({ card, onSubmit, onCancel }: CardFormProps) {
  const [front, setFront] = useState(card?.front || '');
  const [back, setBack] = useState(card?.back || '');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isEditing = !!card;

  useEffect(() => {
    if (card) {
      setFront(card.front);
      setBack(card.back);
    }
  }, [card]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!front.trim() || !back.trim()) return;

    setLoading(true);
    setError(null);

    try {
      await onSubmit({
        front: front.trim(),
        back: back.trim(),
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onCancel}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <h2>{isEditing ? 'Edit Card' : 'Create New Card'}</h2>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="front">Front *</label>
            <textarea
              id="front"
              value={front}
              onChange={(e) => setFront(e.target.value)}
              placeholder="Question or prompt"
              maxLength={2000}
              rows={3}
              required
              autoFocus
            />
          </div>
          <div className="form-group">
            <label htmlFor="back">Back *</label>
            <textarea
              id="back"
              value={back}
              onChange={(e) => setBack(e.target.value)}
              placeholder="Answer or translation"
              maxLength={2000}
              rows={3}
              required
            />
          </div>
          {error && <div className="form-error">{error}</div>}
          <div className="form-actions">
            <button type="button" onClick={onCancel} className="secondary" disabled={loading}>
              Cancel
            </button>
            <button type="submit" disabled={loading || !front.trim() || !back.trim()}>
              {loading ? 'Saving...' : isEditing ? 'Update' : 'Create'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
