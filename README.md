# SampCup

The web application for SAMP Cup, a one-day pickleball tournament: schedules, live scores,
standings, the knockout bracket, judging and announcements.

- **Build status and next steps:** `docs/TRACKER.md`
- **Tournament rules and requirements:** `Tournament Resources/`, starting with
  `00_README_START_HERE.md`. `02_TOURNAMENT_RULES.md` is the source of truth.

## Stack
- Backend: Python 3.12, FastAPI, SQLAlchemy, Alembic, PostgreSQL
- Frontend: React, Vite, TypeScript
- Local dev: Docker Compose
- CI: GitHub Actions

## Run it locally
1. Copy `.env.example` to `.env`.
2. Run `docker compose up --build`.
3. Open the app at <http://localhost:5173>. The API is at <http://localhost:8000/api/docs>.

## Run the checks
```sh
cd backend && python3.12 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/pytest

cd frontend && npm ci
npm run lint && npm run typecheck && npm run test:coverage && npm run build
```

Both test suites fail below 90% coverage.
