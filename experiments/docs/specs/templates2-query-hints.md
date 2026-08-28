# Templates2 + dataset2 — spec

> **Status:** shipped 2026-08-21 — frozen spec, kept as a point-in-time record. Rationale and
> outcome in [decisions.md](../decisions.md) (2026-08-21). Living how-to for using the dataset:
> [dataset2_experiments.md](../dataset2_experiments.md).

**Date:** 2026-08-21
**Timebox:** design session (this doc) + separate implementation tasks per step below — 9 decisions, well over the 3-decision single-task threshold.

## Goal
A new `templates2.yaml` + regenerated `generator.py` output (`notes2.jsonl`, `eval_set2.jsonl`) whose query hints are typed as search-style vs. ask-style, with enough structure (`intent`, `expected_time_filter`, `expected_category_filter`, `expected_note_ids`) to later evaluate the Ask pipeline stage-by-stage (analyzer / retrieval / generation / end-to-end), not just retrieval like dataset1.

## Non-goals (→ parking lot)
- Rewriting all ~40 existing templates — pilot only (mood, journal, task, achievement).
- Tag-aware query rewriting — belongs to `docs/design/tag-search.md`.
- Any change to `analyzer.py`, `retrieval.py`, or the Search page.
- Building the eval scripts that consume dataset2 (analyzer-only / retrieval-only / generation-only / end-to-end scoring) — this task only produces the data.
- A live online-vs-offline comparison against real `ask_log` usage — only one real example exists today, not enough volume.

## Decisions this task needs
- [x] Split `query_hints` → `query_hints_search` (keyword/refinding) + `query_hints_ask` (natural questions implying a filter), per template.
- [x] Ask-style hints carry `expected_time_filter` / `expected_category_filter` so `analyzer.py` extraction can be scored directly.
- [x] Eval rows use `expected_note_ids` (list) + `intent` (factual/pattern/browse, matching `analyzer.py`) instead of a single `expected_note_id` — factual is 1:1, pattern/temporal are many-notes-to-one-query.
- [x] Same dataset consumed at 4 levels later (analyzer-only, retrieval-only via given filters, generation-only via gold context, end-to-end) rather than separate datasets per purpose.
- [x] Pilot size: ~40–80 ask rows across the 4 categories — directional/qualitative, not a trustworthy per-intent accuracy number.
- [x] Model: `gpt-4o-mini` via OpenAI (already `generator.py`'s default) — no Ollama. Dissatisfaction with dataset1 was about Ollama runs and hint style, not this model.
- [x] Pilot scope: **mood, journal, task, achievement** — clearest ask/search gap, and task/achievement have zero template coverage today despite real usage (6 and 4 entries in the last 30 days).
- [x] Voice/text mix: keep meaningful voice coverage — the DB's 98% text skew is a deployment artifact (no mobile access yet), not reduced relevance.
- [x] Persona prompt: describe tendencies (jumps topics, fragments, trails off) instead of naming "ADHD"; voice-type prompts mimic Whisper-repunctuated output — no "...", no emoji.

## Acceptance checks
1. `templates2.yaml` has templates for mood/journal/task/achievement, each with `query_hints_search` and `query_hints_ask` (with `expected_time_filter`/`expected_category_filter` on ask hints).
2. `generator.py` writes `notes2.jsonl` + `eval_set2.jsonl` without touching `notes.jsonl`/`eval_set.jsonl`.
3. `eval_set2.jsonl` rows carry `target_system`, `intent`, `expected_note_ids` (list), and ask-rows carry the expected filters.
4. Manual spot-check of ~10 ask rows: hints read as natural questions (not disguised search), filter labels look correct, no "ADHD" in generated text, voice-type notes have no "..." or emoji.
5. `USE_OLLAMA` unset for the generation run (confirm via env before running).

## Done when
- [x] Acceptance checks pass — 30 templates (mood/journal/task/achievement), 116 eval rows (60 search / 56 ask) generated via `generator2.py`; dataset1 untouched. Spot-checked: no emoji, 3/11 voice notes use an ellipsis (down from 11/11 pre-tuning — see decisions.md). `USE_OLLAMA` confirmed unset before the real run.
- [x] `docs/engineering-standards.md` checklist applied — mostly N/A: this is a standalone experiments data-generation script, no `src/`/`ui/` or SQLite/ChromaDB changes. Consciously skipped pytest coverage, matching `generator.py`'s own precedent (no tests either); manual schema/content checks substituted (see decisions.md).
- [x] decisions.md entry written — `experiments/docs/decisions.md`, 2026-08-21 entry (not `docs/decisions.md` — that log is product milestones, this is the experiments/eval track)
- [x] Committed

Run plan and review notes for actually using this dataset: [dataset2_experiments.md](../dataset2_experiments.md).
