# Dataset2 stage-aware reporting — spec

**Date:** 2026-08-24
**Timebox:** design session (this doc) + two separate implementation tasks below — 8 decisions, over the 3-decision threshold.

## Goal
`report.py` and `compare.py` can inspect and diff dataset2's `stage_results` rows (retrieval / intent / generation, individually or combined) the same way they already handle dataset1 — without assuming every run has every stage, and without treating "compare" as only valid when two runs are identical in shape.

## Non-goals (→ parking lot)
- Moving aggregation to pandas/SQL/a dashboard — hand-printing still has real learning value right now (per discussion); this spec's layering (pure dict-returning `summarize`/`compare` functions, printing kept separate) is what keeps that swap cheap *later*, not something to build now.
- Any change to `experiments/ask_eval/*` — separate, already-working track, left untouched.
- New metrics beyond the 4 RAGAS ones already in `grader.py` — reporting task, not a grading task.
- Fancy confusion-matrix visualization (heatmap, etc.) — a plain text table is enough given printing is intentionally being kept simple.

## Decisions this task needs
- [x] `report.py` gains `--stage {retrieval,intent,generation}` for dataset2 rows; if omitted, print every stage present in that run's rows (auto-detect, not all-or-nothing). Dataset1's existing behavior (no stage concept) is untouched.
- [x] New `experiments/reporting/` package, split **by function, not by stage**: `summarize.py` (pure, rows → dict), `compare.py` (pure, two row-sets → dict), `print.py` (dict → terminal text). Chosen over per-stage files so the print layer stays one swappable file, and formatting (widths, headers) stays consistent across stages by construction.
- [x] `experiments/report.py` / `experiments/compare.py` stay as the two top-level CLI entry points — no invocation-path change (`python experiments/report.py run_id` keeps working). They add dataset2 branching (branch on row shape — same precedent as `runner.py`'s Step 1 branch) and delegate to `experiments.reporting.*`.
- [x] Compare semantics: a stage is only comparable between two runs if it's meaningfully computed in both. Retrieval/intent require the stage to have actually run in both runs — error clearly if not, never print an empty/misleading table. Generation is the exception: it's comparable across runs regardless of upstream stages (gold-context vs full-pipeline), because "given this context, how good is the answer" stays well-defined either way — this cross-stage generation comparison is a first-class use case (it's how retrieval's real impact gets measured indirectly), not an edge case to reject.
- [x] Row matching for `compare` stays keyed by `query` text — same convention dataset1's `compare.py` already uses, no new join key needed.
- [x] Intent summary reports per-class confusion (`expected_intent → actual_intent` counts), not just aggregate accuracy — which classes get confused matters more than one percentage.
- [x] Generation summary reports per-metric mean **plus** a low-score count (e.g. `< 0.5`), not mean alone — RAGAS scores can be bimodal; a mean hides a few badly hallucinated answers sitting inside an otherwise-good run.
- [x] Per-row failure drill-down (the `show()` equivalent) extends per stage: retrieval unchanged; intent shows expected vs. actual intent/filters; generation shows query + context used + generated answer + each metric score. This is what lets you inspect *why* a number is low, not just that it is — the original motivation for this whole discussion.

## Acceptance checks
1. `python experiments/report.py <dataset2_run_id> --stage retrieval` on a retrieval-only run prints recall/mrr matching the numbers already verified in Step 1.
2. `python experiments/report.py <dataset2_run_id> --stage intent` prints accuracy + a confusion table; spot-check 2-3 rows by hand against `eval_set2.jsonl`'s `expected_intent`.
3. `python experiments/report.py <dataset2_run_id>` (no `--stage`) on a full-pipeline run prints all three blocks without three separate invocations.
4. `python experiments/compare.py <gold_context_run> <full_pipeline_run> --stage generation` succeeds and shows a per-metric delta, despite the two runs not sharing a retrieval stage.
5. `python experiments/compare.py <gold_context_run> <full_pipeline_run> --stage retrieval` fails with a clear message ("run X has no retrieval stage") instead of an empty or misleading table.
6. `python experiments/report.py <dataset1_run_id>` and `python experiments/compare.py <run_a> <run_b>` (both dataset1, no `--stage`) behave identically to before this change — regression check.
7. Generation drill-down on a low-scoring row shows the query, the context notes actually used, and the generated answer next to the failing metric.

## Done when (Step 4a)
- [x] Acceptance checks pass
- [x] `docs/engineering-standards.md` checklist applied
- [x] `experiments/docs/decisions.md` entry written
- [ ] Committed

## Implementation split (per usual build-session rhythm — one task = one commit = one decision entry)
- **Step 4a**: `experiments/reporting/summarize.py` + `print.py` + `report.py` CLI wiring (`--stage`, dataset2 branch). Single-run reporting only.
- **Step 4b**: `experiments/reporting/compare.py` + `compare.py` CLI wiring (`--stage`, shared-stage detection, generation cross-stage comparison, clear error on unsupported comparisons). (Be careful about generation is None for search/browse queries,consider when implementing compare logic ) — [x] done 2026-08-27, see `decisions.md` entry.
