import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Vite 配置：开发时代理 /api 到 FastAPI 后端（默认 8000 端口）
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        timeout: 180000,
        proxyTimeout: 180000,
      },
    },
  },
})
