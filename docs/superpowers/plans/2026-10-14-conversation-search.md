# Conversation and Search Implementation Plan

Goal: Persist conversations and trip plans, support multi-turn changes, and search opening/booking information with citations.

Architecture: Existing initial trip graph remains. SQLite holds conversation snapshots and search cache; SqliteSaver checkpoints a new LangGraph message workflow. ChatOpenAI binds a Tavily search tool; only validated day changes update the canonical plan.

Constraints: Single backend instance/local personal use; no authentication added; database under backend/data (ignored). No booking/purchase actions. Missing search credentials must produce explicit unavailable results, never invented facts. Invalid edits preserve the original plan. Optimistic version checks and per-session serialization prevent lost writes.

- [x] Storage/API: create/list/get conversations, append chat and persist versions, patch manual edits. Tests: restart recovery, isolation, stale version rejected.
- [x] Search: HTTPS Tavily API, bounded results and timeout, cache, citations and unavailable handling. Tests: errors and missing credentials, no unsafe links.
- [x] Conversation graph: intent extraction, dynamic tool loop, constrained day merge, budgets, SQLite checkpoints. Tests: question leaves plan unchanged, local edit preserves other days, errors leave baseline intact, tool loop bounded.
- [x] Frontend: create conversation from Home, Result chat/history, backend restore, synchronize edits; build with vue-tsc.
- [x] Documentation and verification: setup keys, API tests, build, independent final review.

Execution: inline, as authorized by user. Preserve existing uncommitted MCP fixes. Validation uses stub model/search for repeatable tests; live services only when credentials and network permit.

Verification: 10 backend tests passed; vue-tsc and Vite build passed. Live Tavily returned five sources; live tool-calling model returned four citations without changing the plan. Live two-turn conversation saved an allergy constraint and changed only day two. Independent review findings (partial-day field loss and constraint removal) were reproduced and fixed with regression tests.

Ruling: Work in the current checkout to preserve existing uncommitted MCP fixes and local environment. No commits or branch changes were performed.
