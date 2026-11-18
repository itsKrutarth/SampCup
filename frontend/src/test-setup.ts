import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

import { judgeQueue } from './lib/queue'

afterEach(() => {
  cleanup()
  judgeQueue.token = null
  judgeQueue.clear()
  localStorage.clear()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})
