/**
 * MSAL Provider component that wraps the app with authentication context.
 * This handles initialization, redirect callbacks, and provides auth state.
 */

import { ReactNode, useEffect, useState } from 'react';
import {
  PublicClientApplication,
  EventType,
  AuthenticationResult,
  AccountInfo,
  InteractionStatus,
} from '@azure/msal-browser';
import { MsalProvider } from '@azure/msal-react';
import { msalConfig, isAuthConfigured, authConfig } from './config';

// Create MSAL instance (singleton)
let msalInstance: PublicClientApplication | null = null;

function getMsalInstance(): PublicClientApplication {
  if (!msalInstance) {
    msalInstance = new PublicClientApplication(msalConfig);
  }
  return msalInstance;
}

interface AuthProviderProps {
  children: ReactNode;
}

/**
 * Authentication Provider component.
 * Wraps the app with MSAL context if auth is configured,
 * otherwise renders children directly (for local dev without auth).
 */
export function AuthProvider({ children }: AuthProviderProps) {
  const [isInitialized, setIsInitialized] = useState(false);
  const [initError, setInitError] = useState<Error | null>(null);

  // If auth is disabled or not configured, skip MSAL setup
  if (!authConfig.authEnabled || !isAuthConfigured()) {
    console.log('[Auth] Authentication disabled or not configured');
    return <>{children}</>;
  }

  const pca = getMsalInstance();

  useEffect(() => {
    const initializeMsal = async () => {
      try {
        // Initialize MSAL
        await pca.initialize();

        // Handle redirect response
        const response = await pca.handleRedirectPromise();
        if (response) {
          console.log('[Auth] Redirect login successful');
          pca.setActiveAccount(response.account);
        }

        // Set active account if one exists
        const accounts = pca.getAllAccounts();
        if (accounts.length > 0 && !pca.getActiveAccount()) {
          pca.setActiveAccount(accounts[0]);
        }

        // Register event callback for login events
        pca.addEventCallback((event) => {
          if (event.eventType === EventType.LOGIN_SUCCESS && event.payload) {
            const payload = event.payload as AuthenticationResult;
            pca.setActiveAccount(payload.account);
          }
        });

        setIsInitialized(true);
      } catch (error) {
        console.error('[Auth] MSAL initialization failed:', error);
        setInitError(error as Error);
      }
    };

    initializeMsal();
  }, [pca]);

  if (initError) {
    return (
      <div className="auth-error">
        <h2>Authentication Error</h2>
        <p>Failed to initialize authentication: {initError.message}</p>
        <p>Please check your configuration and try again.</p>
      </div>
    );
  }

  if (!isInitialized) {
    return (
      <div className="auth-loading">
        <p>Initializing authentication...</p>
      </div>
    );
  }

  return <MsalProvider instance={pca}>{children}</MsalProvider>;
}

/**
 * Get the MSAL instance for use outside of React components.
 * Used by the API client for token acquisition.
 */
export function getPublicClientApplication(): PublicClientApplication | null {
  if (!authConfig.authEnabled || !isAuthConfigured()) {
    return null;
  }
  return getMsalInstance();
}

/**
 * Get the current active account.
 */
export function getActiveAccount(): AccountInfo | null {
  const pca = getPublicClientApplication();
  return pca?.getActiveAccount() ?? null;
}

// Re-export for convenience
export { InteractionStatus };
export type { AccountInfo };
