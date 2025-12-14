import { useCallback, useEffect, useRef, useState } from 'react';
import {
  getLearnAgents,
  getLearnNext,
  postLearnStart,
  postLearnChat,
  postLearnReview,
  SUPPORTED_LANGUAGES,
  type LearnAgentSummary,
  type LearnChatResponse,
  type LearnGrade,
} from '../api/client';
import './LearnPage.css';

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export function LearnPage() {
  // Agent selection state
  const [agents, setAgents] = useState<LearnAgentSummary[]>([]);
  const [loadingAgents, setLoadingAgents] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Selected agent/deck state
  const [selectedAgent, setSelectedAgent] = useState<LearnAgentSummary | null>(null);

  // Learning session state
  const [cardId, setCardId] = useState<string | null>(null);
  const [cardFront, setCardFront] = useState<string | null>(null);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [canGrade, setCanGrade] = useState(false);
  const [isCorrect, setIsCorrect] = useState(false);
  const [revealed, setRevealed] = useState(false);

  // UI state
  const [loadingSession, setLoadingSession] = useState(false);
  const [sendingMessage, setSendingMessage] = useState(false);
  const [userInput, setUserInput] = useState('');
  const [nextDueAt, setNextDueAt] = useState<string | null>(null);

  const chatEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Auto-scroll to bottom of chat
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages]);

  // Focus input when session starts
  useEffect(() => {
    if (selectedAgent && cardId) {
      inputRef.current?.focus();
    }
  }, [selectedAgent, cardId]);

  // Fetch available agents
  const fetchAgents = useCallback(async () => {
    setLoadingAgents(true);
    setError(null);
    try {
      const resp = await getLearnAgents();
      setAgents(resp.agents);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load agents');
    } finally {
      setLoadingAgents(false);
    }
  }, []);

  useEffect(() => {
    fetchAgents();
  }, [fetchAgents]);

  // Start learning session with selected agent
  const startSession = useCallback(async (agent: LearnAgentSummary) => {
    setSelectedAgent(agent);
    setLoadingSession(true);
    setError(null);
    setChatMessages([]);
    setCanGrade(false);
    setIsCorrect(false);
    setRevealed(false);
    setNextDueAt(null);

    try {
      const resp = await postLearnStart({ deckId: agent.deckId });
      setCardId(resp.cardId);
      setCardFront(resp.cardFront);
      setChatMessages([{ role: 'assistant', content: resp.assistantMessage }]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start session');
      setSelectedAgent(null);
    } finally {
      setLoadingSession(false);
    }
  }, []);

  // Send a chat message
  const sendMessage = useCallback(async () => {
    if (!selectedAgent || !cardId || !userInput.trim() || sendingMessage) return;

    const message = userInput.trim();
    setUserInput('');
    setSendingMessage(true);
    setChatMessages(prev => [...prev, { role: 'user', content: message }]);

    try {
      const resp: LearnChatResponse = await postLearnChat({
        deckId: selectedAgent.deckId,
        userMessage: message,
        cardId,
      });

      setChatMessages(prev => [...prev, { role: 'assistant', content: resp.assistantMessage }]);
      setCanGrade(resp.canGrade);
      setIsCorrect(resp.isCorrect);
      setRevealed(resp.revealed);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send message');
    } finally {
      setSendingMessage(false);
    }
  }, [selectedAgent, cardId, userInput, sendingMessage]);

  // Handle grade submission
  const submitGrade = useCallback(async (grade: LearnGrade) => {
    if (!selectedAgent || !cardId) return;

    setLoadingSession(true);
    setError(null);

    try {
      // Submit the grade
      await postLearnReview({
        deckId: selectedAgent.deckId,
        cardId,
        grade,
      });

      // Reset chat state and fetch next card
      setChatMessages([]);
      setCanGrade(false);
      setIsCorrect(false);
      setRevealed(false);

      // Try to get next card
      const nextResp = await getLearnNext(selectedAgent.deckId);
      if (nextResp.card) {
        // Start new session with next card
        const startResp = await postLearnStart({ deckId: selectedAgent.deckId });
        setCardId(startResp.cardId);
        setCardFront(startResp.cardFront);
        setChatMessages([{ role: 'assistant', content: startResp.assistantMessage }]);
      } else {
        // No more cards due
        setCardId(null);
        setCardFront(null);
        setNextDueAt(nextResp.nextDueAt);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit grade');
    } finally {
      setLoadingSession(false);
    }
  }, [selectedAgent, cardId]);

  // Go back to agent selection
  const backToAgents = useCallback(() => {
    setSelectedAgent(null);
    setCardId(null);
    setCardFront(null);
    setChatMessages([]);
    setCanGrade(false);
    setIsCorrect(false);
    setRevealed(false);
    setNextDueAt(null);
    setError(null);
    fetchAgents();
  }, [fetchAgents]);

  // Handle Enter key in input
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  // Get language display name
  const getLanguageName = (code: string) => {
    const lang = SUPPORTED_LANGUAGES.find(l => l.code === code);
    return lang?.name || code;
  };

  return (
    <div className="learn-page">
      <header className="page-header">
        <h1>Learn</h1>
        {selectedAgent && (
          <button className="back-button" onClick={backToAgents}>
            ← Back to Agents
          </button>
        )}
      </header>

      {error && (
        <div className="error-message">
          {error}
          <button onClick={() => setError(null)} className="dismiss">×</button>
        </div>
      )}

      {!selectedAgent ? (
        // Agent selection view
        <>
          <p className="learn-subtitle">Choose an agent to start practicing.</p>
          {loadingAgents ? (
            <div className="loading">Loading available agents...</div>
          ) : agents.length === 0 ? (
            <div className="empty-state">
              <p>No agents available right now.</p>
              <p className="muted">Add cards to your decks or wait for cards to become due.</p>
            </div>
          ) : (
            <div className="agents-grid">
              {agents.map((agent) => (
                <div
                  key={agent.deckId}
                  className="agent-card"
                  onClick={() => startSession(agent)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => e.key === 'Enter' && startSession(agent)}
                >
                  <div className="agent-avatar">
                    {agent.agentName.charAt(0)}
                  </div>
                  <div className="agent-info">
                    <h3>{agent.agentName}</h3>
                    <p className="agent-deck">{agent.deckName}</p>
                    <p className="agent-language">{getLanguageName(agent.language)}</p>
                    <p className="agent-due">{agent.dueCardCount} card{agent.dueCardCount !== 1 ? 's' : ''} due</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      ) : loadingSession ? (
        <div className="loading">Loading session...</div>
      ) : cardId && cardFront ? (
        // Chat view
        <div className="chat-container">
          <div className="chat-header">
            <div className="chat-agent-info">
              <div className="agent-avatar small">
                {selectedAgent.agentName.charAt(0)}
              </div>
              <div>
                <strong>{selectedAgent.agentName}</strong>
                <span className="chat-language">{getLanguageName(selectedAgent.language)}</span>
              </div>
            </div>
            <div className="chat-card-prompt">
              <span className="prompt-label">Card:</span> {cardFront}
            </div>
          </div>

          <div className="chat-messages">
            {chatMessages.map((msg, idx) => (
              <div key={idx} className={`chat-message ${msg.role}`}>
                <div className="message-content">{msg.content}</div>
              </div>
            ))}
            {sendingMessage && (
              <div className="chat-message assistant">
                <div className="message-content typing">
                  <span className="dot"></span>
                  <span className="dot"></span>
                  <span className="dot"></span>
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>

          {canGrade ? (
            <div className="grade-section">
              <p className="grade-prompt">
                {isCorrect ? '✓ Correct!' : revealed ? 'Answer revealed.' : ''} How well did you know this?
              </p>
              <div className="learn-grades">
                <button className="grade-btn again" onClick={() => submitGrade('again')}>
                  Again
                  <span className="grade-hint">Forgot</span>
                </button>
                <button className="grade-btn hard" onClick={() => submitGrade('hard')}>
                  Hard
                  <span className="grade-hint">Struggled</span>
                </button>
                <button className="grade-btn good" onClick={() => submitGrade('good')}>
                  Good
                  <span className="grade-hint">Remembered</span>
                </button>
                <button className="grade-btn easy" onClick={() => submitGrade('easy')}>
                  Easy
                  <span className="grade-hint">Instant</span>
                </button>
              </div>
            </div>
          ) : (
            <div className="chat-input-container">
              <input
                ref={inputRef}
                type="text"
                value={userInput}
                onChange={(e) => setUserInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Type your answer..."
                disabled={sendingMessage}
                maxLength={2000}
              />
              <button 
                onClick={sendMessage} 
                disabled={!userInput.trim() || sendingMessage}
                className="send-button"
              >
                Send
              </button>
            </div>
          )}
        </div>
      ) : nextDueAt ? (
        <div className="empty-state">
          <p>🎉 Great job! You've reviewed all due cards.</p>
          <p className="muted">Next card due at {new Date(nextDueAt).toLocaleString()}</p>
          <button onClick={backToAgents} className="secondary">Back to Agents</button>
        </div>
      ) : (
        <div className="empty-state">
          <p>No cards in this deck.</p>
          <button onClick={backToAgents} className="secondary">Back to Agents</button>
        </div>
      )}
    </div>
  );
}
