import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import '@fontsource-variable/outfit'
import '@fontsource/anton/latin.css'
import '@fontsource/bebas-neue/latin.css'

import App from './App'
import './styles.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
