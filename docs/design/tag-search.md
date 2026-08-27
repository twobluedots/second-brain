# Tag search — spec

**Date:** 2026-08-18
**Timebox:** ~1 hr (if it can't fit, split before starting — never mid-flow)

## Goal
One sentence. What exists after this task that didn't before?

Entries become findable by exact tag match, not just full-text/semantic search or category browse.

## Non-goals (→ parking lot)
Explicitly out of scope. This section is the scope-creep firewall — anything tempting goes here with one line.
- Fuzzy/partial tag matching (typo tolerance, prefix search) — exact match only
- `entry_tags` normalized join table + index — rejected for now; at 216 entries, `LIKE` (median 0.09ms) and `json_each` (median 0.13ms) are both effectively instant, benchmarked on the real DB
- Tag rename/merge — already deferred (2026-07-29 decisions.md entry)
- LLM auto-suggested tags — already deferred (plan.md parking lot)
- Semantic/embedding-based tag search — separate thread entirely, and today's search-latency finding (embedding inference is 300ms–1.9s vs. tag lookup at ~0.1ms) argues against adding another embedding call for something exact-match already solves cheaply
- Multi-tag AND filter — deferred to a follow-up task, not rejected; start with single-tag and see if the need shows up in practice

## Decisions this task needs
List every decision before writing code. **More than 3 → this is a design session plus separate implementation task(s), not one task.**
- [x] Match approach: SQLite `json_each()` over `LIKE` on the JSON blob — correct semantics (no accidental substring matches), and perf is a non-issue at this scale (see benchmark above)
- [x] No schema migration — `entries.tags` (JSON TEXT) stays as-is; no `entry_tags` join table, no new index
- [x] Single-tag click-to-filter only for this task. Multi-tag AND deferred to a follow-up task — revisit once single-tag filtering is in use and it's clear whether AND-combining is actually needed.

## Acceptance checks
Concrete "do X, see Y" lines. Each becomes a pytest test where possible (service/storage/pure functions); UI checks stay manual.
1. Given an entry tagged `["python", "health"]`, filtering by tag `python` returns it.
2. Given an entry not tagged `python`, filtering by tag `python` excludes it.
3. (multi-tag AND — out of scope, tracked as follow-up)

## Done when
- [ ] Acceptance checks pass
- [ ] `docs/engineering-standards.md` checklist applied
- [ ] decisions.md entry written (if a decision was made)
- [ ] Committed
