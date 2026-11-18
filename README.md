# SampCup

The web application for SAMP Cup, a one-day pickleball tournament: schedules, live scores,
standings, the knockout bracket, judging and announcements.

- **Build status and next steps:** `docs/TRACKER.md`
- **Tournament rules and requirements:** `Tournament Resources/`, starting with
  `00_README_START_HERE.md`. `02_TOURNAMENT_RULES.md` is the source of truth.

## Stack
- Backend: Python 3.12, FastAPI on AWS Lambda (Mangum), DynamoDB
- Frontend: React, Vite, TypeScript, served from S3 through CloudFront
- Infrastructure: Terraform (`infra/`), see `docs/DEPLOY.md`
- Local dev: Docker Compose with DynamoDB Local
- CI: GitHub Actions

## Run it locally
1. Copy `.env.example` to `.env`.
2. Run `docker compose up --build`.
3. Create an admin and, if you like, 40 made-up demo teams:
   ```sh
   docker compose exec api python -m app.cli create-admin <username>
   docker compose exec api python -m app.cli create-judges
   docker compose exec api python -m app.cli seed-demo     # demo team password: demo
   ```
4. Open <http://localhost:5173>. Staff log in at `/staff`, players join at `/join`,
   the projector screen is `/display`. The API is at <http://localhost:8000/api/docs>.

## Deploy
See `docs/DEPLOY.md`: serverless AWS (CloudFront, S3, Lambda, DynamoDB), all by Terraform.

## Run the checks
```sh
cd backend && python3.12 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/pytest   # fake AWS (moto)

cd frontend && npm ci
npm run lint && npm run typecheck && npm run test:coverage && npm run build
```

Both test suites fail below 90% coverage.
