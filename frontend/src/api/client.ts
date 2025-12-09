/**
 * API client for communicating with the backend.
 * Uses VITE_API_URL for production (direct backend URL) or /api for local dev (proxied).
 */

const API_BASE = import.meta.env.VITE_API_URL || '/api';

// Default user ID for demo purposes
export const DEFAULT_USER_ID = 'demo-user-001';

// Types matching backend models
export interface Deck {
  id: string;
  name: string;
  description: string | null;
  userId: string;
  createdAt: string;
  updatedAt: string;
}

export interface DeckCreate {
  name: string;
  description?: string | null;
}

export interface DeckUpdate {
  name?: string | null;
  description?: string | null;
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

// Helper function for API calls with user ID header
async function apiFetch<T>(
  endpoint: string,
  options: RequestInit = {},
  userId: string = DEFAULT_USER_ID
): Promise<T> {
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    'X-User-Id': userId,
    ...options.headers,
  };

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

// Health check function
export async function healthCheck(): Promise<{ status: string }> {
  const response = await fetch(`${API_BASE}/healthz`);
  return response.json();
}
