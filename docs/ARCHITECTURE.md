# EnterpriseGym Architecture

> Status: **Milestone 0 draft.** This document records intended design. Sections are
> marked *(planned)* until code and tests exist for them. See `PROJECT_STATUS.md`.

## 1. What this system is (and is not)

EnterpriseGym is a **stateful environment** that simulates an insurance company's back
office. An **agent** receives a natural-language task and changes the business state by
calling **tools**, such as reading a claim, verifying a document or issuing a payment. When the
episode ends, a **hidden verifier** inspects the resulting database state. It does not use the agent's
claims to decide success. A separate **reward engine** then turns the verifier's findings
into a score.

It **is** an RL-style environment: it has a `reset/step` interface, discrete actions, observations,
episode termination and a scalar reward. That is the interface an RL training loop
would consume.

It **is not**, at this stage, a trained RL system. No model weights are updated here.
We use the environment to **evaluate** agents. Training (e.g. RLVR) would be a
consumer of this environment, not part of it.

## 2. Component diagram

```
                          ┌──────────────────────────── EVALUATION SIDE (hidden) ─────────┐
                          │                                                                │
 ┌──────────────┐  load   │  ┌──────────────┐   hidden spec   ┌───────────────┐            │
 │ Task Registry│────────────▶ Task Loader  │────────────────▶│ Verifier      │──┐         │
 │  tasks/<id>/ │         │  └──────┬───────┘                 │ Engine        │  │ result  │
 └──────────────┘         │         │ public view + seed      └───────▲───────┘  ▼         │
                          │         ▼                                 │  ┌───────────────┐ │
                          │  ┌──────────────────┐   read-only snapshot│  │ Reward Engine │ │
                          │  │ Environment      │─────────────────────┘  └──────┬────────┘ │
                          │  │ Manager          │                               │          │
                          │  │ reset/step/close │                               ▼          │
                          │  └──┬───────────▲───┘                     ┌──────────────────┐ │
                          └─────┼───────────┼─────────────────────────│ Evaluation Runner│─┘
                                │           │                         │ + Experiment Mgr │
                    tool call   ▼           │ observation             └────────┬─────────┘
                       ┌────────────────────┴──┐                               │
                       │ Agent Tool Interface  │◀── also exposed via FastAPI   ▼
                       │ (Pydantic schemas,    │                     ┌──────────────────┐
                       │  allow-list per task) │                     │ Reports (CSV/JSON)│
                       └──────────┬────────────┘                     │ Dashboard         │
                                  ▼                                  └──────────────────┘
                       ┌───────────────────────┐        ┌──────────────────────┐
                       │ Enterprise Services   │──────▶ │ Environment State    │
                       │ (business rules,      │        │ (SQLAlchemy / PG)    │
                       │  permissions, audit)  │        └──────────────────────┘
                       └───────────────────────┘
   ┌──────────────┐  act(observation) → action
   │ Agent Adapter│◀──────────────────────────────▶ Environment Manager
   │ reference /  │          every step ───────────▶ Trajectory Logger (JSONL)
   │ scripted /   │
   │ mock / LLM   │
   └──────────────┘
```

**Trust boundary:** everything inside the dashed "evaluation side" box is invisible to
the agent. The agent sees only (a) the public instruction, (b) tool schemas for the
tools that task allows, and (c) tool outputs.

## 3. Components

| # | Component | Responsibility | Module *(planned)* |
|---|-----------|----------------|--------------------|
| 1 | Environment Manager | `reset(task, seed)`, `step(action)`, termination, limits | `env/manager.py` |
| 2 | Task Registry | Discover and index task directories | `tasks/registry.py` |
| 3 | Task Loader | Parse and validate task files into public and hidden models | `tasks/loader.py` |
| 4 | State Manager | Create isolated DB state per episode, seed it, snapshot it | `env/state.py` |
| 5 | Enterprise Services | Domain logic, hard business rules, permissions, audit writes | `services/*` |
| 6 | Agent Tool Interface | Tool registry, Pydantic I/O schemas, per-task allow-list | `tools/*` |
| 7 | Agent Adapter | `Agent` protocol: `act(observation) -> Action` | `agents/base.py` |
| 8 | Trajectory Logger | One JSONL event per step | `trajectory/*` |
| 9 | Reference Agent | Deterministic rule-based policy using only public tools | `agents/reference.py` |
| 10 | Verifier Engine | State-based checks against hidden expectations and global invariants | `verifiers/*` |
| 11 | Reward Engine | Weighted, configurable scoring with hard-failure gates | `reward/*` |
| 12 | Evaluation Runner | Orchestrates one episode end to end | `runner/*` |
| 13 | Experiment Manager | Grids of agents × tasks × configs × seeds, then reports | `experiments/*` |
| 14 | Dashboard | Read-only view over results | `dashboard/` |

## 4. The episode lifecycle

```python
env = EnvironmentManager(task, seed=42)       # task already split public/hidden
obs = env.reset()                              # fresh seeded DB; obs = instruction + tool specs
while not obs.done:
    action = agent.act(obs)                    # ToolCall(name, args) | Submit(answer)
    obs = env.step(action)                     # validated → service → DB; logged to JSONL
verification = verifier.verify(env.readonly_snapshot(), trajectory, task.hidden)
reward = reward_engine.score(verification, trajectory, reward_config)
```

Episodes end on `Submit`, on reaching the step limit, or on wall-clock timeout. The last
two are recorded as failure categories. They are not crashes.

## 5. Key design decisions

### D1. Two kinds of business rules: hard constraints and soft policies
- **Hard constraints** are enforced by the service layer, and the API rejects violations. Examples:
  paying more than the coverage limit, approving a claim on a cancelled policy, or acting
  beyond the agent role's authority limit.
- **Soft policies** are written in the public operations handbook but deliberately **not**
  enforced by the API. Examples: "verify all required documents before approving", "add an audit
  note explaining any rejection", "check for duplicate claims before paying".

*Why:* Real enterprise systems don't encode every SOP. If the API blocked every mistake,
any agent that avoided errors would pass and the benchmark would measure nothing.
Soft policies are where agent judgement is tested, and the verifier is what checks them.
*Trade-off:* the verifier must be stronger, and task authors must keep the handbook and
the verifier consistent. We test that consistency.

### D2. Verifier independence
The verifier reads the final DB state through its own read-only queries. It does **not**
call the services' business functions, such as `calculate_coverage`. Expected values,
such as "payment = 4,250.00", are hand-computed by the task author and stored in the hidden spec. The
verifier then also asserts global invariants, such as no duplicate payments, paid ≤ coverage − deductible,
and no payment without an approved claim.
*Why:* if the verifier reused the service's coverage function, a bug in that function
would pass both. *Trade-off:* expected values are duplicated, and task authoring is slower.

### D3. Money as integer cents, time from a simulated clock
Floats make `0.1 + 0.2 != 0.3` a grading bug. Each task fixes a `business_date`, so
"is the policy active today?" never depends on when the benchmark runs.

### D4. Deterministic IDs and seeds
Seeded entities have stable IDs (`CLM-1001`). Entities the agent creates get IDs from a
per-episode counter. Random choices, such as fault injection, use `random.Random(seed)`.
Same task + same seed + same actions ⇒ byte-identical final state. A test asserts this.

### D5. Database backend: PostgreSQL canonical, SQLite for fast runs
SQLAlchemy 2.0 models use portable types: integers for money, generic `JSON`, and string enums
with CHECK constraints. Postgres is the system of record (Docker, integration tests, API).
In-memory SQLite is supported for unit tests and large batch rollouts, where creating a
fresh database per episode costs microseconds.
*Trade-off:* there is a risk of dialect drift. Mitigation: the full suite runs on both backends,
and Postgres-only features are avoided in the domain layer.
*Episode isolation on Postgres:* one schema per episode (`ep_<id>`), created and seeded at
reset and dropped at close.

### D6. In-process tools first, HTTP second
`ToolRegistry` is the single source of truth. The in-process runner calls it directly, which is
fast and easy to debug. FastAPI exposes the **same** registry over HTTP for out-of-process
agents and for Harbor. There is one schema definition and two transports.

### D7. Public and hidden task data are separated on disk
```
tasks/<task_id>/
  task.yaml        # PUBLIC: id, title, difficulty, instruction, allowed_tools, timeout, tags
  seed.yaml        # initial_environment_state (loaded by the env; not shown to the agent)
  hidden/
    evaluation.yaml  # success_criteria, expected values, check list, fault plan
    solution.yaml    # reference action sequence (documentation + solvability tests)
```
The loader produces two different Pydantic models. Only `PublicTask` ever reaches the agent.

### D8. Deterministic fault injection
Hard tasks can declare faults in the hidden spec. For example: "the 1st `issue_payment` call
commits and then returns a transient 503". A naive retry then pays twice. The correct
behaviour is to check existing payments or retry with the same idempotency key. The faults
are seeded and reproducible.

### D9. Redis deferred
No component needs Redis yet. If the Experiment Manager grows into a distributed job
queue (M10/M11), it is the natural place for it. We will not add it speculatively.

## 6. Threat model (summary; full version in `SECURITY.md`)

| Agent type | Isolation provided | Sufficient? |
|------------|--------------------|-------------|
| Honest-but-fallible (LLM calling tools) | Tool allow-list, schema validation, service-layer rules, no DB handle | Yes |
| In-process Python agent | Same process as hidden files, so it *could* read `hidden/` | **No.** Use out-of-process mode for adversarial agents |
| Hostile agent (M11/M12) | Separate container, HTTP API only, hidden data never mounted, no network egress | Reasonable, with limits documented |

## 7. Repository layout *(planned)*

```
src/enterprisegym/
  config.py            settings (pydantic-settings, env vars)
  db/                  models.py, session.py, seed.py
  domain/              enums.py, money.py, clock.py
  services/            customers, policies, claims, documents, payments, audit, errors
  tools/               schemas.py, registry.py
  env/                 manager.py, state.py, faults.py
  tasks/               spec.py, loader.py, registry.py
  agents/              base.py, reference.py, scripted.py, mock.py, llm.py
  verifiers/           checks.py, engine.py, weak.py
  reward/              config.py, engine.py
  trajectory/          schema.py, logger.py, inspect.py
  runner/              episode.py, evaluate.py
  experiments/         manager.py, analysis.py
  api/                 app.py
  cli.py
tasks/                 30 → 50 task directories
configs/               reward/*.yaml, experiments/*.yaml
docs/handbook.md       public operations handbook given to agents
tests/                 unit/ integration/ adversarial/ e2e/
docker/                Dockerfile, docker-compose.yml
harbor/                Harbor packaging (M12)
dashboard/             frontend (M13)
```
