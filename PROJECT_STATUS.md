# Project Status

_Last updated: 2026-11-11_

## Milestones

| # | Milestone | Status | Evidence |
|---|-----------|--------|----------|
| 0 | Requirements & architecture | ✅ Done | `docs/ARCHITECTURE.md`; scaffold: `uv run pytest` → 1 passed, `ruff check` clean |
| 1 | Repository setup & data models | ⏳ Next | |
| 2 | Core insurance services | ⬜ | |
| 3 | Agent tool interface | ⬜ | |
| 4 | Task specifications & dataset (30 → 50) | ⬜ | |
| 5 | Reference agent | ⬜ | |
| 6 | Hidden verifiers | ⬜ | |
| 7 | Reward engine | ⬜ | |
| 8 | Trajectory logging | ⬜ | |
| 9 | Evaluation runner | ⬜ | |
| 10 | Experiments & analytics | ⬜ | |
| 11 | Docker & security hardening | ⬜ | |
| 12 | Harbor integration | ⬜ | |
| 13 | Dashboard | ⬜ | |
| 14 | Documentation & final validation | ⬜ | |

## Environment (verified 2026-11-11)
- Python 3.11.9 (pyenv), uv 0.11.28, Docker 27.4.0, Docker Compose v2.31.0
- Dependencies are locked exactly in `uv.lock`; `pyproject.toml` holds lower bounds.

## Known issues
- Docker daemon was not running during M0. It must be started before the Postgres work in M1.
- The shell has a pyenv `VIRTUAL_ENV` exported, so uv prints a harmless warning and uses `.venv`.

## Next actions
1. M1: `docker-compose.yml` with Postgres 16, SQLAlchemy models for 6 entities with
   constraints, session/engine factory supporting PG + SQLite, model and constraint tests.
