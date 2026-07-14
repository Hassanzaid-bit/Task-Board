# Architecture & Tradeoffs

## 1. System overview

Three components, one Docker Compose stack:

```
┌─────────────┐        REST (JWT)         ┌──────────────┐
│   React     │ ────────────────────────► │   FastAPI    │
│   (Vite)    │ ◄──────────────────────── │              │
│             │                            │              │
│             │        WebSocket           │              │
│             │ ◄─────────────────────────►│              │
└─────────────┘                            └──────┬───────┘
                                                    │
                                                    │ asyncpg/SQLAlchemy
                                                    ▼
                                            ┌──────────────┐
                                            │  PostgreSQL  │
                                            └──────────────┘
```

- **Frontend**: React + TanStack Query for server-state caching, a thin WebSocket hook for live updates.
- **Backend**: FastAPI, one process, exposing both the REST API (`/api/v1/...`) and a WebSocket endpoint (`/ws/boards/{project_id}`).
- **DB**: PostgreSQL, plain SQL schema (SQLAlchemy Core, not the ORM's relationship-mapping layer) so the data model stays explicit and inspectable.

### Data model

Three tables, defined explicitly in `backend/app/schema.py`:

- **users** — `id`, `email` (unique), `display_name`, `password_hash` (argon2), `created_at`.
- **projects** — `id`, `name`, `description`, `created_by` → users (`SET NULL` on user deletion: projects outlive their creator), `created_at`.
- **tasks** — `id`, `project_id` → projects (`CASCADE`: tasks die with their project), `title`, `description`, `status`, `assignee_id` → users (`SET NULL`: tasks outlive their assignee), `due_date`, `created_at`, `updated_at`.

Decisions worth noting:

- **Status is constrained at the DB level** (`CHECK status IN ('todo','in_progress','done')`), not just validated in the API — bad data can't sneak in through a future code path.
- **`tasks.project_id` is indexed** because "fetch a board's tasks" is the hot query.
- **Title, description, assignee, and due date are mandatory at the API layer** (a task should be actionable, owned, and scheduled). `assignee_id` stays nullable in the DB only to support `SET NULL` when a user account is deleted; the API refuses to create or edit a task into an unassigned state.
- No ordering column: tasks sort by `created_at` within a column. Manual reordering was cut as out of scope.

## 2. The real-time decision (Section 4)

**Chosen approach: WebSockets, single in-memory connection manager, keyed by board (project) ID.**

### Options considered

Four real options exist for "how does a connected client find out about a change made by someone else":

| Approach | Latency | Server cost | Client complexity | Bidirectional? | Infra needed |
|---|---|---|---|---|---|
| **Short polling** | Bounded by interval (2-5s typical) | High — N clients × 1 request every few seconds, mostly returning "nothing changed" | Trivial | No | None |
| **Long polling** | Near-instant | Medium — holds a connection open, but still one request per event per client | Moderate — needs request re-issue loop | No | None |
| **SSE** | Near-instant | Low — one open HTTP connection per client, server pushes when there's data | Low — native `EventSource` API, auto-reconnect built in | No (client→server still needs regular REST) | None (works over plain HTTP/1.1, proxy-friendly) |
| **WebSockets** (chosen) | Near-instant | Low — one persistent connection per client | Moderate — reconnect/heartbeat logic is ours to own | Yes | None extra now; sticky sessions or a broker if load-balanced later |

**Why not short polling.** This is the "default no thought" choice, which is exactly why the brief calls this out as *the* decision to reason about rather than assume. At tens of users polling every 3s, most requests return "nothing changed," so we'd pay a DB round-trip per client per interval for information that's usually negative. It also caps latency at the poll interval — a "live board" that updates every 3-5s doesn't feel live.

**Why not long polling.** Better latency than short polling, but it's essentially reimplementing a weaker version of what SSE/WebSockets give natively (holding a connection open, handling timeouts, re-issuing requests) without gaining anything SSE doesn't already provide more cleanly.

**Why not SSE, even though it's the closest competitor.** SSE is genuinely a defensible alternative here, worth being honest about rather than dismissing. It's simpler than WebSockets — no ping/pong heartbeat protocol to hand-roll, auto-reconnect is built into `EventSource` — and it's one-directional, which is *all this feature needs*: the client already has REST for writes. If we wanted the most conservative, easiest-to-defend choice for a 2.5-day exercise, SSE is arguably the "does exactly what's asked, nothing more" pick. The reason we still chose WebSockets: this app's plausible future direction (presence, typing/editing indicators, live cursors on the board) is naturally bidirectional, and building the WebSocket abstraction now avoids adding a second protocol layer later for a marginal implementation cost over SSE today.

**Why WebSockets, and what we're accepting by choosing it.** The cost of this choice is reconnect/heartbeat logic we have to write ourselves, plus — later, not now — needing sticky sessions or a pub/sub layer once we run more than one server process. At tens of users on a single process, neither of those costs bites yet.

### The reasoning chain, stated explicitly

The mechanism matters less than the chain of reasoning that leads to it:

1. **What's actually needed**: server-initiated, near-real-time, one-board-scoped updates.
2. **What's explicitly not needed yet**: cross-process fan-out (we run one instance), message durability (this is a short-lived internal tool — a missed event just means the client refetches current state on reconnect, which is acceptable), presence or other bidirectional features (out of scope now, but plausible later).
3. **Given that**, both SSE and WebSockets clear the bar. WebSockets was chosen for the low marginal cost of preserving a path to future bidirectional features, in exchange for owning reconnect logic ourselves.
4. **Explicit non-goal**: scaling the connection layer beyond one process. This is deferred, with a named, ready-to-slot-in solution (Redis pub/sub — see Section 4) rather than left unaddressed.

### Why this fits *this* scale (tens of users, single process)

A `ConnectionManager` dict (`{project_id: [WebSocket, ...]}`) held in FastAPI's process memory is sufficient because:
- We run **one backend process**. There's no cross-process fan-out problem to solve.
- Board membership is small (a handful of users per project), so broadcasting to a Python list on every mutation is cheap.
- It avoids adding Redis (or another broker) as a dependency the case study doesn't need yet — every extra moving part is time not spent on Must-haves.

### Trigger point
Broadcasts fire from inside the mutating endpoint, **after the DB transaction commits successfully** — not before, and not via a separate polling job. This keeps "what clients see" always consistent with "what's actually persisted." If the WS send fails for a disconnected client, that failure is swallowed and the stale connection is pruned; it never blocks or rolls back the HTTP response.

### Frontend consumption pattern
The WebSocket message is treated as an **invalidation signal**, not a data payload to merge by hand: `{ type: "task.updated", project_id }` → `queryClient.invalidateQueries(['tasks', project_id])`. This avoids an entire class of bugs (out-of-order messages, partial payloads, merge conflicts with in-flight optimistic updates) in exchange for one extra refetch per event — a good trade at this volume. The user who *made* the change gets an optimistic local update immediately; everyone else gets the refetch-triggered update, typically within one round trip.

### What we explicitly did not build (2.5-day constraint)
- No message durability / replay — if a client is disconnected when a change happens, it simply gets current state on reconnect via the normal REST fetch, not a backlog of missed events.
- No presence indicators ("who's viewing this board") — the connection manager only tracks sockets for broadcast, not for display.
- No horizontal scaling of the WS layer (see Section 4 below) — deliberately deferred.

## 3. Frontend state management

**Chosen approach: split server state and client state, and treat them as genuinely different problems rather than one "state management library" decision.**

- **Server state** (projects, tasks, board contents — anything that lives in Postgres): **TanStack Query**.
- **Client/UI state** (which modal is open, current filter selection, drag-in-progress state, form inputs before submit): React's built-in `useState`/`useReducer`, no external library.

### Options considered

| Approach | What it's actually for | Fit for this app |
|---|---|---|
| **Context API only** | Passing state down the tree without prop drilling | Works for small UI state, but people often stretch it to hold server data too — then every board update re-renders every consumer of that context, and you've hand-rolled a weaker cache with none of TanStack Query's dedup/refetch/staleness handling |
| **Redux / Redux Toolkit** | Centralized, normalized client state with strict update rules, time-travel debugging | Real power for large apps with complex client-side state interactions; for this app almost all "state" *is* server state, so Redux would mean writing thunks/slices to do a worse version of what a data-fetching library already does out of the box |
| **Zustand** | Lightweight global store, less boilerplate than Redux | A reasonable choice for the small amount of *client* state this app has (e.g. active board filters, selected task for a detail panel) — genuinely close to what we picked, see below |
| **TanStack Query** (chosen, for server state) | Caching, deduping, refetching, and invalidating server-derived data | Directly matches what this app needs: task/project data that's fetched, cached, and must be invalidated on a WebSocket event — invalidation is a first-class concept in the library, not something to build by hand |

**Why not put everything in Redux or Context.** The board's data — tasks, statuses, assignees — isn't really "app state" in the Redux sense; it's a cached view of what's in Postgres, and the real problem is keeping that cache correct as three things happen concurrently: the local user's optimistic edit, the server's authoritative response, and another user's change arriving over the WebSocket. That's precisely the problem TanStack Query is built to solve (query keys, cache invalidation, refetch-on-invalidate, background refetching), and reimplementing it in Redux would mean writing our own cache invalidation logic — the exact thing the library gives for free.

**Why not Zustand instead of plain `useState`/Context for the remaining UI state.** Zustand is a legitimate, close second choice here — it would have been the pick if the app had more cross-cutting client state (e.g., a multi-step wizard, complex filter combinations shared across several unrelated components). For this app's actual UI state — a handful of local component states and one small "which filter is active" piece of state — plain React state plus one thin Context avoids adding a dependency with no real payoff at this scope. **What I'd revisit with more time / at larger scope**: if filter/sort state, multi-select, or bulk actions grow to be shared across many components, Zustand is the natural next step before reaching for Redux.

### How the two halves interact with the real-time layer
This split is what makes the WebSocket-as-invalidation-signal pattern (Section 2) clean: a WS message never touches client/UI state at all — it only calls `queryClient.invalidateQueries(['tasks', project_id])`, and TanStack Query handles the refetch, request deduplication (if a fetch is already in flight), and re-render of only the components actually subscribed to that query. If the board's data lived in Redux or Context instead, the WebSocket handler would need to know the shape of that store and dispatch/merge updates by hand — more code, and a second place (besides the REST response) where the "what does a task record actually look like" logic could drift out of sync.

## 4. Scaling: what we have now vs. what changes at 10x / 100x

| Concern | Now (tens of users) | At 10x (hundreds) | At 100x (thousands+) |
|---|---|---|---|
| **Real-time fan-out** | In-memory `ConnectionManager`, single process | Same, but move broadcast trigger to publish onto **Redis Pub/Sub**; every backend worker subscribes and relays to its local sockets — needed as soon as we run >1 Uvicorn worker or >1 instance behind a load balancer | Dedicated pub/sub broker (Redis Streams, NATS, or Kafka) if we need replay/ordering guarantees; possibly a separate "realtime gateway" service so WS connection count doesn't couple to API instance count |
| **DB access pattern** | Direct SQLAlchemy Core queries, no caching | Add read replicas for board-fetch queries; connection pooling tuned (pgbouncer) | Consider read-through cache (Redis) for hot boards; partition/shard if task volume per tenant grows large |
| **Auth** | JWT, no refresh-token rotation | Add refresh-token rotation + revocation list | Move to a dedicated auth service / short-lived tokens + rotating refresh, rate-limited per user |
| **Task assignment / board size** | Unbounded task list per project, fetched whole | Add pagination/infinite scroll (listed as "Could have," deferred here) | Required — unbounded fetches become a real cost/latency problem |
| **Multi-tenancy** | None — any logged-in user can edit any project (per brief's "won't do" list) | Still likely fine for an internal tool | Would need real permission/role model if used outside a single trusted org |
| **Observability** | Basic logging | Structured logging + request tracing | Full APM (latency percentiles per endpoint, WS connection counts, broadcast fan-out latency) |

The one-sentence version for the write-up: **the current design is intentionally "correct but not distributed" — every scaling step above is a known, bounded piece of work, not an architectural rewrite**, because the trigger-after-commit pattern and invalidate-then-refetch client pattern both survive the move to a pub/sub-backed multi-process backend unchanged.

## 5. Other tradeoffs made under the 2.5-day constraint

### a) Raw SQL / SQLAlchemy Core over full ORM relationship mapping
**Decision**: Model tables explicitly, write queries directly rather than leaning on ORM-managed relationships and lazy loading.
**Why**: The brief calls out "no ORMs-as-a-crutch that hide an unthought-through data model." Explicit queries also make N+1 query bugs visible immediately instead of hidden behind lazy-loaded relationships.
**Risk / what I'd revisit with more time**: More boilerplate per query; a larger schema would benefit from a query builder layer to avoid repetition.

### b) No refresh-token rotation
**Decision**: JWT access tokens with a fixed expiry; no refresh-token flow.
**Why**: Full rotation (refresh tokens, revocation lists, rotating secrets) is a half-day of work that doesn't move any Must-have forward for a tens-of-users internal tool.
**Risk**: A stolen access token is valid until expiry with no way to revoke early. **What I'd do next**: short-lived access tokens (~15 min) + rotating refresh tokens stored server-side, revocable on logout.

### c) Testing scope: one test per layer, not broad coverage
**Decision**: One backend unit test (task status-transition logic), one API integration test (task creation end-to-end against a real/test DB), one frontend test (board column interaction) — not a coverage-percentage target.
**Why**: The brief explicitly says coverage % isn't the metric; judgment about *what's worth testing* is. These three cover the riskiest logic (state transitions), the riskiest integration point (API + DB), and the riskiest UI interaction (the thing users actually do most).
**What's explicitly not tested and why**: Auth edge cases (expired/malformed tokens), WebSocket reconnect logic, and concurrent-edit conflict scenarios (two users editing the same task simultaneously) — all real risks, deferred because the time budget doesn't allow exhaustive coverage; noted here rather than silently skipped.

### d) Docker Compose over a production-style multi-stage build
**Decision**: A single `docker-compose.yml` that runs db + backend + frontend for local development; no production-hardened multi-stage Dockerfiles.
**Why**: Listed explicitly under "Could have" in the brief — not worth the time against Must-haves.
**What I'd add**: multi-stage builds (smaller images, no dev dependencies in the final image), a non-root container user, and a separate `docker-compose.prod.yml`.
