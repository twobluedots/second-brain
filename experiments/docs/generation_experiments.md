# Generation Experiments: Findings & Next Steps

> **All notes and queries quoted in this doc are synthetic test data**, generated for evaluation —
> none are real personal notes.

Companion to [retrieval_experiments.md](retrieval_experiments.md) — that doc covers retrieval (which notes come back); this one covers generation (what the model does with them): faithfulness, answer relevancy, and the statement-decomposition read described in [eval-ask-grader.md](eval-ask-grader.md)'s metric triangle.

## Overview

| Date | Run | Query set | Faithfulness (avg) | Answer Relevancy (avg) | Notes |
|---|---|---|---|---|---|
| 2026-08-12 | `run_0a4a47cee` → `run_20260812T150305` (ask_eval, live entries) | ask_eval `queries/default.json` | 0.73 → 1.0 | — | Not a metric or generation-quality finding — an eval-harness bug (see Experiment 1). Faithfulness "failures" were false negatives from missing note metadata in eval context, fixed same day. |
| 2026-08-24 | `dataset2_generation_20260824-121145` | dataset2 `eval_set2.jsonl`, gold context, 56 `ask` rows | 0.933 | 0.510 (27/56 low) | **Superseded** — includes `browse`-intent rows scored with a QA-shaped metric; see Failure Category 1 below. Bug fixed same day in `runner.py` (see `experiments/docs/decisions.md`). |
| 2026-08-28 | `dataset2_generation_20260828-090947` | same, `browse` rows excluded per fix | 0.892 | 0.515 (14/34 low) | Fix confirmed: row count dropped 56→34, browse-specific extreme gaps (e.g. 0.916 vs 0.293 on the identical source note) are gone. Relevancy mean barely moved — the *browse* noise is gone, but a comparable residual problem persists across the remaining qa/factual/pattern rows (categories 2–5 below). **Faithfulness fell 0.933 → 0.892: the excluded `browse` rows were easy-faithful and had been inflating the average; the residual gap is Categories 7–8.** |
| 2026-08-24 | `dataset2_bge-large_vector_n10_intent-retrieval-generation_20260824-130500` | dataset2, full pipeline, bge-large n10, 56 rows | 0.941 | 0.600 (18 low) | Experiment 3 — real retrieval in front of the generator. |
| 2026-08-27 | `dataset2_openai-3-small_vector_n15_intent-retrieval-generation_20260827-112737` | dataset2, full pipeline, openai-3-small n15, 34 rows | 0.944 | 0.557 (13 low) | Experiment 3. |

---

## Dataset

Eval set: `experiments/data/dataset2/eval_set2.jsonl`, 56 `ask` rows across 4 categories
(mood / journal / task / achievement), synthetic. Pilot, not a benchmark — read qualitatively,
don't trust any single per-intent percentage. Full corpus detail in
[dataset2_experiments.md](dataset2_experiments.md).

**Two run types feed the Overview table; their absolute numbers are not comparable:**

| Run type | How | Isolates |
|---|---|---|
| Generation-only (gold context) | `runner.py --stage generation`; context = row's `expected_note_ids`. No retriever, no reranker — the notes are handed straight to the generator. | Generation alone — retrieval cannot be the cause. The 2026-08-24 / 08-28 runs (Experiment 2). |
| Full pipeline | Real retrieval in front of the generator (bge-large + reranker, or `ask_eval/` end-to-end) | End-to-end behaviour — a low score may originate upstream in retrieval or the analyzer. (Experiment 3.) |

The two are not comparable on *absolute* numbers, but each generation metric asks "given this
context, how good is the answer" — which is well-defined either way. That's what makes the
Experiment 3 comparison legitimate.

Two dataset facts the failure categories below lean on:
- `days_ago` is a relative offset; `created_at` is computed at load time. Every absolute date in an
  answer is therefore inferred from note **metadata**, not note text (see Categories 7–8).
- `expected_time_filter` is `this_week` on only 7 rows; `expected_category_filter` is deliberately
  null on almost all — matches real usage, expect little date/category-filter signal elsewhere.

---

## Experiment 1 — Real-data pass on `ask_eval`, and the eval-harness bug it exposed (2026-08-12)

**Setup:** full `ask()` pipeline over live entries, scored with reference-free RAGAS (faithfulness,
answer relevancy, context relevance, context utilization). Query set: `ask_eval` `queries/default.json`.

**Result:** answers read fine but faithfulness came back at 0.73. Dumping the judge's intermediate
output (`FaithfulnessWithDecomposition`, not just the final score) showed the number was an
eval-harness artifact, not real unfaithfulness.

### The bug

- **Symptom:** date-attribution claims failed. "On July 28, the user mentioned clean meals" →
  verdict 0, "context does not specify dates."
- **Cause:** `ask_eval/collector.py` saved only `id`+`content` per retrieved note for eval, while
  `generator.py`'s real prompt also included `created_at`/`category`/`content_type` (via
  `_format_notes()`). The judge checked dated claims — which the generator legitimately saw —
  against context that never carried a date.
- **Fix:** extracted `format_note()` in `generator.py` as the single formatter shared by the
  generation prompt and eval context; `collector.py` now captures full metadata
  (`docs/decisions.md`, 2026-08-12). Post-fix the same claim scored verdict 1 ("context explicitly
  states... on July 28") and faithfulness went 0.73 → 1.0 on the same query set — confirmed at the
  reasoning level, not just the score.

**Aggregation-judgment hypothesis** (`eval-ask-grader.md` parking lot, `decisions.md:175` — does
faithfulness under-evaluate multi-note synthesis/ranking answers?): this bug was masking the answer.
Post-fix, the synthesis-style "most important wins" question scored 13/13 faithful claims — no
evidence of the gap, but the sample is small (3 answered questions). Recheck with a larger set
before closing.

### Statement Decomposition Assessment — Round 1 (2026-08-12)

<!-- One entry per assessment round — keep old rounds so the redo can be compared against the original. -->

**Reviewed:** 3 answered questions from `run_0a4a47cee.jsonl` (pre-fix), re-checked post-fix against
`run_20260812T150305` — "most important wins from last month" (synthesis/ranking-style), "anything
makes me feel good in the morning," "what did I learn related to coding recently."

**Worked:** statements were atomic and faithful to the answer text — no decomposition artifacts. The
NLI `reason` field was specific enough to diagnose *why* a claim failed, which is what surfaced the
plumbing bug instead of leaving a mystery score.

**Didn't:** not where the parking-lot hypothesis expected — nearly every verdict-0 statement was a
date-attribution claim failing on missing metadata, a plumbing bug rather than a synthesis/ranking
judgment gap.

**Verdict:** pre-fix scores conflated the plumbing bug with real unfaithfulness — not trustworthy.
Post-fix they are, and the hypothesized aggregation/ranking blind spot didn't appear even on the
synthesis-style question. Sample small; recheck before treating the hypothesis as closed.

---

## Experiment 2 — Generation-only runs on dataset2 gold context (2026-08-24, rerun 2026-08-28)

**Setup:** `runner.py --stage generation`, context = each row's `expected_note_ids` (gold). No
retrieval and no reranking in this stage — the notes are handed to the generator directly, so any
low score is generation or metric, never retrieval. 56 `ask` rows; the 2026-08-28 rerun excludes
`browse` rows (→ 34) per the Category 1 fix.

| Run | rows | faithfulness | answer_relevancy | context_relevance | context_utilization |
|---|---|---|---|---|---|
| 08-24 | 56 | 0.933 (1 low) | 0.510 (27 low) | 0.790 (2 low) | 1.000 |
| 08-28 (browse excluded) | 34 | 0.892 (1 low) | 0.515 (14 low) | 0.882 (0 low) | 1.000 |

Faithfulness held at roughly 0.89–0.93. Answer relevancy sat at about 0.51, with roughly half the
rows flagged low. Reading those rows one at a time, most of the low answer-relevancy scores were
*not* wrong answers — the metric was reacting to phrasing and structure. They split into the
categories below.

### Findings — Faithfulness / Relevancy Failure Categories

<!-- Mirror the failure-category structure from retrieval_experiments.md once patterns emerge, e.g.: -->

#### 1. Browse-intent rows scored with a QA-shaped metric (eval bug, fixed 2026-08-24)

- Example: "how do I feel in loud crowded places" (`qa`) — 0.916, vs "show me notes about feeling overwhelmed" (`browse`, identical source note) — 0.293.
- Cause: `runner.py` ran every `ask`-target row through `generate()` + `answer_relevancy` regardless of gold intent, even though production (`src/rag/pipeline.py`) never sends `browse` queries to the generator at all — it returns raw notes, `answer=None`.
- RAGAS's `AnswerRelevancy` reverse-generates questions from the answer and embeds them against the query; a narrative answer compared to an imperative "show me..." query mismatches in phrasing regardless of content correctness.
- **Fixed** — `runner.py` now skips generation for `gen_plan.intent == "browse"`. Confirmed by the 2026-08-28 rerun: row count dropped 56→34, and the extreme same-note gaps are gone.

#### 2. Verdict-last, evidence-first answer structure (`pattern` intent)

- Example: "is there a pattern in how I feel on Sundays" — faithfulness 1.0, context scores 1.0, answer_relevancy 0.424. Answer is a chronological, per-date breakdown with the actual verdict only in the closing sentence.
- Contrast: "what do I usually feel before the week starts" (0.711) and "how do I feel late at night when I can't sleep" (0.809) both open by directly answering, in language that echoes the query itself, before adding supporting detail.
- Hypothesis: RAGAS's reverse-question generation skews toward the answer's dominant content (itemized evidence) rather than a verdict buried at the end, lowering similarity to a query asking for the verdict.
- **Caveat from the 2026-08-28 rerun:** not a clean rule — "have I kept the streak going this week" opens with a direct "Yes, you have kept the streak going..." (verdict-first) and still scored 0.465. Structure alone doesn't fully explain the gap; see category 5.

#### 3. Query vocabulary abstracts over the note's concrete language

- Example: "what did I say I needed to handle before the deadline?" — faithfulness 1.0, answer_relevancy 0.238 (reproduced 2026-08-28, unchanged). Also "what deadline did I write down" — 0.462 → 0.399 across the two runs.
- The word "deadline" never appears in the source note or the (faithful) answer — the note uses concrete phrasing ("by Friday", "before it renews next week") instead.
- Reverse-generated questions likely mirror the answer's concrete vocabulary, not the query's abstract framing word, lowering embedding similarity independent of correctness.

#### 4. Noncommittal penalty over-triggers on honest hedges *and* genuinely mixed/ambivalent answers

- Example A: "have my mornings been better or worse lately" — answer_relevancy 0.000 (flat, both runs). Faithfulness 0.667→0.6 (context is a single note; a trend question can't really be answered from one data point, and the answer honestly says so).
- Example B (new, 2026-08-28): "how did the change to my routine go" and "what did I expect versus what actually happened after I changed my schedule" — both scored a flat 0.000 despite faithfulness 1.0 and context scores 1.0. Neither answer is vague or evasive — both substantively describe a "mixed bag" outcome, which is what the source note itself says verbatim.
- This broadens the finding beyond "insufficient data" hedges (Example A) to "the honest answer is genuinely mixed/ambivalent" (Example B) — a much more common shape for personal notes/journaling than clean yes/no outcomes, and one RAGAS's noncommittal classifier appears to zero out just as aggressively.
- Example A's single-note context is deliberate, not a dataset gap — it's a purpose-built test of whether the model will correctly say "I can't tell from this" rather than fabricate a trend it has no evidence for. The model passed: it hedged honestly. The metric failed to recognize that as correct, scoring it identically to an evasive non-answer. That gap between "correct calibrated uncertainty" and "the metric's noncommittal penalty" is exactly what the *Calibration* dimension in the planned custom judge (Next Steps) needs to fix.
- This is the one category here that is a **real metric gap** rather than a phrasing artifact.

#### 5. (New, 2026-08-28) "In your note from [date], you..." preamble correlates with low scores

- Nearly every low-scoring row in the 2026-08-28 rerun opens with a date/citation preamble before the actual answer: "In your note from 2026-08-07, you mentioned...", "In your note from [1], the renewal deadline is...", "In your note from 2026-07-23, you reflected...".
- The consistently high-scoring rows from the 2026-08-24 run instead open by restating the query's own terms directly: "In loud, crowded places, you feel overstimulated..." (0.916), "Late at night when you can't sleep, you feel very tired..." (0.809).
- **Hypothesis, not yet verified**: the date-preamble phrasing shifts what the judge reverse-generates ("What did you note on [date]?") away from the query's own framing. If true, this is a generation-prompt lever, not just a metric-design problem — cheap to test before investing in a new metric (see Next Steps).
- Reliability caveat also observed here: "what did I say about how my days are shaped" scored faithfulness 1.0 in the 2026-08-24 run and 0.571 in the 2026-08-28 rerun, same query and gold context. **Resolved by comparing the two actual answers, not just the scores:** the generated text itself differed between runs — the 08-28 answer added "shaped by **a pattern**" and "**memorable**," neither supported by the note, which describes a single day, not a recurring pattern. So this specific swing is generator sampling variance interacting with a thin/vague source note (room to over-infer), not judge inconsistency scoring identical text differently. Treat single-row readings cautiously either way — but the mechanism here is a generation-quality issue, not just eval noise. See the parked analysis below.

#### 6. Eval context missing note metadata — false negative faithfulness verdicts (bug, fixed 2026-08-12)

This is Experiment 1's bug, written up in full there. The number is kept so the category
references in `decisions.md` and in the Overview table still resolve. Nothing new surfaced for it
in the dataset2 runs — by 08-24 the `format_note()` fix was already in place.

#### 7. Real faithfulness failures (not eval artifacts)

Categories 1 and 6 were eval bugs. These are the generator actually producing unsupported claims.

**7a. Helpful-but-ungrounded suggestions.** Query "what helps with anxiety" — notes describe anxiety
but none prescribe coping strategies. The answer summarizes the notes faithfully, then appends a
suggestion of its own. Faithfulness scores it down, correctly: the suggestion is not in context.
This is a helpfulness ↔ faithfulness tension and a *product* decision, not a metric bug — "dump and
mirror" implies Ask reflects notes back rather than advising. If mirror-only is the intent, this is
a generation-prompt fix (forbid recommendations absent from context).

**7b. Metadata role confusion — `created_at` rendered as "due date".** Full-pipeline run (see
Experiment 3), query "show me anything with a due date" — faithfulness 0.000. The answer invents
absolute dates ("August 7, 12, 15, 17, 18") and items ("Follow up on the project", "check in with
the team"). The dates trace to each note's `created_at`, relabeled as a due date. Two stacked
problems: (1) a `browse`-intent query reached the generator at all — the `runner.py` skip
(Category 1) was verified only on the gold-context run, not this full-pipeline path; confirm
coverage and that this row's gold intent is labeled `browse`. (2) Independently of (1), the
generator misreads the role of `created_at` in its formatted context. A perfect browse-skip hides
this bug; it does not fix it.

#### 8. The answer value lives only in metadata, not note text

Query "when did I start doing the habit this week?" (gold context, single note). Note text: "today I
actually did the habit for the first time this week" — no date string. Answer: "In your note from
2026-08-16, you mentioned...". Scores: context_relevance 0.500, faithfulness 0.500,
answer_relevancy 0.244, context_utilization 1.000.

The "when" is answerable only from `created_at`. The sub-metrics disagree on whether that counts:
- **context_relevance 0.5** — judged against note *text*, which only half-answers "when" ("this
  week", no date).
- **faithfulness 0.5** — the "first time this week" claim is grounded (verdict 1); the date claim
  ("note from 2026-08-16") fails (verdict 0) — that sub-judge's context for this row is text-only.
- **answer_relevancy 0.244** — Category 5 preamble; reverse-question drifts to "what's in the
  08-16 note?" instead of "when did I start?".

The answer is likely *factually correct* (08-16 = `created_at`), just unverifiable from text and
phrased for a low score. Two levers: (a) if metadata answers are legitimate, ensure every
sub-metric's context includes formatted metadata, not just faithfulness; (b) generation prompt —
answer "when" directly ("You started this week's habit on Saturday, 2026-08-16") rather than the
"In your note from [date]…" frame.

### Experiment 2 verdict

On gold context, faithfulness is sound at roughly 0.89–0.93; the few real misses are catalogued in
Categories 7 and 8. Answer relevancy at about 0.51 is mostly a **metric-fit** problem rather than an
answer-quality problem — Categories 2, 3 and 5 are all cases where the answer was correct and the
metric was measuring phrasing. Category 4 is the exception: a genuine gap, where honest hedges and
mixed verdicts get zeroed regardless of correctness.

No decision made here. The blocked next step is the custom rubric judge (see Next Steps); the
generator-prompt ideas for Category 5's over-inference are in the Parked section.

---

## Experiment 3 — Full pipeline vs generation-only (2026-08-24 / 08-27)

**Motivation:** everything in Experiment 2 held retrieval constant by using gold context. The open
question is whether putting real retrieval in front of the generator changes the generation-quality
picture — and if it does, which metric moves.

**Setup:** `runner.py` with stages `[intent, retrieval, generation]` — live analyzer plus real
vector retrieval feeding the generator. Two configs: bge-large n10 (2026-08-24, 56 rows) and
openai-3-small n15 (2026-08-27, 34 rows), each compared against the matching gold-context run from
Experiment 2.

| Run | rows | context_rel | context_util | faithfulness | answer_rel |
|---|---|---|---|---|---|
| gen-only (gold) 08-24 | 56 | 0.790 | 1.000 | 0.933 | 0.510 |
| full-pipe bge-large n10, 08-24 | 56 | 0.812 | **0.733** (13 low) | 0.941 | 0.600 |
| gen-only (gold) 08-28 | 34 | 0.882 | 1.000 | 0.892 | 0.515 |
| full-pipe openai-3-small n15, 08-27 | 34 | 0.860 | **0.885** (1 low) | 0.944 | 0.557 |

**Findings:**

1. **Faithfulness barely moved.** It held or rose slightly with real retrieval (0.933 → 0.941, and
   0.892 → 0.944). The generation stage stays faithful regardless of where the context came from.
   The one exception the mean hides is Category 7b's faithfulness-0.000 row (`created_at` read as a
   due date) — a `browse` row that reached the generator on the full-pipeline path, where the
   browse-skip had not yet been verified.
2. **Answer relevancy also held or rose slightly** full-pipeline (0.510 → 0.600, and
   0.515 → 0.557). So the answer-relevancy weakness is intrinsic to generation plus the metric —
   it is *not* caused by retrieval, and it is if anything worse under perfect gold context. That
   backs Experiment 2's reading: the fix is a better judge, not better retrieval.
3. **The one metric that dropped is `context_utilization`** — 1.000 under gold context (by
   construction) down to 0.733–0.885 full-pipeline. Real retrieval pulls in notes the generator
   doesn't use. The size of the drop is config-dependent: bge-large n10 fell to 0.733 (13 low
   rows), openai-3-small n15 only to 0.885 (1 low row).

**Caveats:** this is not a perfectly controlled comparison — the runs are on different dates, the
56-row full-pipeline run still contains `browse` rows, and the two full-pipeline runs use different
retrievers, so config effect and pipeline effect are partly entangled.

**Experiment 3 verdict:** generation is robust to where its context comes from. Faithfulness and
answer relevancy do not degrade when real retrieval replaces gold context, so the Experiment 2
findings stand on their own. The remaining end-to-end headroom is in **retrieval**, and it surfaces
as `context_utilization`, not as faithfulness — attributing it to ranking/MRR needs the
retrieval-stage report ([retrieval_experiments.md](retrieval_experiments.md)), not this one.

**Revisit triggers:**
- Confirm the `browse`-skip covers the full-pipeline path, not just gold-context runs (Finding 1's
  exception). Blocks trusting any full-pipeline faithfulness number.
- Re-run with matched retrievers and `browse` rows excluded on both sides before treating the
  "+0.09 answer relevancy under real retrieval" as anything more than noise.

---

## Reading the Scores Together (the triangle, from eval-ask-grader.md)

| Pattern | Diagnosis |
|---|---|
| high faithfulness + low context precision | Grounded in the wrong notes — honest answer, failed retrieval. Not a generation problem. |
| low faithfulness + high answer relevancy | Model answering from its own knowledge, ignoring the notes. |
| high faithfulness + high context precision + low answer relevancy | Retrieved and grounded fine, but dodged the question. |

<!-- Log which pattern each weak question actually falls into as you assess — this is what turns raw scores into a findings list. -->

**Refinement from the 2026-08-24/28 pass:** the third row's "dodged the question" diagnosis doesn't hold for most of our high-faithfulness/high-context/low-relevancy rows — none of them dodged anything. They split into distinct sub-patterns instead, which the generic triangle collapses into one bucket:
- Answered correctly, but buried the verdict in evidence (Category 2)
- Answered correctly, but in vocabulary that doesn't echo the query's framing (Category 3)
- Answered correctly *and* honestly — including correctly hedging when the evidence didn't support a firm verdict — but RAGAS zeroes honest hedges/mixed verdicts regardless of correctness (Category 4)
- Answered correctly, but opened with a date/citation preamble instead of the query's own terms (Category 5, hypothesis — unverified, see Next Steps)

None of these are "grounded fine but dodged the question" — they're all cases where `answer_relevancy` measures phrasing/structure, not whether the question was actually addressed. Worth updating the triangle's third row to point to these sub-categories instead of "dodged."

---

## Next Steps

<!-- Concrete follow-ups once a findings list exists — prompt customization, hand-rolling a metric, re-running after a fix, etc. -->

- [x] Fix `runner.py` to skip generation for `browse`-intent rows (Category 1) — done 2026-08-24, verified by the 2026-08-28 rerun.
- [ ] **Surface RAGAS's `AnswerRelevancy` intermediate output** — same technique already used for faithfulness (`FaithfulnessWithDecomposition`, 2026-08-12 decision): capture the N reverse-generated questions + per-question similarity, not just the final score, for the Category 2/3/5 rows. Turns the vocabulary/preamble/verdict-placement ideas from speculation into evidence, and tells us whether the fix belongs in `AnswerRelevancy`'s own question-generation prompt (customizable, same family as the faithfulness judge-prompt work) or needs a separate custom judge.
- [ ] **Design a G-Eval-style custom rubric judge**, informed by the above, especially for `pattern`/trend-intent rows. Score two separate dimensions instead of one embedding-similarity number:
  - *Engagement*: does the answer address what was actually asked, regardless of phrasing/structure?
  - *Calibration*: does the answer's confidence/stance match what the context can actually support — explicitly rewarding "insufficient data" or "mixed" verdicts when the context is genuinely ambiguous or thin (Category 4's deliberate test case), instead of zeroing them.
  - Real design work (rubric definition, few-shot examples, validation against these categorized rows) — spec it as its own task.
- [x] Run-to-run score stability (Category 5's reliability caveat) — resolved by direct comparison, not speculation: the "what did I say about how my days are shaped" swing traced to genuinely different generated text (one run added an unsupported "pattern"/"memorable" claim), not judge inconsistency. Confirms generation, not just eval, needs attention for thin/vague source notes.
- [ ] **Confirm the `browse`-skip covers the full-pipeline path**, not just gold-context generation runs (Category 7b / Experiment 3). Cheap check; blocks trusting any full-pipeline faithfulness number.
- [ ] **Decide the mirror-vs-advise product stance** for Category 7a, then align the generation prompt. Blocks distinguishing "real unfaithfulness" from "intended helpfulness" in every future run.
- [ ] **Statement Decomposition Round 2** — a larger sample than Round 1's 3 answered questions, to close (or not) the aggregation-judgment hypothesis.
- [ ] **Re-run Experiment 3 with matched retrievers** and `browse` rows excluded on both sides, before treating the full-pipeline answer-relevancy gain as real.

---

## Parked: Generator Improvement Options (analysis session, not yet scoped)

<!-- Brainstormed 2026-08-28 in response to the "days are shaped by a pattern" overclaim (Category 5 reliability caveat) — a single-day note, and the generator inferred recurrence on one run but not another. Not decided or spec'd — pick this up as its own session before building anything. -->

**Problem statement:** thin/vague source notes give the generator room to make an inferential leap (e.g. one day → "a pattern") that faithfulness sometimes catches and sometimes doesn't, depending on sampling variance. Four candidate directions, roughly cheapest-to-try → most robust:

1. **Explicit epistemic-scope instruction in the generation prompt** — tell the generator not to generalize to "a pattern"/"usually"/"you tend to" from a single-note context; few-shot a "one note → no pattern claim" vs "multiple dated notes → pattern claim OK" pair. Same technique that already fixed the melodramatic note-generation register (2026-08-21 decision log entry).
2. **Lower generation temperature** — cheapest to test; reduces the sampling variance that let "days are shaped by a pattern" happen on one run and not the other. Doesn't teach the model *why* it overclaimed, just makes the roll less likely.
3. **Self-check pass after generation** — a second cheap LLM call: "does every claim trace back to context? Rewrite what doesn't." Moves faithfulness-checking into the live pipeline, not just eval. More cost/latency per real query.
4. **Extract-then-compose** — pull explicit facts from the note(s) first, then compose the answer constrained to that fact list, instead of freeform synthesis directly off raw note text. Most invasive change to the generation pipeline.

**Next when picked up:** decide which 1–2 to actually try, spec per the usual threshold (>3 decisions → write it up), and validate against the specific rows already flagged in Category 4/5 above rather than the whole eval set blind.

---

## Product Feature Implications

<!-- Same shape as retrieval_experiments.md's table — only fill in once a finding clearly points at a product fix. -->

| Finding | Feature | Status |
|---|---|---|
| Helpful-but-ungrounded suggestions (Category 7a) | Generation prompt: mirror-only — forbid recommendations absent from context | Product decision pending |
| `created_at` misread as "due date" (Category 7b) | Generation prompt: label metadata roles explicitly; verify `browse`-skip on the full-pipeline path | Open |
| "when"-type answers live only in metadata (Category 8) | Generation prompt: answer "when" directly from `created_at` ("You started this week's habit on Saturday, 2026-08-16") rather than "In your note from [date]…" | Open |
| Date-preamble phrasing correlates with low answer-relevancy (Category 5) | Generation prompt: open by restating the query's terms, not a citation preamble | Hypothesis — test before building |
| Honest hedges / mixed verdicts zeroed by RAGAS (Category 4) | Custom rubric judge with an explicit Calibration dimension | Spec'd as own task |
