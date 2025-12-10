/**
 * Custom hooks for authentication state and operations.
 */

import { useMsal, useIsAuthenticated, useAccount } from '@azure/msal-react';
import { InteractionStatus, SilentRequest } from '@azure/msal-browser';
import { useCallback } from 'react';
import { loginRequest, tokenRequest, authConfig, isAuthConfigured } from './config';

/**
 * Hook to get authentication state and operations.
 */
export function useAuth() {
  const { instance, accounts, inProgress } = useMsal();
  const isAuthenticated = useIsAuthenticated();
  const account = useAccount(accounts[0] || null);

  const login = useCallback(async () => {
    try {
      await instance.loginRedirect(loginRequest);
    } catch (error) {
      console.error('[Auth] Login failed:', error);
      throw error;
    }
  }, [instance]);

  const logout = useCallback(async () => {
    try {
      await instance.logoutRedirect({
        postLogoutRedirectUri: authConfig.redirectUri,
      });
    } catch (error) {
      console.error('[Auth] Logout failed:', error);
      throw error;
    }
  }, [instance]);

  const getAccessToken = useCallback(async (): Promise<string | null> => {
    if (!account) {
      return null;
    }

    const request: SilentRequest = {
      ...tokenRequest,
      account,
    };

    try {
      const response = await instance.acquireTokenSilent(request);
      return response.accessToken;
    } catch (error) {
      console.warn('[Auth] Silent token acquisition failed, attempting redirect:', error);
      try {
        await instance.acquireTokenRedirect(request);
        return null; // Will redirect, so no token returned
      } catch (redirectError) {
        console.error('[Auth] Token acquisition failed:', redirectError);
        throw redirectError;
      }
    }
  }, [instance, account]);

  return {
    isAuthenticated,
    isLoading: inProgress !== InteractionStatus.None,
    account,
    user: account
      ? {
          id: account.localAccountId,
          name: account.name || account.username,
          email: account.username,
        }
      : null,
    login,
    logout,
    getAccessToken,
  };
}

/**
 * Hook for unauthenticated mode (when auth is disabled).
 * Returns a mock auth state for local development.
 */
export function useMockAuth() {
  return {
    isAuthenticated: true,
    isLoading: false,
    account: null,
    user: {
      id: 'dev-user-001',
      name: 'Development User',
      email: 'dev@localhost',
    },
    login: async () => {
      console.log('[Auth] Mock login - auth is disabled');
    },
    logout: async () => {
      console.log('[Auth] Mock logout - auth is disabled');
    },
    getAccessToken: async () => null,
  };
}

/**
 * Unified auth hook that works in both authenticated and mock modes.
 */
export function useAuthState() {
  // If auth is not configured/enabled, we're in mock mode
  if (!authConfig.authEnabled || !isAuthConfigured()) {
    // Using mock auth - can't use hooks conditionally, so we return mock directly
    return useMockAuth();
  }
  
  // This will throw if not within MsalProvider, which is expected
  // when auth is enabled but no provider is present
  return useAuth();
}
