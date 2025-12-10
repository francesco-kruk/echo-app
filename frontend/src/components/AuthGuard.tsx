/**
 * AuthGuard component that protects routes requiring authentication.
 * 
 * When auth is enabled:
 * - Shows loading state during authentication check
 * - Redirects to login if user is not authenticated
 * - Renders children only when authenticated
 * 
 * When auth is disabled:
 * - Renders children directly (for local development)
 */

import { ReactNode } from 'react';
import { useMsal, useIsAuthenticated } from '@azure/msal-react';
import { InteractionStatus } from '@azure/msal-browser';
import { authConfig, isAuthConfigured, loginRequest } from '../auth';
import { LoginScreen } from './LoginScreen';

interface AuthGuardProps {
  children: ReactNode;
}

/**
 * Inner guard component that uses MSAL hooks.
 * Must be used within MsalProvider.
 */
function MsalAuthGuard({ children }: AuthGuardProps) {
  const { instance, inProgress } = useMsal();
  const isAuthenticated = useIsAuthenticated();

  // Show loading while checking auth status
  if (inProgress !== InteractionStatus.None) {
    return (
      <div className="auth-loading">
        <div className="auth-loading-spinner"></div>
        <p>Checking authentication...</p>
      </div>
    );
  }

  // Show login screen if not authenticated
  if (!isAuthenticated) {
    return (
      <LoginScreen
        onLogin={async () => {
          await instance.loginRedirect(loginRequest);
        }}
      />
    );
  }

  // User is authenticated, render children
  return <>{children}</>;
}

/**
 * Auth guard that handles both authenticated and non-authenticated modes.
 */
export function AuthGuard({ children }: AuthGuardProps) {
  // If auth is disabled or not configured, render children directly
  if (!authConfig.authEnabled || !isAuthConfigured()) {
    return <>{children}</>;
  }

  // Use MSAL guard when auth is enabled
  return <MsalAuthGuard>{children}</MsalAuthGuard>;
}
