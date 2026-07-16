# Bug Tracker

Bugs discovered but not yet prioritized for fixing. Update status as things change.

**Statuses**: `OPEN` | `FIXED` | `WONTFIX` | `IN PROGRESS`

---

## [OPEN] Ask logging fails — missing column on ask_log table
- **Where**: Ask page logging → `ask_log` table
- **What**: `WARNING | Ask logging failed: table ask_log has no column named retrieval_fallback` — column was added to the model/code but no migration script was written to alter the existing table
- **Fix**: Write migration script to add `retrieval_fallback` column to `ask_log`
- **When found**: 2026-07-16


---

## [OPEN] Embedding model blocks app startup
- **Where**: `src/storage/storage.py` — `Storage.__init__`
- **What**: `SentenceTransformerEmbeddingFunction` (bge-large-en-v1.5) loads into RAM at startup, blocking the UI for ~3–5 seconds before the app is usable
- **Fix**: Lazy-load the embedding function — initialize it only on first search/save, not in `__init__`
- **When found**: 2026-07-14

---

## [OPEN] Ask page text bar not cleared after submit
- **Where**: Ask tab → `src/app.py` — Ask page input widget
- **What**: After submitting a question, the text input box is not cleared — the previous query remains in the field
- **When found**: 2026-07-14
- **Notes**: Not yet investigated

---

## [FIXED] Edit button in search page shows missing fields / results vanish on interaction
- **Where**: Search tab → search for a note → click Edit
- **What**: Edit dialog opened with fields missing/empty; search results also vanished on any interaction
- **When found**: 2026-07-10 · **Fixed**: 2026-07-16
- **Cause**: results were rendered *inside* `if st.button("Search")` — `st.button` is True for exactly one rerun, so the ✏️ click's rerun skipped the whole block and the click landed in a void (the button-is-momentary trap). Follow-up: caching results in `session_state.search_result` fixed vanishing but went stale on delete/edit (cache invalidation — dialog only synced `entries` and `ask_result`).
- **Fix**: store search *params* in session_state on click; recompute + render below the button on every rerun (Recents pattern). `NoteService.search()` gained `log_event` so only the click writes to search_log, not every rerun. Rule for the standards checklist: cache results only when recomputing is expensive; otherwise store intent, recompute.
