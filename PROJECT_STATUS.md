# Project Status

_Last updated: 2026-11-11_

## Workflow
- One branch and one PR per milestone (`milestone-N/<topic>`), with several commits each.
- PRs are reviewed and merged by the project owner. Nothing is merged automatically.
- A milestone is marked done only when its PR is merged.

## Milestones

| # | Milestone | Status | Evidence |
|---|-----------|--------|----------|
| 0 | Requirements & architecture | ✅ Done (on `main`) | `docs/ARCHITECTURE.md`; scaffold smoke test passed |
| 1 | Repository setup & data models | 🔍 In review (`milestone-1/database-models`) | 91 passed, 0 skipped (SQLite + Postgres); `alembic check`: no drift |
| 2 | Core insurance services | ⬜ Blocked on M1 review | |
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

## Milestone 1 evidence (2026-11-11)

| Command | Result |
|---------|--------|
| `uv run pytest` | 91 passed in 3.17s (45 SQLite, 45 Postgres, 1 smoke) |
| `uv run pytest -m postgres` / `-m "not postgres"` | 45 passed / 46 passed. Proves the Postgres tests run rather than skip |
| Fresh `git clone` of the branch → `uv sync` → `EG_REQUIRE_POSTGRES=1 uv run pytest` | 91 passed in 4.13s |
| `uv run ruff check .` / `ruff format --check .` | clean |
| `uv run alembic upgrade head` (dev DB) → `alembic check` | `0001 (head)`, "No new upgrade operations detected" |
| SQLite engine *without* FK pragma (manual check) | orphan policy accepted, which confirms the pragma test guards a real failure |

## Known issues / limitations
- `compare_metadata` cannot see CHECK constraints. A custom test compares their *names*,
  not their SQL text, so changing a CHECK expression without renaming it would not be caught.
- The Postgres test suite drops and recreates tables per test (~60ms each). That is fine
  at this size, and can be revisited if the suite grows.
- Audit-log append-only behaviour is not yet enforced. That is planned for the M2 service layer.
- Your shell exports a pyenv `VIRTUAL_ENV`, so uv prints a harmless warning.

## Next actions
1. Owner reviews and merges the M1 PR.
2. M2: service layer covering the claim status state machine, permissions/authority limits,
   audit writes, transaction handling, and a payment idempotency key (a second
   migration, `0002`).
