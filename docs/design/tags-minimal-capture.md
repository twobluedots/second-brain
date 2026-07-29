# [v2] Tags — Minimal Capture — spec

**Date:** 2026-07-28
**Timebox:** ~1 hr (if it can't fit, split before starting — never mid-flow)

## Goal
Notes can be tagged with free-text, user-defined, multi-tag labels at capture time, and those tags show on note cards.

## Non-goals (→ parking lot)
- Tag browse/filter view (topic pages) — a dedicated page to click a tag and see all notes with it, like the existing Categories page. Later v2 session.
- LLM tag auto-suggestion — deferred
- ChromaDB tag metadata / combined semantic+tag search — deferred
- Tag hierarchy/taxonomy — not designed yet
- Backfill onto existing notes — batch script later, once real topics are known
- Tag rename/merge/management UI — later, once real topics are known
- Third-party tag-input component (`streamlit-tags`) — parked as a fallback if `st.multiselect` UX doesn't hold up in practice

## Decisions this task needs
- [x] Input widget: `st.multiselect(accept_new_options=True)` — native Streamlit (1.51.0 has it), no new dependency; gives pills + × removal + autocomplete for free
- [x] Single-word tags only; multi-word free text auto-converts internal spaces → dashes (`machine learning` → `machine-learning`)
- [x] Leading `#` stripped on save (`#python` and `python` both save as `python`)
- [x] Tags are fully case-sensitive — `python` and `Python` are separate, independent tags, both shown separately in autocomplete. No case-folding/merging; that's deferred to the future tag rename/merge session (see non-goals above), by conscious choice once a collision is actually noticed, rather than automatically now.
- [x] No cap on tags per note (unbounded)
- [x] Autocomplete options = existing distinct tags pulled from SQLite (no LLM)
- [x] Tags stored in SQLite only for now — column + JSON serialization already exist (`Entry.tags`, `storage.py`); ChromaDB metadata skipped. Built with a dedicated `tags` table for the distinct/autocomplete list, not a scan over `entries.tags` — see `decisions.md` 2026-07-29.
- [x] Pills use Streamlit's native multiselect chip styling — no custom color scheme this round
- [x] No backfill onto existing notes

## Implementation touchpoints (built)
- `src/tags.py` (new): `normalize_tag`/`normalize_tags` — strip leading `#`, convert internal spaces to dashes
- `src/storage/storage.py`: `tags` table + `get_all_tags() -> list[str]` (ordered by `last_used_at DESC`); `save()` and `update()` upsert into it
- `src/notes_service.py`: `save_note()` normalizes tags before `Entry()`; `get_all_tags()` and `update_tags()` passthroughs
- `src/app.py` capture form: `st.multiselect(..., accept_new_options=True)` on all three dialogs, wired into `save_note(tags=...)`
- `src/app.py` `render_entry_card()`: renders `entry.get("tags")` as `#`-prefixed pills alongside the category badge
- `src/app.py` `edit_note_dialog()`: tags now editable on existing notes too (beyond original scope) — same multiselect pattern, saved via `update_tags()`

## Acceptance checks
1. Typing a new word into the tag widget and submitting a note saves it in `entries.tags` as a JSON array.
2. Typing `#python` saves as tag `python` (no hash).
3. Typing `machine learning` as a new tag saves as `machine-learning`.
4. A note with tags shows tag pills on its card wherever `render_entry_card` is used.
5. Typing a prefix of an existing tag, in any case, surfaces it in the autocomplete dropdown.
6. A note saved with zero tags behaves exactly as today (no crash, no empty pill row).

## Done when
- [x] Acceptance checks pass (spot-checked manually)
- [x] `docs/engineering-standards.md` checklist applied
- [x] decisions.md entry written (if a decision was made)
- [x] Committed (ugly is fine)
