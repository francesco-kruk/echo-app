import { Outlet, Link } from 'react-router-dom'
import './App.css'

function App() {
  return (
    <div className="app">
      <nav className="app-nav">
        <Link to="/decks" className="app-title">
          <h1>📚 Echo App</h1>
        </Link>
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
