# AI usage disclosure

## Tools used

- **Cursor** (agent mode, Claude) — the primary tool for this project.
- No other AI tools (ChatGPT, Copilot, etc.) were used.

## What AI was used for

- **Scaffolding and boilerplate**: the Vite/React project setup, the FastAPI
  application skeleton, the docker-compose file, the GitHub Actions workflow,
  and test harness configuration (pytest/vitest fixtures and setup).
- **Implementation against my architecture**: I wrote `ARCHITECTURE.md` (the
  design, the real-time tradeoff analysis, the state-management choice, and
  the scope cuts) before implementation, and used the agent to implement to
  that spec — e.g. the broadcast-after-commit pattern, the
  WebSocket-as-invalidation-signal client, and the optimistic move with
  rollback were design decisions the agent turned into code.
- **Test writing**: drafting the unit/integration/component tests for the
  test scope I had already defined in the architecture doc.
- **CSS**: most of the stylesheet.

## What I changed, rejected, or verified myself

- **Verified the transaction/broadcast ordering**: the key correctness property
  (WebSocket broadcast fires only after the DB transaction commits) is easy to
  get subtly wrong with FastAPI dependency-injected connections, because a
  dependency-managed transaction commits *after* the endpoint body runs. I
  checked that all mutating endpoints manage their transaction explicitly
  (`async with engine.begin()`) and broadcast outside that block.
- **Reviewed the auth code path**: argon2 hashing, the identical error message
  for unknown-email vs wrong-password (no user enumeration), and JWT expiry
  handling.
- **Caught a test-isolation bug**: the first run of the frontend tests failed
  because Testing Library's auto-cleanup doesn't run when vitest globals are
  disabled; fixed with an explicit `afterEach(cleanup)` in the test setup.
- **Ran everything locally**: lint, both test suites, the production
  type-check build, and the full docker compose stack with two browser
  sessions to confirm the real-time board behaviour end-to-end.
- **Business rule ownership**: the "moving an unassigned task to In Progress
  auto-assigns the mover" rule is my decision (documented in the README), not
  an AI suggestion I accepted blindly — it exists so the status-transition
  logic is a real business rule worth unit-testing rather than a trivial enum
  check.

## Judgment call on AI use

I treated the agent as a fast implementer working from a spec I own: the
architecture, scope cuts, data model, and test scope were decided up front in
`ARCHITECTURE.md`, and I reviewed the generated code against those decisions
rather than accepting it wholesale.
