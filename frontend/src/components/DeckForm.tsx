import { useState, useEffect } from 'react';
import type { Deck, DeckCreate, DeckUpdate, LanguageCode } from '../api/client';
import { SUPPORTED_LANGUAGES } from '../api/client';
import './DeckForm.css';

interface DeckFormProps {
  deck?: Deck | null;
  onSubmit: (data: DeckCreate | DeckUpdate) => Promise<void>;
  onCancel: () => void;
}

export function DeckForm({ deck, onSubmit, onCancel }: DeckFormProps) {
  const [name, setName] = useState(deck?.name || '');
  const [description, setDescription] = useState(deck?.description || '');
  const [language, setLanguage] = useState<LanguageCode>(deck?.language || 'es-ES');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isEditing = !!deck;

  useEffect(() => {
    if (deck) {
      setName(deck.name);
      setDescription(deck.description || '');
      setLanguage(deck.language);
    }
  }, [deck]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;

    setLoading(true);
    setError(null);

    try {
      if (isEditing) {
        // When editing, don't include language (immutable)
        await onSubmit({
          name: name.trim(),
          description: description.trim() || null,
        } as DeckUpdate);
      } else {
        // When creating, include language
        await onSubmit({
          name: name.trim(),
          description: description.trim() || null,
          language,
        } as DeckCreate);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onCancel}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <h2>{isEditing ? 'Edit Deck' : 'Create New Deck'}</h2>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="name">Name *</label>
            <input
              id="name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Deck name"
              maxLength={200}
              required
              autoFocus
            />
          </div>
          <div className="form-group">
            <label htmlFor="language">
              Language *
              {isEditing && <span className="immutable-hint"> (cannot be changed)</span>}
            </label>
            <select
              id="language"
              value={language}
              onChange={(e) => setLanguage(e.target.value as LanguageCode)}
              disabled={isEditing}
              required
            >
              {SUPPORTED_LANGUAGES.map((lang) => (
                <option key={lang.code} value={lang.code}>
                  {lang.name}
                </option>
              ))}
            </select>
            {!isEditing && (
              <small className="form-hint">
                This determines which AI tutor will help you learn this deck.
              </small>
            )}
          </div>
          <div className="form-group">
            <label htmlFor="description">Description</label>
            <textarea
              id="description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional description"
              maxLength={1000}
              rows={3}
            />
          </div>
          {error && <div className="form-error">{error}</div>}
          <div className="form-actions">
            <button type="button" onClick={onCancel} className="secondary" disabled={loading}>
              Cancel
            </button>
            <button type="submit" disabled={loading || !name.trim()}>
              {loading ? 'Saving...' : isEditing ? 'Update' : 'Create'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
