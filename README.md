# SampCup

Stage 0 scaffold for the SampCup tournament web application.

## Stack
- Backend: FastAPI, SQLAlchemy, Alembic, PostgreSQL
- Frontend: React + Vite + TypeScript
- Infra: Terraform
- Local dev: Docker Compose
- CI: GitHub Actions

## Quick start
1. Copy `.env.example` to `.env`.
2. Run `docker compose up --build`.
3. API health: `http://localhost:8000/health`.
4. Frontend: `http://localhost:5173`.

## Stage 0 acceptance
- Docker Compose starts api, db, and web.
- API responds on `/health`.
- Frontend renders a Stage 0 shell.
- CI runs backend tests and frontend build.
