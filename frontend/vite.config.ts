import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Backend URL: use 'backend' hostname in Docker Compose, 'localhost' for local dev
const backendTarget = process.env['VITE_API_TARGET'] ?? 'http://backend:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    host: true,
    // Proxy /api requests to backend during development
    proxy: {
      '/api': {
        target: backendTarget,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
  preview: {
    port: 4173,
    host: true,
  },
})
