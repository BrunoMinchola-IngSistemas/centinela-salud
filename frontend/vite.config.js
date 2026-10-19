import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // En desarrollo, el front llama a /api/... y Vite lo reenvía al
      // backend Django en localhost:8000. En producción, VITE_API_URL
      // apunta directo a la API detrás del ALB.
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
