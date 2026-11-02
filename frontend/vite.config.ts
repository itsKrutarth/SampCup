import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { '/api': process.env.API_PROXY_TARGET ?? 'http://localhost:8000' },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['src/test-setup.ts'],
    coverage: {
      provider: 'v8',
      include: ['src/**/*.{ts,tsx}'],
      exclude: ['src/main.tsx', 'src/test-setup.ts', 'src/**/*.test.{ts,tsx}'],
      thresholds: { lines: 90, functions: 90, branches: 90, statements: 90 },
    },
  },
})
