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
- **DB**: PostgreSQL, plain SQL schema (SQLAlchemy Core) so the data model stays explicit and inspectable.

### Data model

Three tables, defined explicitly in `backend/app/schema.py`:

- **users** — `id`, `email` (unique), `display_name`, `password_hash` (argon2), `created_at`.
- **projects** — `id`, `name`, `description`, `created_by`, `created_at`.
- **tasks** — `id`, `project_id`, `title`, `description`, `status`, `assignee_id`, `due_date`, `created_at`, `updated_at`.


## 2. The real-time decision

**Chosen approach: WebSockets, single in-memory connection manager, keyed by board (project) ID.**

### Options considered

Four real options exist for "how does a connected client find out about a change made by someone else":

| Approach | Latency | Server cost | Client complexity | Bidirectional? | Infra needed |
|---|---|---|---|---|---|
| **Short polling** | Bounded by interval (2-5s typical) | High — N clients × 1 request every few seconds, mostly returning "nothing changed" | Trivial | No | None |
| **Long polling** | Near-instant | Medium — holds a connection open, but still one request per event per client | Moderate — needs request re-issue loop | No | None |
| **SSE** | Near-instant | Low — one open HTTP connection per client, server pushes when there's data | Low — native `EventSource` API, auto-reconnect built in | No (client→server still needs regular REST) | None (works over plain HTTP/1.1, proxy-friendly) |
| **WebSockets** (chosen) | Near-instant | Low — one persistent connection per client | Moderate — reconnect/heartbeat logic is ours to own | Yes | None extra now; Redis Pub/Sub once you run multiple instances |

**Why not short polling.** At tens of users polling every 3s, most requests return "nothing changed," so we'd pay a DB round-trip per client per interval for information that's usually negative. It also caps latency at the poll interval — a "live board" that updates every 3-5s doesn't feel live.

**Why not long polling.** Better latency than short polling, but it's essentially reimplementing a weaker version of what SSE/WebSockets give natively (holding a connection open, handling timeouts, re-issuing requests) without gaining anything SSE doesn't already provide more cleanly.

**Why not SSE, even though it's the closest competitor.** SSE is genuinely a defensible alternative here. It's simpler than WebSockets — no ping/pong heartbeat protocol to hand-roll, auto-reconnect is built into `EventSource` — and it's one-directional. The reason we still chose WebSockets: this app's plausible future direction (presence, typing/editing indicators, live cursors on the board) is naturally bidirectional, and building the WebSocket abstraction now avoids adding a second protocol layer later for a marginal implementation cost over SSE today.

**Why WebSockets, and what we're accepting.** One-directional push is enough for today's board updates, but likely next steps — who's viewing a board, typing indicators on a task, live cursors — need the client to send messages back over the same connection. WebSockets cover that without adding a second protocol later (SSE would still need REST for those). The tradeoff: we own reconnect logic, and with multiple server processes each user's socket and REST requests must land on the same instance — otherwise the open socket might be on Server A while the mutation that triggers the broadcast hits Server B. Redis pub/sub sidesteps that by letting any instance notify all connected clients. At tens of users on one process, none of this is a problem yet.

### Scaling the real-time layer (10x / 100x)

The invalidate-then-refetch client pattern and broadcast-after-commit server pattern wouldn't change as load grows — only **how a broadcast reaches every connected socket** would.

**Now (tens of users, one process).** After a task mutation commits, the endpoint calls `manager.broadcast()` on an in-memory dict: `{project_id: [WebSocket, …]}`. Every socket watching that board is on the same machine, so this is simple and fast. No Redis, no load balancer.

**At 10x (hundreds of users, multiple workers).** I'd run more than one backend instance behind a load balancer. The problem I'd hit: User B's WebSocket might be on Server A, but the PATCH that moves a task could land on Server B — and B's in-memory socket list is empty, so nobody gets notified. My fix would be **Redis Pub/Sub**: after commit, the mutating instance publishes `{project_id, event}` to a channel; every instance subscribes and relays to its own local sockets. Any instance can handle any request. The client would still just invalidate and refetch — unchanged.

**At 100x (thousands+).** If I needed message replay (a client offline must catch up on missed events) or wanted to separate WebSocket connection load from API traffic, I'd move to a dedicated message broker (Kafka, NATS) or a standalone realtime gateway. I wouldn't do that for this exercise's scale — only once replay, ordering guarantees, or connection volume become real constraints.

**Bottom line:** the design is correct for one process today. Redis pub/sub is the first step I'd add when running a second worker — not an architectural rewrite.

### Trigger point
Broadcasts fire from inside the mutating endpoint, **after the DB transaction commits successfully**. This keeps "what clients see" always consistent with "what's actually persisted."

### Frontend consumption pattern
The WebSocket message is treated as an **invalidation signal**, not a data payload to merge by hand: `{ type: "task.updated", project_id }` → `queryClient.invalidateQueries(['tasks', project_id])`. This avoids an entire class of bugs (out-of-order messages, partial payloads, merge conflicts with in-flight optimistic updates) in exchange for one extra refetch per event. The user who *made* the change gets an optimistic local update immediately; everyone else gets the refetch-triggered update. If a client misses an event while disconnected, the reconnect refetch catches them up — sufficient for a small team on one board.

## 3. Frontend state management

**Chosen approach: split server state and client state, and treat them as genuinely different problems rather than one "state management library" decision.**

- **Server state** (projects, tasks, board contents — anything that lives in Postgres): **TanStack Query**.
- **Client/UI state** (which modal is open, current filter selection, drag-in-progress state, form inputs before submit): React's built-in `useState`/`useReducer`, no external library.

### Options considered

| Approach | What it's actually for | Fit for this app |
|---|---|---|
| **Context API only** | Passing state down the tree without prop drilling | Works for small UI state |
| **Redux / Redux Toolkit** | Centralized, normalized client state with strict update rules | Real power for large apps with complex client-side state interactions; for this app almost all "state" *is* server state, so Redux would be an overkill at the stage  |
| **Zustand** | Lightweight global store, less boilerplate than Redux | A reasonable choice for the small amount of *client* state this app has (e.g. active board filters, selected task for a detail panel) — genuinely close to what we picked |
| **TanStack Query** (chosen, for server state) | Caching, refetching, and invalidating server-derived data | Directly matches what this app needs: task/project data that's fetched, cached, and must be invalidated on a WebSocket event — invalidation is a first-class concept in the library, not something to build by hand |

**Why not put everything in Redux or Context.** The board's data isn't really app state — it's a cached copy of what's in Postgres. The hard part is keeping that cache correct while three things happen at once: my optimistic edit, the server's response, and another user's change arriving over the WebSocket. That's exactly the problem TanStack Query solves out of the box (query keys, invalidation, refetching); using Redux would mean rebuilding all of that by hand.

**Why not Zustand instead of plain `useState`/Context for the remaining UI state.** Zustand would make sense if lots of unrelated components needed to share UI state (multi-step wizards, complex filters, bulk actions). This app doesn't — the UI state is small and local (open modal, search text, drag state), so plain `useState` plus one thin Context is enough. If that UI state grows and starts crossing many components, Zustand is the next step before Redux.

### How the two halves interact with the real-time layer

This split is what makes the WebSocket-as-invalidation-signal pattern clean: a WS message never touches UI state — it just calls `queryClient.invalidateQueries(['tasks', project_id])`, and TanStack Query refetches and re-renders only the components that need it. If the board data lived in Redux or Context instead, the WebSocket handler would have to merge updates into that store by hand.

## 4. Other tradeoffs made under the 2.5-day constraint

These are deliberate cuts made to ship the board and real-time path — not oversights. Each follows the same shape: what I skipped, the risk, and how I'd fix it.

### a) No refresh-token rotation
I skipped refresh-token rotation to prioritize the board feature and real-time path over a full auth lifecycle.
- **What shipped**: a single JWT access token (default 8h expiry), stored in the browser and sent on every request; logout only clears local state.
- **Risk**: a stolen token stays valid until expiry with no server-side revoke. Logout on one device doesn't kill sessions elsewhere.
- **How I'd fix it**: short-lived access tokens (~15 min) + rotating refresh tokens stored server-side (hashed), revoked on logout; rotate on every refresh so a stolen refresh token is one-shot.

### b) Testing scope: one test per layer, not broad coverage
**Decision**: One backend unit test (task status-transition logic), one API integration test (task creation end-to-end against a real/test DB), one frontend test (board column interaction) — not a coverage-percentage target.
**What's explicitly not tested and why**: Auth edge cases (expired/malformed tokens), WebSocket reconnect logic, and concurrent-edit conflict scenarios (two users editing the same task simultaneously) — all real risks, deferred because the time budget doesn't allow exhaustive coverage.

### d) Dev-oriented Docker Compose, not a production image
I skipped a production-hardened multi-stage build — it's listed under "Could have" and loses to must-haves.
- **What shipped**: one `docker-compose.yml` for local/demo (db + backend + frontend).
- **Risk**: images carry more than they need; no non-root user; no separate prod compose.
- **How I'd fix it**: multi-stage Dockerfiles (no dev deps in the final image), non-root container user, and a `docker-compose.prod.yml`.
