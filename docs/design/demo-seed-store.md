# Demo seed store — spec

**Date:** 2026-08-31
**Timebox:** ~1 hr (if it can't fit, split before starting — never mid-flow)

## Goal
A one-command, reproducible demo database (SQLite + ChromaDB) seeded from a fixed
synthetic note set, that the app can be pointed at via env vars for README
screenshots and a "clone and try it with sample data" path — with zero real notes
involved and no changes to `src/`.

## Non-goals (→ parking lot)
- Taking the actual screenshots / GIF and embedding them in the README — follow-up task; this task ships the store + a documented launch command.
- ~~Covering all 7 categories.~~ **Closed 2026-09-01** — see the demo-fixture decision below. All 7 now populated.
- Preserving the fixture's `voice`/`text` split. All rows seed as `content_type="text"` — a `voice` card calls `st.audio(file_path)` ([ui/components.py:63](../../ui/components.py#L63)) and there is no audio file. The content is the transcript anyway.
- Seeding audio/image files on disk. `file_path` stays null.
- `Storage.save()` gaining a `created_at` param, an auto-seed-on-empty mode, or a separate `demo_app.py` entry point. Not needed.
- Committing the built `.db` / chroma dir — already covered by `.gitignore` `data/*`; the seed script is the source of truth.

## Decisions this task needs
- [x] **Backdating `created_at` — no `src/` change.** Seed script inserts via `Storage.save()` (lands at "now"), then runs a direct `UPDATE entries SET created_at = ?` on the demo SQLite (throwaway script, throwaway DB — fine), then calls `storage.reindex_all()` which rebuilds ChromaDB from SQLite and already respects `created_at` / `created_at_ts` ([storage.py:602](../../src/storage/storage.py#L602)). Rejected: optional `created_at` param on `Storage.save()` (touches core for a fixture-only need); seed-at-now with no backdating (kills the "this week" Ask time-filter demo and the multi-week Sunday-dread / walk-streak series).
- [x] **Categorization — bypass the LLM.** Script calls `Storage.save(entry)` directly with the fixture's `category`, then `Storage.log_category_event(entry_id, ai_suggested=None, final_category=..., event_type='seed')`. Deterministic screenshots, no API key needed to build the demo, no LLM spend. Category chips still render in the UI, so the "auto-categorize" story is visually intact. Nothing in `src/`/`ui/` reads `category_events` back, so `event_type='seed'` is safe.
- [x] **Wiring — opt-in env var.** `config.py` gains `DEMO_DB_PATH = data/demo/entries.db` and `DEMO_CHROMA_PATH = data/demo/chroma_data` (both already gitignored via `data/*`, so no `.gitignore` change). `ui/services.py` `get_storage()` reads `SECOND_BRAIN_DB` / `SECOND_BRAIN_CHROMA`; if **both** are set it returns `Storage(db_path=..., chroma_path=...)`, else `Storage()` unchanged. Vars are meant to be passed as a one-command shell prefix — nothing to unset after. Launch line documented in README + experiments/README.

- [x] **Demo corpus — a curated fixture, not the eval set (2026-09-01).** `seed_demo.py` reads [scripts/fixtures/demo_notes.jsonl](../../scripts/fixtures/demo_notes.jsonl); it no longer touches `notes2.jsonl`. The eval fixture is written for retrieval-eval, not for a public demo: 12 of its 30 notes are mental-health content (Sunday dread ×3, anxiety, overstimulation) or name real people ("jess", "Sarah"), which is not what a public README should show. Those 12 are dropped; the 18 neutral ones (insurance renewal, walk streak, tax return, errand lists) are **copied** into the demo fixture, and 21 short practical notes are added — travel/motion sickness, food reactions, sleep, shoes/plasters, tea — which also fill `learning`/`reference`/`insight` and give Ask real clusters to retrieve ("what do I need to do before travelling?" → 5 sources). Rejected: filtering `notes2.jsonl` by an id exclusion list (couples the demo to an eval file that can be regenerated, and the demo corpus stops being readable in one place); appending to `notes2.jsonl` (silently shifts eval numbers). Cost accepted: the 18 kept notes' text is duplicated across the two fixtures.

## Acceptance checks
1. `seed_demo.py` (pointed at tmp paths) on empty dirs → 39 entries; category counts match the fixture (`achievement` 10, `task` 8, `insight` 7, `reference` 7, `journal` 4, `learning` 2, `mood` 1); `max(created_at) - min(created_at)` spans ≥ 30 days; every entry `content_type == "text"`. (pytest)
2. Running `seed_demo.py` twice → still exactly 39 entries, no duplicate ids, Chroma count == 39. (pytest — wipe-then-rebuild is idempotent)
3. `get_storage()` with `SECOND_BRAIN_DB` + `SECOND_BRAIN_CHROMA` set (monkeypatch) → `storage.db_path` / `storage.chroma_path` equal those values. With neither set → equals `DB_PATH` / `CHROMA_PATH`. With only one set → falls back to defaults (both-or-nothing). (pytest)
4. `SECOND_BRAIN_DB=data/demo/entries.db SECOND_BRAIN_CHROMA=data/demo/chroma_data uv run streamlit run ui/app.py` → Recents lists the demo notes; Ask "have I kept the streak going this week?" returns the walk-streak answer citing the `achievement` notes. (manual)
5. Plain `uv run streamlit run ui/app.py` with no env vars → opens the normal store, byte-for-byte unchanged. (manual)

## Done when
- [x] Acceptance checks pass (1–3 pytest green; 4–5 substance verified headlessly — semantic search + backdated recents return the expected notes against the built store; full UI launch left to the user via the documented command)
- [x] `docs/engineering-standards.md` checklist applied (demo paths in `config.py`; seed script logs count via `src.logger`; env-var branch covered by test)
- [x] decisions.md entry written (2026-08-31)
- [ ] Committed (ugly is fine)
- [ ] Reminder logged to note the key decisions
