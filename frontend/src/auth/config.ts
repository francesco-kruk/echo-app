/**
 * MSAL Configuration for Azure Entra ID authentication.
 * 
 * Environment variables are set by azd during provisioning:
 * - VITE_AZURE_CLIENT_ID: The SPA app registration client ID
 * - VITE_TENANT_ID: The Azure AD tenant ID
 * - VITE_API_SCOPE: Space-separated list of API scopes to request
 * - VITE_REDIRECT_URI: Optional override for redirect URI (defaults to current origin)
 */

import { Configuration, LogLevel, BrowserCacheLocation } from '@azure/msal-browser';

// Auth configuration from environment
export const authConfig = {
  clientId: import.meta.env.VITE_AZURE_CLIENT_ID || '',
  tenantId: import.meta.env.VITE_TENANT_ID || '',
  apiScopes: (import.meta.env.VITE_API_SCOPE || '').split(' ').filter(Boolean),
  redirectUri: import.meta.env.VITE_REDIRECT_URI || window.location.origin,
  // Auth can be disabled for local development without Entra
  authEnabled: import.meta.env.VITE_AUTH_ENABLED !== 'false',
};

// Check if auth is properly configured
export function isAuthConfigured(): boolean {
  return !!(authConfig.clientId && authConfig.tenantId && authConfig.apiScopes.length > 0);
}

// MSAL configuration object
export const msalConfig: Configuration = {
  auth: {
    clientId: authConfig.clientId,
    authority: `https://login.microsoftonline.com/${authConfig.tenantId}`,
    redirectUri: authConfig.redirectUri,
    postLogoutRedirectUri: authConfig.redirectUri,
    navigateToLoginRequestUrl: true,
  },
  cache: {
    cacheLocation: BrowserCacheLocation.SessionStorage,
    storeAuthStateInCookie: false,
  },
  system: {
    loggerOptions: {
      loggerCallback: (level, message, containsPii) => {
        if (containsPii) {
          return;
        }
        switch (level) {
          case LogLevel.Error:
            console.error('[MSAL]', message);
            break;
          case LogLevel.Warning:
            console.warn('[MSAL]', message);
            break;
          case LogLevel.Info:
            if (import.meta.env.DEV) {
              console.info('[MSAL]', message);
            }
            break;
          case LogLevel.Verbose:
            if (import.meta.env.DEV) {
              console.debug('[MSAL]', message);
            }
            break;
        }
      },
      logLevel: import.meta.env.DEV ? LogLevel.Info : LogLevel.Warning,
    },
  },
};

// Login request configuration
export const loginRequest = {
  scopes: authConfig.apiScopes,
};

// Token request for API calls
export const tokenRequest = {
  scopes: authConfig.apiScopes,
};
