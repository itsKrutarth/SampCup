import React from 'react'
import ReactDOM from 'react-dom/client'
import './styles.css'

function App() {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="logo">SampCup</div>
        <nav>
          <a href="#">Dashboard</a>
          <a href="#">Teams</a>
          <a href="#">Schedule</a>
          <a href="#">Standings</a>
        </nav>
      </aside>
      <main className="main">
        <header className="header">
          <div>
            <p className="eyebrow">Stage 0</p>
            <h1>Tournament control center</h1>
          </div>
          <span className="badge">Scaffold ready</span>
        </header>
        <section className="grid">
          <article className="card">
            <h2>Backend</h2>
            <p>FastAPI health endpoint is wired and ready for Stage 1 database work.</p>
          </article>
          <article className="card">
            <h2>Frontend</h2>
            <p>React + Vite shell follows a dashboard-first layout for admin and judge views.</p>
          </article>
          <article className="card">
            <h2>Next step</h2>
            <p>Google Sheets import, team-number draw, and tournament tables.</p>
          </article>
        </section>
      </main>
    </div>
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
