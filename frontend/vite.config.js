import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 8100,
    proxy: {
      '/api': 'http://localhost:3100',
    },
  },
})
