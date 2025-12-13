import { useCallback, useEffect, useRef, useState } from 'react';
import {
  getDecks,
  getLearnNext,
  postLearnReview,
  type Deck,
  type Card,
  type LearnGrade,
} from '../api/client';
import './LearnPage.css';

export function LearnPage() {
  const [decks, setDecks] = useState<Deck[]>([]);
  const [loadingDecks, setLoadingDecks] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [selectedDeck, setSelectedDeck] = useState<Deck | null>(null);

  const [loadingNext, setLoadingNext] = useState(false);
  const [card, setCard] = useState<Card | null>(null);
  const [showAnswer, setShowAnswer] = useState(false);
  const [nextDueAt, setNextDueAt] = useState<string | null>(null);

  const waitTimerRef = useRef<number | null>(null);

  const clearWaitTimer = () => {
    if (waitTimerRef.current != null) {
      window.clearTimeout(waitTimerRef.current);
      waitTimerRef.current = null;
    }
  };

  const fetchDecks = useCallback(async () => {
    setLoadingDecks(true);
    setError(null);
    try {
      const resp = await getDecks();
      setDecks(resp.decks);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load decks');
    } finally {
      setLoadingDecks(false);
    }
  }, []);

  const fetchNext = useCallback(async () => {
    if (!selectedDeck) return;

    clearWaitTimer();
    setLoadingNext(true);
    setError(null);

    try {
      const resp = await getLearnNext(selectedDeck.id);

      if (resp.card) {
        setCard(resp.card);
        setShowAnswer(false);
        setNextDueAt(null);
        return;
      }

      setNextDueAt(resp.nextDueAt ?? null);
      setCard(null);

      if (resp.nextDueAt) {
        const dueMs = new Date(resp.nextDueAt).getTime();
        const delayMs = Math.max(0, dueMs - Date.now() + 1500);
        waitTimerRef.current = window.setTimeout(() => {
          fetchNext();
        }, delayMs);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load next card');
    } finally {
      setLoadingNext(false);
    }
  }, [selectedDeck]);

  useEffect(() => {
    fetchDecks();
    return () => clearWaitTimer();
  }, [fetchDecks]);

  useEffect(() => {
    if (!selectedDeck) return;
    setCard(null);
    setShowAnswer(false);
    setNextDueAt(null);
    fetchNext();
  }, [selectedDeck, fetchNext]);

  const grade = async (g: LearnGrade) => {
    if (!selectedDeck || !card) return;

    setLoadingNext(true);
    setError(null);

    try {
      await postLearnReview({
        deckId: selectedDeck.id,
        cardId: card.id,
        grade: g,
      });

      setShowAnswer(false);
      await fetchNext();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit review');
    } finally {
      setLoadingNext(false);
    }
  };

  return (
    <div className="learn-page">
      <header className="page-header">
        <h1>Learn</h1>
      </header>

      {error && (
        <div className="error-message">
          {error}
          <button onClick={() => setError(null)} className="dismiss">×</button>
        </div>
      )}

      {!selectedDeck ? (
        <>
          <p className="learn-subtitle">Choose a deck to start.</p>
          {loadingDecks ? (
            <div className="loading">Loading decks...</div>
          ) : decks.length === 0 ? (
            <div className="empty-state">
              <p>No decks yet. Create one first.</p>
            </div>
          ) : (
            <div className="decks-grid">
              {decks.map((d) => (
                <div
                  key={d.id}
                  className="deck-card"
                  onClick={() => setSelectedDeck(d)}
                  role="button"
                >
                  <h3>{d.name}</h3>
                  {d.description && <p className="deck-description">{d.description}</p>}
                </div>
              ))}
            </div>
          )}
        </>
      ) : (
        <>
          <div className="learn-deck-title">Deck: {selectedDeck.name}</div>

          {loadingNext ? (
            <div className="loading">Loading next card...</div>
          ) : card ? (
            <div className="learn-card">
              <div className="learn-face">
                <div className="learn-label">Front</div>
                <div className="learn-text">{card.front}</div>
              </div>

              {!showAnswer ? (
                <div className="learn-actions">
                  <button onClick={() => setShowAnswer(true)}>Show answer</button>
                </div>
              ) : (
                <>
                  <div className="learn-face">
                    <div className="learn-label">Back</div>
                    <div className="learn-text">{card.back}</div>
                  </div>

                  <div className="learn-grades">
                    <button className="secondary" onClick={() => grade('again')}>Again</button>
                    <button className="secondary" onClick={() => grade('hard')}>Hard</button>
                    <button onClick={() => grade('good')}>Good</button>
                    <button onClick={() => grade('easy')}>Easy</button>
                  </div>
                </>
              )}
            </div>
          ) : nextDueAt ? (
            <div className="empty-state">
              <p>No cards due right now.</p>
              <p className="muted">Next due at {new Date(nextDueAt).toLocaleString()}</p>
            </div>
          ) : (
            <div className="empty-state">
              <p>No cards in this deck.</p>
            </div>
          )}
        </>
      )}
    </div>
  );
}
