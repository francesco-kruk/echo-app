import { useCallback, useEffect, useRef, useState } from 'react';
import {
  getDecks,
  postLearnStart,
  postLearnChat,
  SUPPORTED_LANGUAGES,
  type Deck,
  type LearnChatResponse,
  type LearnMode,
} from '../api/client';
import './LearnPage.css';

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

/** Agent info derived from a deck + SUPPORTED_LANGUAGES */
interface DeckAgent {
  deckId: string;
  deckName: string;
  language: string;
  agentName: string;
  dueCardCount: number;
  startsInMode: 'card' | 'free';
}

/** Map a deck to an agent summary using SUPPORTED_LANGUAGES */
function deckToAgent(deck: Deck): DeckAgent {
  const langInfo = SUPPORTED_LANGUAGES.find(l => l.code === deck.language);
  const dueCount = deck.dueCardCount ?? 0;
  return {
    deckId: deck.id,
    deckName: deck.name,
    language: langInfo?.name ?? deck.language,
    agentName: langInfo?.agentName ?? 'Language Tutor',
    dueCardCount: dueCount,
    startsInMode: dueCount > 0 ? 'card' : 'free',
  };
}

export function LearnPage() {
  // Agent selection state (derived from decks)
  const [agents, setAgents] = useState<DeckAgent[]>([]);
  const [loadingAgents, setLoadingAgents] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Selected agent/deck state
  const [selectedAgent, setSelectedAgent] = useState<DeckAgent | null>(null);

  // Learning session state
  const [mode, setMode] = useState<LearnMode>('card');
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [_cardId, setCardId] = useState<string | null>(null);
  const [cardFront, setCardFront] = useState<string | null>(null);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);

  // UI state
  const [loadingSession, setLoadingSession] = useState(false);
  const [sendingMessage, setSendingMessage] = useState(false);
  const [userInput, setUserInput] = useState('');

  const chatEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Auto-scroll to bottom of chat
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages]);

  // Focus input when session starts or mode changes
  useEffect(() => {
    if (selectedAgent && !loadingSession) {
      inputRef.current?.focus();
    }
  }, [selectedAgent, loadingSession, mode]);

  // Fetch available agents (derived from decks)
  const fetchAgents = useCallback(async () => {
    setLoadingAgents(true);
    setError(null);
    try {
      const resp = await getDecks();
      // Map decks to agents using SUPPORTED_LANGUAGES
      setAgents(resp.decks.map(deckToAgent));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load agents');
    } finally {
      setLoadingAgents(false);
    }
  }, []);

  // Initial fetch and periodic refresh while agent selection is visible
  useEffect(() => {
    fetchAgents();

    // Refetch every 30 seconds when on the agent selection screen
    const interval = setInterval(() => {
      if (!selectedAgent) {
        fetchAgents();
      }
    }, 30000);

    return () => clearInterval(interval);
  }, [fetchAgents, selectedAgent]);

  // Refetch on window focus
  useEffect(() => {
    const handleFocus = () => {
      if (!selectedAgent) {
        fetchAgents();
      }
    };
    window.addEventListener('focus', handleFocus);
    return () => window.removeEventListener('focus', handleFocus);
  }, [fetchAgents, selectedAgent]);

  // Start learning session with selected agent
  const startSession = useCallback(async (agent: DeckAgent) => {
    setSelectedAgent(agent);
    setLoadingSession(true);
    setError(null);
    setChatMessages([]);

    try {
      const resp = await postLearnStart({ deckId: agent.deckId });
      setMode(resp.mode);
      setCardId(resp.card?.id ?? null);
      setCardFront(resp.card?.front ?? null);
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
    if (!selectedAgent || !userInput.trim() || sendingMessage) return;

    const message = userInput.trim();
    setUserInput('');
    setSendingMessage(true);
    setChatMessages(prev => [...prev, { role: 'user', content: message }]);

    try {
      const resp: LearnChatResponse = await postLearnChat({
        deckId: selectedAgent.deckId,
        userMessage: message,
      });

      setChatMessages(prev => [...prev, { role: 'assistant', content: resp.assistantMessage }]);
      // Update mode and card from response (server-driven state machine)
      setMode(resp.mode);
      setCardId(resp.card?.id ?? null);
      setCardFront(resp.card?.front ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send message');
    } finally {
      setSendingMessage(false);
    }
  }, [selectedAgent, userInput, sendingMessage]);

  // Go back to agent selection
  const backToAgents = useCallback(() => {
    setSelectedAgent(null);
    setMode('card');
    setCardId(null);
    setCardFront(null);
    setChatMessages([]);
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
              <p>No decks available.</p>
              <p className="muted">Create a deck to start learning.</p>
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
                    <p className="agent-language">{agent.language}</p>
                    <p className="agent-due">{agent.dueCardCount} card{agent.dueCardCount !== 1 ? 's' : ''} due</p>
                    <p className={`agent-starts-in ${agent.startsInMode}`}>
                      Starts in: {agent.startsInMode === 'card' ? 'Card' : 'Free'}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      ) : loadingSession ? (
        <div className="loading">Loading session...</div>
      ) : (
        // Chat view - works in both card and free modes
        <div className="chat-container">
          <div className="chat-header">
            <div className="chat-agent-info">
              <div className="agent-avatar small">
                {selectedAgent.agentName.charAt(0)}
              </div>
              <div>
                <strong>{selectedAgent.agentName}</strong>
                <span className="chat-language">{selectedAgent.language}</span>
              </div>
            </div>
            <div className={`chat-mode-indicator ${mode}`}>
              {mode === 'card' && cardFront ? (
                <>
                  <span className="prompt-label">Card:</span> {cardFront}
                </>
              ) : (
                <span className="prompt-label">Free Mode</span>
              )}
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

          <div className="chat-input-container">
            <input
              ref={inputRef}
              type="text"
              value={userInput}
              onChange={(e) => setUserInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={mode === 'card' ? 'Type your answer...' : 'Chat with your tutor...'}
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
        </div>
      )}
    </div>
  );
}
