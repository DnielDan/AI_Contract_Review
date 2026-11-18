import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// npm run dev serves the workbench on its own port and passes API calls to the
// Python server (python main.py), which must be running on port 8080
export default defineConfig({
  base: '/',
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8080',
    },
  },
})
