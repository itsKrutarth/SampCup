import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, beforeEach, vi } from 'vitest'

import { judgeQueue } from './lib/queue'
import { FakeEventSource } from './test/utils'

beforeEach(() => {
  FakeEventSource.instances = []
  vi.stubGlobal('EventSource', FakeEventSource)
})

afterEach(() => {
  cleanup()
  judgeQueue.token = null
  judgeQueue.clear()
  localStorage.clear()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})
