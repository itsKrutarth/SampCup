# SampCup

Web app to run SAMP Cup, a one-day pickleball tournament.

**Start every session by reading `docs/TRACKER.md`.** It says where the work stands, what is
next, and what is needed from the owner. Update it as chunks finish.

- Requirements: `Tournament Resources/` (read `00_README_START_HERE.md` first).
  `02_TOURNAMENT_RULES.md` is the locked source of truth; change a rule there first.
- This repo is PUBLIC. Never commit secrets, real player names, emails or phone numbers.
- Work on a branch, one small chunk at a time. Test coverage must stay at 90% or more on
  backend and frontend (CI enforces it).
- Do the work in a clone outside OneDrive (`~/dev/SampCup`), never in the OneDrive folder.

## Commands
Backend (from `backend/`): `.venv/bin/ruff check .`, `.venv/bin/pytest`
Frontend (from `frontend/`): `npm run lint`, `npm run typecheck`, `npm run test:coverage`, `npm run build`
Everything: `docker compose up --build`
