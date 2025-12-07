import { useState } from 'react'
import './App.css'

// Use /api prefix for all API calls - works with both Vite dev proxy and Nginx production proxy
const API_BASE = '/api'

function App() {
  const [message, setMessage] = useState('')
  const [response, setResponse] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleEcho = async () => {
    if (!message.trim()) return

    setLoading(true)
    setError(null)

    try {
      const res = await fetch(`${API_BASE}/echo`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ message }),
      })

      if (!res.ok) {
        throw new Error(`HTTP error! status: ${res.status}`)
      }

      const data = await res.json()
      setResponse(data.echo)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setLoading(false)
    }
  }

  const handleHealthCheck = async () => {
    setLoading(true)
    setError(null)

    try {
      const res = await fetch(`${API_BASE}/healthz`)
      const data = await res.json()
      setResponse(`Backend status: ${data.status}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to reach backend')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="app">
      <h1>Echo App</h1>
      <p className="description">
        A minimal React + FastAPI application for Azure Container Apps
      </p>

      <div className="card">
        <input
          type="text"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder="Enter a message to echo..."
          onKeyDown={(e) => e.key === 'Enter' && handleEcho()}
        />
        <div className="buttons">
          <button onClick={handleEcho} disabled={loading || !message.trim()}>
            {loading ? 'Sending...' : 'Echo'}
          </button>
          <button onClick={handleHealthCheck} disabled={loading} className="secondary">
            Health Check
          </button>
        </div>
      </div>

      {response && (
        <div className="response">
          <strong>Response:</strong> {response}
        </div>
      )}

      {error && (
        <div className="error">
          <strong>Error:</strong> {error}
        </div>
      )}
    </div>
  )
}

export default App
