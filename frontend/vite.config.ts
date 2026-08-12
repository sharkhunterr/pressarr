import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    // Accessible sur le réseau local — les tests depuis mobile/autre
    // machine passent par cette adresse au lieu de localhost.
    host: '0.0.0.0',
    proxy: {
      // Aligné sur le port par défaut du backend (`npm run dev:backend`
      // utilise 8585 via ${BACKEND_PORT:-8585}). Override côté frontend
      // avec la var d'env `VITE_API_PORT` si besoin.
      '/api': `http://localhost:${process.env.VITE_API_PORT || 8585}`,
      '/ws': { target: `ws://localhost:${process.env.VITE_API_PORT || 8585}`, ws: true }
    }
  }
})
