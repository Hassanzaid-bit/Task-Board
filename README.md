# Project & Task Board

A lightweight internal tool for tracking tasks across projects.

**Stack**: React (Vite + TypeScript) · Python/FastAPI · PostgreSQL · Docker Compose

**Layout**: monorepo — `backend/` (API + WebSocket), `frontend/` (SPA), one compose file.

## Quick start

Requires Docker. From a clean clone:

```bash
cp .env.example .env   # defaults work out of the box for local dev
docker compose up --build
```

Then open **http://localhost:5173**, create an account, create a project, and add tasks.

To see the real-time behaviour: open the same board in a second browser window
(or a private window with a second account) and move a task — the other window
updates without a refresh.

The API is available at http://localhost:8000 (OpenAPI docs at `/docs`).

## What was built (mapped to the brief)

### Must have — all done

- **Registration & login** — email/password, argon2 hashing, JWT auth on every API route.
- **CRUD for projects and tasks** — title, description, status, assignee, due date.
- **Board view** — three status columns; tasks move by drag-and-drop or the
  arrow buttons on each card (also keyboard/screen-reader friendly).
- **Real-time propagation** — WebSocket per board; changes broadcast after DB
  commit and other clients refetch. See `ARCHITECTURE.md` §2 for the full reasoning.
- **Validation & error handling** — Pydantic validation server-side with a
  consistent error shape (`{"detail": {"code", "message"}}`); forms validate
  client-side and surface API errors inline.
- **Tests** — backend unit (status-transition rules), backend integration
  (task lifecycle over the API against a real DB), frontend (board column
  rendering + move interaction). Details below.
- **One-command run** — `docker compose up` (above).
- **CI** — GitHub Actions runs lint + tests for both halves on every push
  (`.github/workflows/ci.yml`).

### Should have — done

- **Search/filter** — one search box on the board matching title, description,
  assignee name, and status (client-side over the board's task set; the API's
  `q` param does the same server-side, plus `status`/`assignee_id` params).
- **Optimistic UI** — task moves apply instantly, roll back on server error,
  and reconcile with a refetch.
- **Rate limiting** — 10 requests/minute/IP on register and login.
- **Loading / error / empty states** — on projects list, board, and all forms.

### Could have — partially

- Dark mode, activity log, pagination: **not built** (time budget went to must-haves).
- Docker deployment exists but is dev-oriented, not a production multi-stage build
  (see `ARCHITECTURE.md` §5d).

## Assumptions made

- **Single trusted team**: every user sees all projects and users (matches the
  brief's "won't do" list). The assignee picker lists all registered users.
- **Mandatory task fields**: title, description, assignee, and due date are all
  required when creating or editing a task (enforced server-side and in the
  form). Every task should be actionable, owned, and scheduled from the start.
- **Business rule**: if a task ever ends up unassigned (the DB nulls the
  assignee if that user's account is deleted), moving it to *In Progress*
  auto-assigns the person who moved it — work in progress should have an
  owner. Explicit assignee changes always win over this default.
- Any transition between the three statuses is allowed (including reopening
  a Done task).
- Task ordering within a column is by creation time.

## Notable third-party libraries (and why)

- **TanStack Query** (frontend) — server-state caching and invalidation; the
  core of the real-time refetch pattern. Full reasoning in `ARCHITECTURE.md` §3.
- **@hello-pangea/dnd** (frontend) — board drag-and-drop; the maintained fork
  of react-beautiful-dnd, with accessible keyboard dragging built in.
- **argon2-cffi** (backend) — Argon2id password hashing, per the brief's
  bcrypt/argon2 requirement.
- **PyJWT** (backend) — JWT signing/verification; small and standard, no need
  for a full auth framework at this scope.
- **slowapi** (backend) — per-IP rate limiting on the auth endpoints; in-memory,
  which is enough for a single-process deployment.
- **SQLAlchemy Core + asyncpg** (backend) — explicit SQL without ORM
  relationship mapping (see `ARCHITECTURE.md` §5a).

## Running without Docker

Backend (needs a local PostgreSQL, or point `DATABASE_URL` elsewhere):

```bash
cd backend
python -m venv .venv && .venv/Scripts/activate   # or source .venv/bin/activate
pip install -r requirements-dev.txt
set DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/taskboard
uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev    # proxies /api and /ws to localhost:8000
```

## Tests & lint

Backend (uses a throwaway SQLite file — no services needed):

```bash
cd backend
ruff check app tests
pytest
```

Frontend:

```bash
cd frontend
npm run lint
npm test
```

**What is deliberately not tested** (time budget — see `ARCHITECTURE.md` §5c):
auth edge cases (expired/malformed tokens), WebSocket reconnect logic, and
concurrent-edit conflicts. All named risks, not oversights.

### CI pipeline

CI is defined in `.github/workflows/ci.yml` and runs automatically on **every
push and pull request** — no manual trigger needed. It runs two parallel jobs:

- **backend**: `ruff check app tests` then `pytest`
- **frontend**: `npm run lint` then `npm test`

These are the exact same commands as the local ones above, so a green local
run means a green CI run. Results appear under the repository's **Actions**
tab on GitHub. The backend tests run against SQLite, so CI needs no database
service or other setup.

## Environment variables

All documented in `.env.example`. No secrets are committed; the compose file
falls back to dev-only defaults so a clean clone runs without any setup.

## Further reading

- `ARCHITECTURE.md` — system overview, the real-time decision and its
  alternatives, state-management reasoning, scaling at 10x/100x, and the
  tradeoffs made under the time constraint.
- `AI_USAGE.md` — which AI tools were used, for what, and what was verified
  or changed by hand.
