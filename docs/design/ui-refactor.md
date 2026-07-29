# [v2] UI Refactor — spec

**Date:** 2026-07-29
**Timebox:** ~2-3 hrs total, split across the 3 build groups below — each group stays inside its own ~45-60 min sub-timebox; if a group can't fit, split it further before starting, never mid-flow.

## Goal
`app.py` stops being a 637-line monolith: services are wired in one place (`src/services.py`), UI rendering lives in its own module (`src/ui/components.py`), each page is its own file (native Streamlit multipage), the Capture page renders notes the same way every other page does, date-preset filtering resolves inside the service instead of the UI, and `categorize()`/Whisper transcription are cheap and observable to re-run during testing.

## Non-goals (→ parking lot)
- **Local-timezone "Today" fix** — `date_preset` moves into the service layer this round, but the UTC-vs-local-time bug it currently has stays as-is; already tracked separately in the Parking Lot (`docs/plan.md`) and in `docs/bugs.md`.
- **Ask-voice audio retention** — stays transcribe-and-delete; only revisited if `ask_log` shows evidence of garbled transcriptions/re-asks (Parking Lot, evidence-driven).
- **Q9 widget-identity deep-dive** — already correct as-is; parked to `learning.md` as a separate learning topic, not a code change.
- **`AppTest` / scripted UI tests mocking the LLM** — flagged as a future signal (repeated manual retesting), not built this round.
- **v2 tags *experience*** (topic pages, cards-vs-resource) — separate, deferred design session per `plan.md`.

## Decisions this task needs
All already made in a prior scoping session; listed here for the record, not re-litigated:
- [x] Multipage via native `st.navigation` + `st.Page` — each view gets its own file; `app.py` shrinks to navigation + shared setup
- [x] Split extraction by kind: pure logic (no Streamlit dependency) → `src/utils.py`; Streamlit-rendering helpers → new `src/ui/components.py`
- [x] Services factory in `src/services.py`: one `get_storage()`, both `get_note_service()`/`get_ask_service()` build off it explicitly — no service reaches into another's private attributes
- [x] Ask-voice audio: keep discarding after transcription (unchanged); add `whisper_ms` timing regardless, since it's independent of the retention question
- [x] Capture page adopts `render_entry_card()` instead of its own hand-rolled renderer — requires normalizing the session-entry shape closer to the DB-entry shape `render_entry_card` expects
- [x] Collapse the 3 hand-rolled date-math call sites (Search, Journal) onto the existing `src/utils.py::time_filter_to_iso`/`_ts`
- [x] `NoteService.search()` takes `date_preset` as intent and resolves it internally, instead of the UI pre-computing `date_from` and shipping both
- [x] De-duplicate `render_entry_card()`'s two near-identical edit-button branches into one `_edit_button()` helper
- [x] Add `functools.lru_cache` on `categorize()` — avoids repeat LLM calls on identical text during dev add/delete/retest loops; no behavior change for real usage

## Build order

**Group 1 — foundation (do first):**
- `src/services.py` factory
- `src/ui/components.py` extraction + Capture-page unification + `_edit_button()` de-dup

These touch the same file surface and establish the module boundaries everything else depends on.

**Group 2 — depends on Group 1:**
- Multipage split (`st.navigation`/`st.Page`) — new page files import from the now-extracted `src/ui/components.py` and `src/services.py` instead of duplicating extraction mid-split.

**Group 3 — independent, any time:**
- `date_preset` → service (using `src/utils.py`)
- `lru_cache` on `categorize()`
- `whisper_ms` timing

Group 3 has no dependency on Groups 1-2 and can be pulled forward as quick wins if preferred.

## Implementation touchpoints (to build)

**Group 1:**
- `src/services.py` (new): `get_storage()`, `get_note_service()`, `get_ask_service()`, `get_whisper_model()` — replaces the 3 separate `@st.cache_resource` getters at `app.py:17-28`
- `src/ui/components.py` (new): `render_entry_card()`, `_edit_button()`, `format_relative_time()`, the 3 capture dialogs + `edit_note_dialog()` — moved out of `app.py:69-294`
- `app.py:314-335` (Capture page): replace hand-rolled entry loop with `render_entry_card()`; normalize `st.session_state.entries` items to match DB-entry shape (`content_type`, `file_path`, `tags`, etc.)

**Group 2:**
- `app.py` → `pages/capture.py`, `pages/search.py`, `pages/recents.py`, `pages/categories.py`, `pages/journal.py`, `pages/mirror.py`, `pages/ask.py` (naming TBD at build time); `app.py` reduced to `st.navigation([...])` + shared session-state init

**Group 3:**
- `app.py:359-368` (Search) and Journal's date handling → call `src/utils.py::time_filter_to_iso`/`_ts`
- `src/notes_service.py:73-92` `search()`: accept `date_preset`, resolve internally instead of receiving `date_from` from the caller
- `src/categorize.py:64-90`: `@lru_cache` on `categorize()`
- `src/processing.py:8-14`: time the `model.transcribe()` call, return/log `whisper_ms`

## Acceptance checks
1. `app.py` (or the new navigation entrypoint) is under ~100 lines; each page file is independently readable without cross-referencing others for shared rendering logic.
2. Deleting or editing a note from Capture updates the same way it does from Search/Recents (same card, same tag pills, same timestamp).
3. `AskService` and `NoteService` share the identical `Storage` instance (`get_ask_service()`'s storage `is` `get_note_service()`'s storage) — pytest-able via `src/services.py`.
4. Searching with `date_preset="This week"` returns the same result set whether the UI passes only `date_preset` or previously passed `date_from` — pytest against `NoteService.search()`.
5. Calling `categorize(text)` twice with identical `text` hits the LLM provider chain only once (mock/count assertion) — pytest against `src/categorize.py`.
6. A voice note capture logs a `whisper_ms` value greater than 0.
7. Navigating between pages preserves the sidebar and doesn't lose `st.session_state` needed for in-flight dialogs.

## Done when
- [ ] Acceptance checks pass
- [ ] `docs/engineering-standards.md` checklist applied
- [ ] decisions.md entry written (if any implementation-time deltas from this spec occur)
- [ ] Committed — one task (per group above) = one commit
