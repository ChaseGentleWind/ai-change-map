import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src')
    }
  },
  server: {
    port: 5174,
    allowedHosts: ['powwow-uncharted-uniformed.ngrok-free.dev'],
    proxy: {
      '/api': {
        target: 'http://localhost:8001',
        changeOrigin: true
      },
      '/uploads': {
        target: 'http://localhost:8001',
        changeOrigin: true
      },
      '/outputs': {
        target: 'http://localhost:8001',
        changeOrigin: true
      }
    }
  }
})
