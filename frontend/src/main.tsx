import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { HashRouter, Routes, Route, Navigate } from 'react-router-dom'
import App from './App.tsx'
import { DecksPage } from './pages/DecksPage.tsx'
import { CardsPage } from './pages/CardsPage.tsx'
import './index.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <HashRouter>
      <Routes>
        <Route path="/" element={<App />}>
          <Route index element={<Navigate to="/decks" replace />} />
          <Route path="decks" element={<DecksPage />} />
          <Route path="decks/:deckId/cards" element={<CardsPage />} />
        </Route>
      </Routes>
    </HashRouter>
  </StrictMode>,
)
