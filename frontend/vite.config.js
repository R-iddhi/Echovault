import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    proxy: {
      '/transcribe-audio': 'http://127.0.0.1:8000',
      '/extract-memory': 'http://127.0.0.1:8000',
      '/ask-memory': 'http://127.0.0.1:8000',
    },
  },
})
