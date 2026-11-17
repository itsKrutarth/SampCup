import { render, screen } from '@testing-library/react'
import { expect, it } from 'vitest'

import App from './App'
import { overview } from './test/data'
import { mockApi } from './test/utils'

it('boots the real app at the home page', async () => {
  mockApi({ 'GET /public/overview': overview() })
  render(<App />)
  expect(await screen.findByRole('heading', { name: 'SAMP Cup 2026' })).toBeInTheDocument()
})
