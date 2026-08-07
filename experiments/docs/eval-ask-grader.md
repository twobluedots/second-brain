# Eval — ask-service RAGAS pipeline (runner/grader split) — spec

**Date:** 2026-08-03 (ratified in planning session)
**Timebox:** 4 sessions this week (see session plan) — each ~1 focused block

## Goal
A rerunnable grader that scores cached ask() outputs with RAGAS, producing retrieval + generation numbers and a written weaknesses list.

## Why the split (the thing that unblocked this)
`eval_ask.py` coupled an expensive working step (5 live `ask()` calls) to a cheap broken step (RAGAS). Every RAGAS crash re-cost the pipeline calls. Fix: generate records once, grade from disk.

- **`experiments/ask_eval/collector.py`** (done) — calls `ask()` once per query, writes each record immediately to `experiments/artifacts/ask_eval/records/run_*.jsonl`. No ask_log pollution. Queries load from `experiments/ask_eval/queries/<query_set>.json` (default: `"default"`) instead of a hardcoded list.
- **`experiments/ask_eval/grader.py`** (done) — loads a records file, runs `ContextRelevance`, `ContextUtilization`, `Faithfulness`, `AnswerRelevancy`, prints/saves scores. Rerunnable; a rerun costs judge calls only, never pipeline calls.
- **`experiments/ask_eval/runner.py`** (done) — thin orchestrator: `collect()` then `grade()` in one call, for a full fresh end-to-end run.
- **`experiments/eval_ask.py`** (monolith) — deleted.

Naming: `ask_eval/` holds the end-to-end pipeline eval (retrieval + generation, live Storage, reference-free RAGAS metrics) as its own folder, distinct from the retrieval-only offline benchmarking (`runner.py`/`grader.py`/`report.py` flat in `experiments/`, ground-truth-based). Same collect-then-grade shape, different layer of the system.

## Session plan (in order)
1. **Grader + retrieval metrics** — `ContextRelevance` + `ContextUtilization` (question ↔ contexts, no answer involved → simplest to get working). Shipped as two metrics instead of the originally planned `ContextPrecisionWithoutReference` — swapped during implementation.
2. **Read retrieval scores** — next to the actual contexts, question by question → retrieval findings.
3. **Generation metrics** — add `faithfulness` + `answer_relevancy`. This is the RAGAS debugging session: run per-question, read the real exception, check installed version against the docs. Fallback if RAGAS keeps fighting past a timebox: hand-roll the judge prompts with direct LLM calls (arguably better learning).
4. **Read generation scores** → the findings list. **That list is the week's deliverable.**

Optional 5th: dump faithfulness's statement decomposition (it splits the answer into claims and verifies each against context); judge whether the decomposition suits note-style text; customize prompts only if the scores feel untrustworthy.

## How to read the scores (the triangle)
No single metric means good/bad — the *pattern* names the component to blame:

| Pattern | Diagnosis |
|---|---|
| high faithfulness + low context precision | Grounded in the **wrong notes** — honest answer, failed retrieval. Not a generation problem. |
| low faithfulness + high answer relevancy | Model answering from **its own knowledge**, ignoring the notes ("being smart about the query"). |
| high faithfulness + high context precision + low answer relevancy | Retrieved and grounded fine, but **dodged the question**. |

## Non-goals (→ parking lot)
- Chunking experiments — need Dataset 2 (long notes) + the v2 design session first; this week chunking is a *learning* session only
- `TestsetGenerator` / synthetic test sets — later
- Multi-answer eval extension (`expected_note_ids`) — already parked
- Tuning the pipeline based on scores — findings first, fixes go to the PM flex slot
- Multi-run averaging — rerun the grader 3-5x per question set and average scores for stability, once the four current metrics are validated against real judgment
- Intent-classification test suite — empty retrieval results are often an intent-classification miss (e.g. search-task queries), not a generation failure; worth a dedicated test suite rather than folding into RAGAS scoring

## Done when
- [x] Grader runs all four metrics (`ContextRelevance`, `ContextUtilization`, `faithfulness`, `answer_relevancy`) from a cached records file with zero live `ask()` calls
- [ ] Findings list written (retrieval + generation weaknesses)
- [x] decisions.md entry: runner/grader split + why the monolith failed
- [ ] Committed; `eval_ask.py` deleted 