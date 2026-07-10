import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// npm run dev -- --host  →  http://서버IP:5173
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8787',
    },
  },
})
