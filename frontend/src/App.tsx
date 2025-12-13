import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuthState, authConfig, isAuthConfigured } from './auth'
import './App.css'

function App() {
  const { user, logout, isAuthenticated } = useAuthState();
  const showUserMenu = authConfig.authEnabled && isAuthConfigured() && isAuthenticated;
  const location = useLocation();
  const navigate = useNavigate();

  const path = location.pathname;
  const showDecksToLearn = path === '/decks';
  const showLearnToDecks = path === '/learn';

  return (
    <div className="app">
      <nav className="app-nav">
        <div className="nav-header">
          <Link to="/decks" className="app-title">
            <h1>📚 Echo App</h1>
          </Link>

          {showDecksToLearn && (
            <button className="secondary" onClick={() => navigate('/learn')}>
              Learn
            </button>
          )}
          {showLearnToDecks && (
            <button className="secondary" onClick={() => navigate('/decks')}>
              Decks
            </button>
          )}

          {showUserMenu && user && (
            <div className="user-menu">
              <span className="user-name" title={user.email}>
                {user.name}
              </span>
              <button
                className="logout-button"
                onClick={() => logout()}
                title="Sign out"
              >
                Sign out
              </button>
            </div>
          )}
        </div>
        <p className="description">
          A flashcard app for learning languages
        </p>
      </nav>
      <main className="app-main">
        <Outlet />
      </main>
    </div>
  )
}

export default App
