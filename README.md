# SampCup

Stage 0 scaffold for the SampCup tournament web application.

## Tournament plan
The tournament format, day plan, rules and reference schedules live in `Tournament Resources/`. Start with `Tournament Resources/00_README_START_HERE.md`; `02_TOURNAMENT_RULES.md` is the source of truth. Format: 4 random groups with at least 8 group games per team, then the top 4 of each group play a Round of 16, quarterfinals, semifinals and a best-of-3 Final; flow charts are in `flowchart_pool_play.png` and `flowchart_knockout.png`.

## Stack
- Backend: FastAPI, SQLAlchemy, Alembic, PostgreSQL
- Frontend: React + Vite + TypeScript
- Infra: Terraform
- Local dev: Docker Compose
- CI: GitHub Actions

## Quick start
Stage 0 is not finished: `.env.example`, `.gitignore` and the CI workflow are still to be added (see `Tournament Resources/05_DECISIONS_AND_OPEN_ITEMS.md`).

1. Copy `.env.example` to `.env`.
2. Run `docker compose up --build`.
3. API health: `http://localhost:8000/health`.
4. Frontend: `http://localhost:5173`.

## Stage 0 acceptance
- Docker Compose starts api, db, and web.
- API responds on `/health`.
- Frontend renders a Stage 0 shell.
- CI runs backend tests and frontend build.
