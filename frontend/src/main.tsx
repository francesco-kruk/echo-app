import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { HashRouter, Routes, Route, Navigate } from 'react-router-dom'
import App from './App.tsx'
import { AuthProvider } from './auth'
import { AuthGuard } from './components/AuthGuard.tsx'
import { DecksPage } from './pages/DecksPage.tsx'
import { CardsPage } from './pages/CardsPage.tsx'
import { LearnPage } from './pages/LearnPage.tsx'
import './index.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AuthProvider>
      <AuthGuard>
        <HashRouter>
          <Routes>
            <Route path="/" element={<App />}>
              <Route index element={<Navigate to="/learn" replace />} />
              <Route path="decks" element={<DecksPage />} />
              <Route path="decks/:deckId/cards" element={<CardsPage />} />
              <Route path="learn" element={<LearnPage />} />
            </Route>
          </Routes>
        </HashRouter>
      </AuthGuard>
    </AuthProvider>
  </StrictMode>,
)
