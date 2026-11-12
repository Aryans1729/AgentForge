# EnterpriseGym

A stateful simulated insurance enterprise for evaluating tool-using AI agents. Agents
receive natural-language tasks and act through structured tools; hidden verifiers grade
the resulting business state rather than the agent's claims.

> **Status:** early development. Milestone 1 (data model) is in progress. See
> [PROJECT_STATUS.md](PROJECT_STATUS.md) and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Quickstart

Requires Python 3.11+, [uv](https://docs.astral.sh/uv/) and Docker.

```bash
uv sync                          # install pinned dependencies from uv.lock
uv run pytest -m "not postgres"  # SQLite-only tests; no Docker needed

cp .env.example .env             # then change POSTGRES_PASSWORD (and the URLs to match)
docker compose up -d db          # Postgres 16 on 127.0.0.1:5433 (+ enterprisegym_test DB)
uv run pytest                    # full suite: every DB test runs on SQLite AND Postgres
uv run alembic upgrade head      # apply migrations to the dev database
```

Postgres tests are **skipped** (and reported as skipped) when `EG_TEST_DATABASE_URL` is
unset. Set `EG_REQUIRE_POSTGRES=1` to make that a failure instead (CI).

## Development

```bash
uv run ruff check . && uv run ruff format --check .
uv run alembic revision --autogenerate -m "describe change"   # after changing models
uv run alembic check                                          # models vs migrations drift
```
