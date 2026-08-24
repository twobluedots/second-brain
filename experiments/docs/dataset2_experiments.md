# Dataset2 — what to check and how to run it

Companion to [templates2-query-hints.md](../../docs/design/templates2-query-hints.md) (the spec) and
[decisions.md](decisions.md) (why). This doc is the practical "picking this back up" reference —
what to keep in mind reviewing the raw data, and the two separate ways to actually run experiments
against it.

**Why this exists:** dataset1's eval only ever tested retrieval — nothing tested the Ask pipeline's
analyzer (intent/filter extraction) or the generation stage, so a bad answer could be a retrieval
failure, an intent-detection failure, or a generation failure with no way to tell which. Dataset2
(built 2026-08-21) added the ground truth for this — multi-note `expected_note_ids` for
pattern-intent retrieval, `intent`/`expected_time_filter`/`expected_category_filter` for the
analyzer — but building the harness that actually scores against it, including generation, was
explicitly deferred at the time. The 2026-08-24 session below is that deferred work: retrieval,
intent/filter classification, and generation, all built as independently selectable `runner.py`
stages, so each of the three can finally be measured on its own instead of guessed at from one
end-to-end score.

## What's on disk right now

- `experiments/data/dataset2/templates2.yaml` — 30 templates (11 voice, 19 text), mood/journal/task/achievement only
- `experiments/data/dataset2/generator2.py` — separate from `generator.py`; dataset1 untouched
- `experiments/data/dataset2/notes2.jsonl` — 30 generated notes
- `experiments/data/dataset2/eval_set2.jsonl` — 116 rows (60 `target_system: search`, 56 `target_system: ask`)

As of 2026-08-24: retrieval, intent classification, and generation have all been run through
`experiments/runner.py` against this data (see below) — this is no longer just the generated corpus.

## What to keep in mind when reviewing the raw data

- **Pilot, not a benchmark.** 56 ask rows across 4 categories is enough to catch bugs and read
  qualitatively, not enough for a trustworthy per-intent accuracy number. Don't over-index on any
  single percentage this produces.
- **`expected_category_filter` is null on almost every ask row, on purpose.** Real `ask_log` never
  populated it (0/28 real queries). Only 2 rows probe it deliberately (`t2_task_005`, `t2_ach_005`,
  both `expected_category_filter` set) — those two are the ones to watch if you're checking whether
  the analyzer *should* be extracting a category it currently isn't.
- **`expected_time_filter` is real on 7 rows, always `this_week`.** Everything else is null — matches
  real usage, don't expect much date-filter signal outside those 7.
- **Two rows have multi-note `expected_note_ids`** (the Sunday-dread pattern: `v2_journal_002/002b/002c`,
  and the habit-streak pattern: `v2_ach_002/002b/002c`). Any retrieval/pattern-eval logic needs to
  handle a list, not assume one note per query — this was a deliberate design choice, not an artifact.
- **`days_ago` is a relative offset, not an absolute date.** Whatever loads these notes into a test
  DB needs to compute `created_at = load_time − days_ago` at load time, or the "this week" rows are
  meaningless.
- **Tone was hand-tuned, not perfect.** 3/11 voice notes still use an ellipsis; none are melodramatic
  anymore, but this was iterative prompt-tuning on a small sample (`v2_mood_001/002`, `v2_journal_001`)
  — if a category you haven't spot-checked yet (task, achievement) reads oddly, that's plausible, it
  wasn't specifically checked.

## Two existing harnesses — dataset2 feeds both, differently

There are two separate eval harnesses in this repo already, testing different things. As of
2026-08-24, Track 2 consumes dataset2 (retrieval/intent/generation, config-driven); Track 1 still
doesn't — the gap each needs closed was different from the start.

### 1. `experiments/ask_eval/` — full pipeline, needs a "dumb storage"

`collector.py` + `grader.py` run the real `ask()` pipeline end-to-end (analyzer → retrieval →
generate) and score with reference-free RAGAS metrics (Faithfulness, AnswerRelevancy,
ContextRelevance, ContextUtilization). Today `collector.py` always queries the **real production
Storage** — so dataset2's `expected_note_ids` are meaningless there, those synthetic notes don't
exist in it.

**Next up:** give `collector.py` a "dumb storage" option — load `notes2.jsonl` into an isolated
SQLite + Chroma `Storage` (applying `days_ago` → `created_at` at load time) instead of the
production one, then run dataset2's ask queries through the *unchanged* `ask()` + RAGAS scoring
against that. This makes `retrieved_contexts` in the output record actually comparable to
`expected_note_ids` by reading it — still a manual read, no automated pass/fail yet, but for the
first time the comparison means something.

### 2. `experiments/runner.py` (+ `config.py`, `grader.py`, `compare.py`, `report.py`) — the "test one piece" harness

This is the retrieval-only track that produced `search_experiments.md` — builds its own throwaway
Chroma index straight from `notes.jsonl` (not production, not the full `ask()` pipeline), already
config-driven for comparing individual pieces: `EMBEDDING_MODELS`, `RERANKERS` in `config.py`, with
`compare.py run_a run_b` / `report.py run_id` for diffing. This is the natural home for testing
pieces in isolation — it already has the comparable-configs + run-id + diff infrastructure that
new scenario types would otherwise have to build from scratch.

**Built (as of 2026-08-24):** all three scenarios below, config-driven via
`--config <name.yaml>` (bare filenames, resolved against `experiments/configs/`) instead of the old
hardcoded loop in `__main__`.

- **`dataset2` wired into `DATASETS`** in `config.py` — `{"notes": notes2.jsonl, "eval_set":
  eval_set2.jsonl}`. `runner.py` branches per eval row on schema: `expected_note_id` (singular) →
  dataset1's existing exact/ambiguous path, unchanged; `expected_note_ids` (list) + `target_system`
  → the new dataset2 path.
- **Retrieval scenario** (`stages: [retrieval]`): `grade_retrieval_multi()` in `grader.py` handles
  multi-id ground truth (recall = any expected id retrieved; mrr = best rank among matches) — needed
  for the two `pattern`-intent rows where several notes are all correct answers.
- **Intent-classification scenario** (`stages: [intent]`): only applies to `target_system: "ask"`
  rows (the Search page never calls the analyzer in production, so there's no real code path to grade
  for `search` rows). Scores `intent`/`time_filter`/`category_filter` against
  `eval_set2.jsonl`'s ground truth. The analyzer call itself is pluggable —
  `experiments/pipeline/intent.py`'s `ANALYZERS` registry, selected via `config["analyzer"]`
  (defaults to the production `analyze_query`) — so an experimental analyzer variant can be
  swapped in without touching the grading code.
- **Generation scenario** (`stages: [generation]`, optionally combined with `retrieval`/`intent`):
  composable per-stage — if `retrieval` isn't selected, context comes straight from gold
  `expected_note_ids`; if `intent` isn't selected, the `QueryPlan` is built from the row's own
  ground-truth `intent`/filters instead of a live analyzer call. Scored with the same 4 reference-free
  RAGAS metrics as `ask_eval/grader.py` (`context_relevance`, `context_utilization`, `faithfulness`,
  `answer_relevancy`), selectable via `config["generation_metrics"]`. The generator call is pluggable
  too — `experiments/pipeline/generation.py`'s `GENERATORS` registry, `config["generator"]`, same
  pattern as the analyzer. dataset2 notes (`{id, type, category, days_ago, text}`) are bridged to what
  `generate()`/`format_note()` expect via a small adapter (`note_to_generator_shape()`), using a fixed
  `DATASET2_ANCHOR_DATE` reference point (not wall-clock time) so `days_ago` → `created_at` stays
  reproducible run-to-run.

**Not yet built:** `report.py`/`compare.py` still only understand dataset1's row shape
(`expected_id`, `ambiguous`) — they don't know about dataset2's `stage_results` schema
(retrieval/intent/generation, individually or combined) yet. Spec'd in
[dataset2-stage-reporting.md](dataset2-stage-reporting.md), tracked as its own implementation session.

**Track 1 tells you the full pipeline doesn't fall over on these queries, once it's pointed at the
right notes. Track 2 is where "is analyzer/generation/retrieval individually correct" actually gets
answered — and it's an extension of infrastructure that already exists, not a new build.**
