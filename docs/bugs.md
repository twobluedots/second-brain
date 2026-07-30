# Bug Tracker

Bugs discovered but not yet prioritized for fixing. Update status as things change.

**Statuses**: `OPEN` | `FIXED` | `WONTFIX` | `IN PROGRESS`

---

## [OPEN] Audio recording broken when accessing via Tailscale (non-localhost)
- **Where**: Ask page → `st.audio_input` widget
- **What**: Widget shows "An error has occurred, please try again." — browser blocks microphone access entirely; no Python traceback
- **When found**: 2026-07-30
- **Cause**: Browser MediaRecorder API requires a secure context (HTTPS or localhost). Tailscale access is `http://100.x.x.x:8501` — not secure, so mic is blocked at the browser level before any Python code runs
- **Workaround**: Use `http://localhost:8501` when testing on the same machine
- **Fix path**: Enable HTTPS via `tailscale cert <device-name>` and serve over HTTPS; or run a local TLS proxy

---

## [OPEN] Journal entry timestamps shown in UTC, not local time
- **Where**: Journal tab → `src/app.py:471`
- **What**: Each journal entry is prefixed with `HH:MM` formatted directly from the UTC `created_at` string — displayed time doesn't match the user's local clock
- **When found**: 2026-07-27
- **Cause**: `datetime.fromisoformat(entry["created_at"]...).strftime("%H:%M")` never converts from UTC to local timezone before formatting
- **Related**: same root cause family as the open backlog item in `docs/plan.md` ("Today" filters use UTC midnight instead of user-local timezone — Search presets, Journal day range, Mirror week math)

---

## [FIXED] Ask logging fails — missing column on ask_log table
- **Where**: Ask page logging → `ask_log` table
- **What**: `WARNING | Ask logging failed: table ask_log has no column named retrieval_fallback` — column was added to the model/code but no migration script was written to alter the existing table
- **When found**: 2026-07-16 · **Fixed**: 2026-07-16
- **Cause**: `CREATE TABLE IF NOT EXISTS` never alters an existing table, and `log_ask_event` swallows its own errors by design — so inserts failed silently while the Ask page looked healthy. Only visible in app.log WARNINGs.
- **Fix**: `scripts/migrate_ask_log_retrieval_fallback.py` (ran 2026-07-16; 3 existing rows backfilled with 0). Lesson for standards: every schema change needs a migration script *at the time of the change* — and swallow-errors logging means app.log WARNINGs are the only tripwire; check them after schema work.


---

## [WONTFIX] Embedding model blocks app startup
- **Where**: `src/storage/storage.py` — `Storage.__init__`
- **What**: `SentenceTransformerEmbeddingFunction` (bge-large-en-v1.5) loads into RAM at startup, blocking the UI for ~3–5 seconds before the app is usable
- **When found**: 2026-07-14 · **Decided**: 2026-07-24
- **Reasoning**: A 3-5s one-time startup delay is tolerable and lazy-loading wouldn't meaningfully improve the experience — not worth the effort right now.

---

## [FIXED] Ask page text bar not cleared after submit
- **Where**: Ask tab → `src/app.py` — Ask page input widget
- **What**: After submitting a question, the text input box is not cleared — the previous query remains in the field
- **When found**: 2026-07-14 · **Fixed**: 2026-07-16
- **Cause**: n/a — fixed as a side effect of other Ask page work, never updated in this tracker at the time
- **Fix**: `src/app.py:533-579` bumps `ask_form_version` on submit, which changes the `text_key`/`audio_key` used by `st.text_input`/`st.audio_input` (e.g. `ask_text_{version}`) — the rerun mints fresh widgets with no prior value. Same widget-key-bump pattern as the Edit button fix below.

---

## [FIXED] Edit button in search page shows missing fields / results vanish on interaction
- **Where**: Search tab → search for a note → click Edit
- **What**: Edit dialog opened with fields missing/empty; search results also vanished on any interaction
- **When found**: 2026-07-10 · **Fixed**: 2026-07-16
- **Cause**: results were rendered *inside* `if st.button("Search")` — `st.button` is True for exactly one rerun, so the ✏️ click's rerun skipped the whole block and the click landed in a void (the button-is-momentary trap). Follow-up: caching results in `session_state.search_result` fixed vanishing but went stale on delete/edit (cache invalidation — dialog only synced `entries` and `ask_result`).
- **Fix**: store search *params* in session_state on click; recompute + render below the button on every rerun (Recents pattern). `NoteService.search()` gained `log_event` so only the click writes to search_log, not every rerun. Rule for the standards checklist: cache results only when recomputing is expensive; otherwise store intent, recompute.
