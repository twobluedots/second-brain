# Bug Tracker

Bugs discovered but not yet prioritized for fixing. Update status as things change.

**Statuses**: `OPEN` | `FIXED` | `WONTFIX` | `IN PROGRESS`

---

## [OPEN] Note truncation (400-char cap) removed from generator without a replacement strategy
- **Where**: `src/rag/generator.py` — was `_NOTE_TRUNCATE = 400`, used in `_format_notes()` and `_plain_fallback()`
- **What**: Each retrieved note's content was hard-truncated to 400 chars (mid-sentence) before being shown to the generation LLM. Deactivated 2026-08-12 while fixing eval context handling — removed rather than kept as an unexamined constant.
- **Why flagged**: actual note lengths (`data/database/entries.db`): median 126, mean 249, only 21/189 (~11%) exceed 400 chars, but max is 4550 — so it rarely triggers, but when it does it silently drops up to ~4150 chars for a token savings that's negligible against modern context windows.
- **Fix path**: revisit with a deliberate strategy (larger cap, summarization, or truncate-with-notice) instead of no cap at all — no cap is fine short-term but could get costly if note volume/length grows.

---

## [OPEN] `created_at` date/time extracted via fixed-width string slicing (`[:10]`, `[:16]`) instead of parsing
- **Where**: `src/rag/generator.py` — `format_note()`, `_plain_fallback()`
- **What**: Dates pulled from `created_at` (e.g. `'2025-10-30T15:55:20.567449Z'`) via `[:16]` instead of `datetime.fromisoformat(...)`.
- **Why flagged**: safe today since `storage.py` always writes fixed-width ISO timestamps, but it's a positional assumption with no validation — a future change to timestamp generation or format would silently produce a garbled date instead of erroring.
- **Fix path**: `datetime.fromisoformat(note["created_at"].replace("Z", "+00:00")).strftime("%Y-%m-%dT%H:%M")` (same pattern already used in `storage.py:192`).

---

## [FIXED] Multi-word tags not hyphenated in UI after Add dialogs (session-state/DB desync)
- **Where**: `ui/components.py` — `add_voice_dialog` (~line 123-149), `add_image_dialog` (~line 168-183), `add_text_dialog` (~line 198-211); surfaced as a crash in `edit_note_dialog` (line 234)
- **What**: Typing a multi-word tag like "system design" via the Add dialogs' `st.multiselect(..., accept_new_options=True)` saved correctly to the DB as "system-design", but the *raw* unhyphenated string was what got appended to `st.session_state.entries`. Later clicking Edit on that note threw `StreamlitAPIException: The default value 'system design' is not part of the options` — `current_tags` (from stale session state) no longer matched `get_all_tags()` (from DB, already hyphenated).
- **When found**: 2026-08-11 · **Fixed**: 2026-08-11
- **Cause**: `NoteService.save_note()` (`src/notes_service.py:37`) normalizes tags internally via `normalize_tags()` (`src/tags.py`) before persisting, but only returned `(entry_id, category)` — the normalized list was never handed back to the caller. The three Add dialogs then appended the *raw* multiselect output (`tags or []`) into `st.session_state.entries` instead of the normalized value actually saved to the DB. `edit_note_dialog` didn't have this bug — it uses `service.update_tags()`'s return value, which *is* normalized (`src/notes_service.py:50-54`).
- **Fix**: `save_note()` now also returns the normalized tags (`tuple[str, str, list[str]]`); the three Add dialogs use that return value instead of the raw `tags` variable when appending to `st.session_state.entries`.

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

## [FIXED] Ask page — second voice recording silently ignored
- **Where**: Ask page → `ui/pages/ask.py` — voice transcription block
- **What**: After recording once, a second recording (re-recording before hitting "Ask", or retrying after the Ask pipeline errored) never got transcribed — the text field kept the old/empty value with no error shown
- **When found**: 2026-08-26 · **Fixed**: 2026-08-26
- **Cause**: Transcription was guarded by a one-shot `ask_transcribed_{version}` boolean that flipped to `True` after the *first* recording of a form version and was never reset — including when transcription itself failed. `ask_form_version` (and thus a fresh flag) only bumps on a successful "Ask" click, so any recording after the first was skipped regardless of whether it was a new clip.
- **Fix**: Replaced the boolean with `ask_voice_processed_{version}`, which stores the transcribed recording's `file_id` (stable per distinct `st.audio_input` clip) and only skips re-transcription when the current clip's `file_id` matches. On failure, `processed_key` is left unset and a "Retry transcription" button is shown — it re-runs transcription on the same audio (no re-recording needed, so a long recording isn't lost to a transient failure).

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

---

## [FIXED] Tag chip click — infinite rerun loop
- **Where**: `ui/components.py` — `render_entry_card()`'s tag pills (`st.pills`), used on Recents/Search/Categories
- **What**: Clicking a tag chip (e.g. `#journal`) could hang the app in an endless rerun loop — page never finishes loading, browser shows a permanent spinner/"Stop" state
- **When found**: 2026-08-27 · **Fixed**: 2026-08-27
- **Cause**: `st.pills` is a *sticky* widget — its selected value persists in `st.session_state` across reruns, not just the one rerun where the click happened. The click handler treated "pill currently reports selected" as "user just clicked it" and reacted by calling `st.switch_page()`. Since the entry a tag was clicked from is guaranteed to reappear in its own tag-filtered results, that same widget (same key) redraws already-selected on the next render — `st.pills` reports the stale selection again with no new click, `switch_page` fires again, which redraws the same entry again... forever.
- **Fix**: `del st.session_state[pills_key]` immediately after acting on a click, before `switch_page` — makes the click genuinely one-shot by clearing the sticky selection, so the widget starts unselected on its next render instead of replaying the old value. Verified the click fires exactly once and the delete executes without error in an isolated repro; confirmed no more hang after a live retest.
- **Lesson for standards**: any "sticky" selection widget (`st.pills`, `st.segmented_control`, `st.radio`, `st.selectbox`) used to trigger a one-time *action* (not to hold ongoing UI state) needs its key cleared right after acting on it — otherwise the action can refire on any later rerun that redraws the same widget key, including loops when the action's own effect causes that redraw.
