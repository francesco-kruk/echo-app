/**
 * API client for communicating with the backend.
 * 
 * In production: Uses /api which nginx proxies to the internal backend container.
 * In local dev: Uses /api which vite proxies to localhost:8000.
 * 
 * When auth is enabled, automatically acquires and attaches Bearer tokens.
 * When auth is disabled, falls back to X-User-Id header for local development.
 */

import { getPublicClientApplication, getActiveAccount, tokenRequest, authConfig, isAuthConfigured } from '../auth';

// Always use /api - nginx (production) or vite (dev) handles proxying to backend
const API_BASE = '/api';

// Default user ID for demo/dev purposes when auth is disabled
export const DEFAULT_USER_ID = 'demo-user-001';

/**
 * Get an access token for API calls.
 * Returns null if auth is disabled or token acquisition fails.
 */
async function getAccessToken(): Promise<string | null> {
  // Skip token acquisition if auth is disabled
  if (!authConfig.authEnabled || !isAuthConfigured()) {
    return null;
  }

  const pca = getPublicClientApplication();
  const account = getActiveAccount();

  if (!pca || !account) {
    console.warn('[API] No MSAL instance or account available');
    return null;
  }

  try {
    const response = await pca.acquireTokenSilent({
      ...tokenRequest,
      account,
    });
    return response.accessToken;
  } catch (error) {
    console.error('[API] Silent token acquisition failed:', error);
    // Trigger interactive login by redirecting
    try {
      await pca.acquireTokenRedirect({
        ...tokenRequest,
        account,
      });
    } catch (redirectError) {
      console.error('[API] Token redirect failed:', redirectError);
    }
    return null;
  }
}

// Types matching backend models

// Supported deck languages
export type LanguageCode = 'es-ES' | 'de-DE' | 'fr-FR' | 'it-IT';

export const SUPPORTED_LANGUAGES: { code: LanguageCode; name: string; agentName: string }[] = [
  { code: 'es-ES', name: 'Spanish (Spain)', agentName: 'Miguel de Cervantes' },
  { code: 'de-DE', name: 'German (Germany)', agentName: 'Johann Wolfgang von Goethe' },
  { code: 'fr-FR', name: 'French (France)', agentName: 'Victor Hugo' },
  { code: 'it-IT', name: 'Italian (Italy)', agentName: 'Leonardo da Vinci' },
];

export interface Deck {
  id: string;
  name: string;
  description: string | null;
  language: LanguageCode;
  userId: string;
  createdAt: string;
  updatedAt: string;
}

export interface DeckCreate {
  name: string;
  description?: string | null;
  language: LanguageCode;
}

export interface DeckUpdate {
  name?: string | null;
  description?: string | null;
  // Note: language is intentionally NOT included here as it is immutable
}

export interface DeckListResponse {
  decks: Deck[];
  count: number;
}

export interface Card {
  id: string;
  front: string;
  back: string;
  deckId: string;
  userId: string;
  createdAt: string;
  updatedAt: string;

  dueAt: string;
  easeFactor: number;
  repetitions: number;
  intervalDays: number;
  lastReviewedAt: string | null;
}

export interface CardCreate {
  front: string;
  back: string;
}

export interface CardUpdate {
  front?: string | null;
  back?: string | null;
}

export interface CardListResponse {
  cards: Card[];
  count: number;
}

export interface SeedResponse {
  message: string;
  decks_created: number;
  cards_created: number;
}

export interface LearnNextResponse {
  card: Card | null;
  nextDueAt: string | null;
}

export type LearnGrade = 'again' | 'hard' | 'good' | 'easy';

export interface LearnReviewRequest {
  deckId: string;
  cardId: string;
  grade: LearnGrade;
}

/**
 * Helper function for API calls with authentication.
 * 
 * When auth is enabled: Uses Bearer token from MSAL
 * When auth is disabled: Falls back to X-User-Id header for local dev
 */
async function apiFetch<T>(
  endpoint: string,
  options: RequestInit = {},
  userId: string = DEFAULT_USER_ID
): Promise<T> {
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  // Get access token if auth is enabled
  const token = await getAccessToken();
  
  if (token) {
    // Use Bearer token authentication
    (headers as Record<string, string>)['Authorization'] = `Bearer ${token}`;
  } else {
    // Fallback to X-User-Id for local dev when auth is disabled
    (headers as Record<string, string>)['X-User-Id'] = userId;
  }

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP error ${response.status}`);
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

// Deck API functions
export async function getDecks(userId?: string): Promise<DeckListResponse> {
  return apiFetch<DeckListResponse>('/decks', {}, userId);
}

export async function getDeck(deckId: string, userId?: string): Promise<Deck> {
  return apiFetch<Deck>(`/decks/${deckId}`, {}, userId);
}

export async function createDeck(deck: DeckCreate, userId?: string): Promise<Deck> {
  return apiFetch<Deck>(
    '/decks',
    {
      method: 'POST',
      body: JSON.stringify(deck),
    },
    userId
  );
}

export async function updateDeck(
  deckId: string,
  deck: DeckUpdate,
  userId?: string
): Promise<Deck> {
  return apiFetch<Deck>(
    `/decks/${deckId}`,
    {
      method: 'PUT',
      body: JSON.stringify(deck),
    },
    userId
  );
}

export async function deleteDeck(deckId: string, userId?: string): Promise<void> {
  return apiFetch<void>(
    `/decks/${deckId}`,
    {
      method: 'DELETE',
    },
    userId
  );
}

// Card API functions
export async function getCardsForDeck(
  deckId: string,
  userId?: string
): Promise<CardListResponse> {
  return apiFetch<CardListResponse>(`/decks/${deckId}/cards`, {}, userId);
}

export async function getCard(
  deckId: string,
  cardId: string,
  userId?: string
): Promise<Card> {
  return apiFetch<Card>(`/decks/${deckId}/cards/${cardId}`, {}, userId);
}

export async function createCard(
  deckId: string,
  card: CardCreate,
  userId?: string
): Promise<Card> {
  return apiFetch<Card>(
    `/decks/${deckId}/cards`,
    {
      method: 'POST',
      body: JSON.stringify(card),
    },
    userId
  );
}

export async function updateCard(
  deckId: string,
  cardId: string,
  card: CardUpdate,
  userId?: string
): Promise<Card> {
  return apiFetch<Card>(
    `/decks/${deckId}/cards/${cardId}`,
    {
      method: 'PUT',
      body: JSON.stringify(card),
    },
    userId
  );
}

export async function deleteCard(
  deckId: string,
  cardId: string,
  userId?: string
): Promise<void> {
  return apiFetch<void>(
    `/decks/${deckId}/cards/${cardId}`,
    {
      method: 'DELETE',
    },
    userId
  );
}

// Seed API function
export async function seedSampleData(userId?: string): Promise<SeedResponse> {
  return apiFetch<SeedResponse>(
    '/seed',
    {
      method: 'POST',
    },
    userId
  );
}

// Learn (SRS) API functions
export async function getLearnNext(deckId: string, userId?: string): Promise<LearnNextResponse> {
  const params = new URLSearchParams({ deckId });
  return apiFetch<LearnNextResponse>(`/learn/next?${params.toString()}`, {}, userId);
}

export async function postLearnReview(
  request: LearnReviewRequest,
  userId?: string
): Promise<Card> {
  return apiFetch<Card>(
    '/learn/review',
    {
      method: 'POST',
      body: JSON.stringify(request),
    },
    userId
  );
}

// Agent-based learning API types
export interface LearnAgentSummary {
  deckId: string;
  deckName: string;
  language: LanguageCode;
  agentName: string;
  dueCardCount: number;
}

export interface LearnAgentsResponse {
  agents: LearnAgentSummary[];
  count: number;
}

export interface LearnStartRequest {
  deckId: string;
}

export interface LearnStartResponse {
  cardId: string;
  cardFront: string;
  assistantMessage: string;
  agentName: string;
  language: LanguageCode;
}

export interface LearnChatRequest {
  deckId: string;
  userMessage: string;
  cardId?: string;
}

export interface LearnChatResponse {
  assistantMessage: string;
  canGrade: boolean;
  revealed: boolean;
  isCorrect: boolean;
  cardId: string;
  cardFront: string;
}

// Agent-based learning API functions
export async function getLearnAgents(userId?: string): Promise<LearnAgentsResponse> {
  return apiFetch<LearnAgentsResponse>('/learn/agents', {}, userId);
}

export async function postLearnStart(
  request: LearnStartRequest,
  userId?: string
): Promise<LearnStartResponse> {
  return apiFetch<LearnStartResponse>(
    '/learn/start',
    {
      method: 'POST',
      body: JSON.stringify(request),
    },
    userId
  );
}

export async function postLearnChat(
  request: LearnChatRequest,
  userId?: string
): Promise<LearnChatResponse> {
  return apiFetch<LearnChatResponse>(
    '/learn/chat',
    {
      method: 'POST',
      body: JSON.stringify(request),
    },
    userId
  );
}

// Health check function
export async function healthCheck(): Promise<{ status: string }> {
  const response = await fetch(`${API_BASE}/healthz`);
  return response.json();
}
