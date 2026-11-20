import { fileURLToPath } from 'node:url'
import { defineConfig, loadEnv, type ProxyOptions } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const projectRoot = fileURLToPath(new URL('.', import.meta.url))

export default defineConfig(({ mode }) => {
  // Lê o .env do backend na raiz do projeto. Só variáveis com prefixo VITE_
  // chegariam ao navegador; o token abaixo fica no servidor de desenvolvimento.
  const env = { ...loadEnv(mode, projectRoot, ''), ...process.env }
  if (!env.MEDGUIDE_ADMIN_TOKEN) {
    console.warn('[medguide] MEDGUIDE_ADMIN_TOKEN ausente: crie o .env com "cp .env.example .env".')
  }
  const token = env.MEDGUIDE_ADMIN_TOKEN
  const apiProxy: ProxyOptions = {
    target: env.MEDGUIDE_API_URL || 'http://127.0.0.1:8000',
    changeOrigin: true,
    configure(proxy) {
      proxy.on('proxyReq', (request) => {
        if (token) request.setHeader('Authorization', `Bearer ${token}`)
      })
    },
  }

  return {
    plugins: [react(), tailwindcss()],
    server: { proxy: { '/api': apiProxy } },
    preview: { proxy: { '/api': apiProxy } },
  }
})
