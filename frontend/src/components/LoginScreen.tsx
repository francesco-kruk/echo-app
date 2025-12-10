/**
 * Login screen shown to unauthenticated users.
 */

import './LoginScreen.css';

interface LoginScreenProps {
  onLogin: () => Promise<void>;
  error?: string | null;
}

export function LoginScreen({ onLogin, error }: LoginScreenProps) {
  const handleLogin = async () => {
    try {
      await onLogin();
    } catch (err) {
      console.error('[Login] Login failed:', err);
    }
  };

  return (
    <div className="login-screen">
      <div className="login-card">
        <div className="login-header">
          <h1>📚 Echo App</h1>
          <p>A flashcard app for learning languages</p>
        </div>
        
        <div className="login-content">
          <p>Sign in with your organization account to continue.</p>
          
          {error && (
            <div className="login-error">
              <p>{error}</p>
            </div>
          )}
          
          <button
            className="login-button"
            onClick={handleLogin}
          >
            <svg
              className="microsoft-icon"
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 23 23"
              width="20"
              height="20"
            >
              <path fill="#f35325" d="M1 1h10v10H1z" />
              <path fill="#81bc06" d="M12 1h10v10H12z" />
              <path fill="#05a6f0" d="M1 12h10v10H1z" />
              <path fill="#ffba08" d="M12 12h10v10H12z" />
            </svg>
            Sign in with Microsoft
          </button>
        </div>
        
        <div className="login-footer">
          <p>
            By signing in, you agree to use this application in accordance with
            your organization's policies.
          </p>
        </div>
      </div>
    </div>
  );
}
