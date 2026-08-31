# Retrieval Experiments: Findings & Decisions

> **All notes and queries quoted in this doc are synthetic test data**, generated for
> evaluation — none are real personal notes.

## Overview

This doc covers the **retrieval stage** — which notes come back for a query. It started life as
"search experiments" when only the Search page existed; the Ask pipeline now shares the same
retrieval stage, so the scope is retrieval, singular. Generation findings live in
[generation_experiments.md](generation_experiments.md); dataset2 methodology in
[dataset2_experiments.md](dataset2_experiments.md).

Two eval datasets appear below:

- **dataset1** — 35 synthetic personal notes, 152 queries (141 exact, 11 ambiguous; eval set
  `e88128e3`). Queries were written by *predicting* what a user might search — a choice that
  turned out to matter (see failure category 5). Originally 162 queries; cleaned 2026-07-22
  (162 → 156), later trimmed further to the current 152.
- **dataset2** — 30 notes, 116 queries modeled on real logged usage (`ask_log`), with multi-note
  ground truth and intent/filter labels. Built 2026-08-21 specifically to fix dataset1's
  weaknesses — see [dataset2_experiments.md](dataset2_experiments.md).

---

## Experiment 1 — Embedding comparison (dataset1)

First two runs, on the pre-cleanup eval set:

| Run | Model | Rank@1 | Not Found | Avg MRR* |
|---|---|---|---|---|
| 60052450 | all-MiniLM-L6-v2 (default) | 61% (96) | 15% (24) | 0.698 |
| 41be62cc | bge-large-en-v1.5 | 72% (113) | 11% (18) | 0.783 |

*Originally reported as "precision" — the metric was always MRR and was later renamed in the grader.

bge-large improved 35 queries, regressed on 15. Net: +20 queries, MRR +0.085.

**bge-large clearly better at:** handling of polarity and emotional directionality.

**bge-large regresses on:**
- Abstract/metaphorical: `"project mirrors personal life"` #1→#4, `"why am I building this tool for myself"` #2→✗
- Multi-theme conceptual: `"lesson learned about organization"` #1→#4, `"reality gap in personal progress"` #1→✗
- Root cause: bge-large over-indexes on literal semantic match; loses on indirect conceptual connections

**Both models fail on:** temporal queries, bad dataset entries, ambiguous queries, and
retrieve-vs-generate queries — none of which are embedding problems. That realization produced
the failure taxonomy below, which ended up being the more important output of this experiment.

---

## Failure Categories — and what each one drove

Reading every miss individually (not just the aggregate score) split the failures into five
categories. Only one of them is a model problem. Each category is annotated with what was
done about it.

### 1. Dataset Quality Issues

These are problems in the eval set itself, not the model.

**Wrong topic mapping** — query has no real relationship to the expected note:
- `"devops continuous delivery"` → expected: knowledge graphs note (`v_learning_001`)
- `"what is pipeline orchestration"` → expected: knowledge graphs note (`v_learning_001`)
- The note is about tree-based data retrieval structures, not DevOps.

**Expected note is wrong — retrieved note is actually better:**
- `"location of laptop at home"` and `"where did I put my charger"` → expected: `t_ref_003` (keys/wallet in kitchen drawer)
- Retrieved `v_ref_001` ("Charger by the big book on the shelf above the fireplace") is the correct answer for the charger query.

**Query vocabulary doesn't match note vocabulary + temporal mismatch:**
- `"when I was anxious about meeting at work friday"` → expected: `v_mood_001` ("anxious bout that call with Alex")
- The note says "call" not "meeting", says "today" not "friday". The model correctly retrieves
  the note that actually contains "meeting" and "Alex". Not a model failure; the query is
  misleading and requires date metadata to resolve "friday".

**→ What we did:** fixed the obvious errors immediately (2026-07-22 cleanup: 6 queries removed,
2 fixed, 162 → 156) — and, longer-term, built dataset2 grounded in real usage instead of
predicted queries, so quality issues like these can't silently accumulate again.

### 2. Ambiguous Queries — Multiple Valid Answers

The eval framework assumed one correct note per query. These queries have at least two valid
answers in the dataset — every miss here is partly an eval design flaw, not a model failure.
Examples: `small win I want to remember`, `good conversation`, `low energy day`,
`task I was avoiding`.

**→ What we did:** tagged them `"ambiguous": true` (no hand-maintained `also_valid` lists —
doesn't scale), excluded them from exact metrics (Rank@1/MRR), and score them separately with
**LLM-as-judge** reference-free relevance ("is this retrieved note relevant to this query?") in
`grader.py`. dataset2 goes further: multi-note `expected_note_ids` makes "several notes are all
correct" representable *ground truth* instead of an exception.

### 3. Temporal & Metadata Queries — Feature Gap, Not Model Gap

No embedding model will solve these. They fail because they reference time, date, or note type —
none of which are in the semantic embedding. Examples:

| Query | What's missing |
|---|---|
| `how I feel at the end of today` | date filter (today) |
| `day reflection voice note` | content_type filter (voice) |
| `intention for tomorrow` | date filter (relative: tomorrow) |
| `what I did and didn't do this week` | date range filter (this week) |

**→ What we did:** treated it as a product feature, not a retrieval experiment: the Search page
got date/type filters, and the Ask pipeline's analyzer extracts time/category filters from the
query before retrieval. dataset2 carries `expected_time_filter` / `expected_category_filter`
ground truth so the analyzer can be graded as its own stage.

### 4. Retrieval vs Generation — Wrong Tool for the Job

Some queries aren't "find me a note" requests — they're questions that need an answer
synthesized from multiple notes. Pure retrieval will always underperform on these:
- `"How do I learn best?"` → should synthesize from several insight/learning notes
- `"why no motivation?"` → should aggregate mood notes and surface a pattern

The "lesson learned about organization" case also showed **embedding dilution**: a long
multi-topic note's embedding is spread across all its topics, so a single topic's signal is too
weak to win over a note entirely about that topic. (This observation later spawned the
[chunking experiments](chunking_experiments.md).)

**→ What we did:** built the Ask pipeline — intent detection decides whether the user is
retrieving a specific note or asking a question to be answered from their notes. dataset2 labels
every query with `target_system` (search vs ask) and `intent` so this routing is gradeable.

### 5. Unrealistic Queries

`"Lunch packing for tomorrow"` — not how a user would actually search. **Key insight: we don't
know what queries real users actually use.** The eval dataset was written by predicting queries,
not observing them.

**→ What we did:** started logging real queries (`ask_log`), and generated dataset2's queries
from the patterns in that log — e.g. real users almost never imply a category filter (0/28
logged queries), so dataset2 barely probes it, instead of inventing query styles that never occur.

**Experiment 1 verdict:** bge-large wins on this eval — but the eval itself was the bigger
finding. Before trusting further experiments, the measurement needed fixing: cleanup first,
dataset2 eventually.

---

## Experiment 2 — Reranking, first pass (2026-08, older 155-query eval set)

A cross-encoder reranker (`cross-encoder/ms-marco-MiniLM-L-6-v2`, later also
`BAAI/bge-reranker-base`) was added on top of both embeddings: retrieve top-15 with the
bi-encoder, rescore each (query, note) pair, reorder.

| Config | Avg MRR | with ms-marco | with bge-reranker-base |
|---|---|---|---|
| default (MiniLM) | 0.763 | 0.821 | 0.821 |
| bge-large | 0.865 | 0.834 | 0.828 |

The pattern was already visible — **both rerankers help the weak retriever and hurt the strong
one** — but the result read as "weird" at the time (a reranker *lowering* MRR looked like a
possible grading bug), so the conclusion was deferred rather than trusted. Resolved in
Experiment 3 with repeat runs and a wider sweep.

---

## Experiment 3 — Consolidated sweep: OpenAI embeddings, rerankers, both datasets (2026-08-26/27)

### Motivation: deployment

bge-large runs locally — fine on a laptop, a liability for deployment (large model download,
RAM, cold start). That constraint motivated testing hosted embeddings: OpenAI
`text-embedding-3-small` / `-large`.

### Embeddings: OpenAI wins outright

dataset1 (eval `e88128e3`): openai-3-small reaches **MRR 0.911** at n=10 — beating bge-large at
n=15 (0.863) with a smaller candidate pool. dataset2 confirms the ordering:

| Embedding | dataset1 MRR (exact) | dataset2 MRR |
|---|---|---|
| default (MiniLM) | 0.763 | 0.577 |
| bge-large | 0.863 | 0.697 |
| openai-3-small | **0.911** | **0.786** (recall 1.0) |
| openai-3-large | — | 0.83 (n10) |

**Retrieval depth matters for recall:** on dataset1, bge-large recall goes 0.927 → 0.986 from
n=5 → n=15; on dataset2, 0.948 → 0.957 from n=10 → n=15. Since the Ask pipeline's generation
stage consumes the whole candidate list, deeper retrieval is cheap recall — the candidate count
was raised accordingly.

### Rerankers: the full grid (dataset1, eval `e88128e3`)

Setup: bi-encoder retrieves top-n (n=15 bge-large, n=10 openai-3-small), reranker rescores and
reorders. Recall is identical in every configuration (0.986) **by construction** — a reranker
only reorders the candidates the retriever already fetched; it can never add or remove one.
Reranking is purely a bet on better ordering, so MRR is the metric that can move.

| Retriever | Reranker | MRR (exact) | LLM-judge (ambiguous, n=11) |
|---|---|---|---|
| bge-large (n15) | — | **0.863** | 0.76 |
| bge-large (n15) | ms-marco-MiniLM | 0.844 | 0.85 |
| bge-large (n15) | bge-reranker-base | 0.839 | 0.79 |
| bge-large (n15) | bge-reranker-v2-m3 | **0.887** | 0.85 |
| openai-3-small (n10) | — | **0.911** | 0.85 |
| openai-3-small (n10) | ms-marco-MiniLM | 0.851 | 0.82 |
| openai-3-small (n10) | bge-reranker-base | 0.850 | 0.79 |
| openai-3-small (n10) | bge-reranker-v2-m3 | 0.892 | 0.88 |

(The ambiguous-judge column is 11 queries — directional at best; don't read precision into ±0.05.)

**Experiment 2's "weird" result was real.** The full bge-large sweep was re-run twice on
2026-08-27; both passes produced identical recall/MRR for every configuration (the LLM-judge
column varies slightly run-to-run, as LLM scoring does). Reproducible, not a grading bug.

### Finding: reranking benefit is conditional on retriever strength

Putting Experiments 2 and 3 together gives a monotonic gradient — the same reranker, the same
dataset, opposite effects depending on how strong the retriever already is:

| Retriever strength | baseline MRR | effect of ms-marco rerank |
|---|---|---|
| MiniLM default (weak) | 0.763 | **+0.058** ✓ helps |
| bge-large (strong) | 0.863 | −0.019 ✗ hurts |
| openai-3-small (strongest) | 0.911 | −0.060 ✗ hurts most |

Why:

1. **Training-domain mismatch.** ms-marco-MiniLM and bge-reranker-base are trained predominantly
   on MS MARCO — factoid web-search queries against web passages. Our queries are first-person,
   vague, and emotional ("small win I want to remember"); out of distribution, cross-encoders
   fall back toward literal lexical overlap — the same failure mode bge-large itself showed in
   Experiment 1. bge-reranker-v2-m3 (bge-m3 lineage, much broader training data) degrades least
   and is the only reranker that ever helps. The ordering base ≈ ms-marco < v2-m3 tracks
   training-data breadth.
2. **A strong retriever leaves no room to win.** With recall at 0.986–1.0, the expected note is
   already at rank 1 for most queries. A reranker can only gain on the few misordered queries but
   can lose on every query where it demotes a correct #1 — out-of-domain, it does that often
   enough to go net negative. This matches the published pattern: reranking gains are largest
   over weak retrievers and large candidate pools, and shrink toward zero (or below) as the
   retriever strengthens.
3. **Nuance: exact rank vs general relevance.** On bge-large, rerankers hurt exact rank but
   *improved* the ambiguous LLM-judge score (0.76 → 0.85). The reranker's relevance judgment
   isn't useless — it's worse than the bi-encoder at picking the *one* expected note while still
   decent at pulling *generally relevant* notes into the top ranks.

### Does this hold on the realistic dataset? (dataset2 replication)

Every reranker configuration was replicated on dataset2 (116 realistic queries, multi-note
ground truth):

| Retriever | baseline MRR | + bge-base | + v2-m3 | + ms-marco |
|---|---|---|---|---|
| default (MiniLM) | 0.577 | **0.662** ✓ | — | — |
| bge-large (n15) | 0.697 | 0.670 ✗ | **0.729** ✓ | — |
| openai-3-small | 0.786 (n15) | 0.687 ✗ (n10) | 0.750 ✗ (n15) | 0.683 ✗ (n10) |

Same qualitative story in every cell: rerankers rescue the weak retriever, v2-m3 gives bge-large
a modest bump, everything hurts on OpenAI — where recall is a flat 1.0, so there was nothing
left to rescue.

Two dataset-level observations fall out of the replication:

1. **Absolute scores drop hard on dataset2** (openai 0.911 → 0.786, bge-large 0.863 → 0.697).
   dataset1's predicted queries shared vocabulary with the notes they targeted, inflating
   scores; realistic queries are simply harder.
2. **But every relative ranking transferred** — embedding order, reranker effects, the strength
   gradient. A flawed benchmark inflated our absolute numbers yet still ranked systems
   correctly, so the decisions made on it survived the better benchmark.

### Decision

**Production config: openai-3-small, no reranker.** On the production embedding, every reranker
tested reduces MRR while adding latency and a locally-hosted model — negative measured benefit
at positive cost.

Revisit triggers, not a permanent verdict:
- **Corpus growth** — these datasets are 30–35 notes. If recall@k degrades as the real note
  count grows into the hundreds, the candidate set gets noisier and the trade-off can flip.
- **Hybrid retrieval** — if keyword/BM25 search is added alongside vector search, the two
  retrievers produce incomparable scores and something must fuse the merged candidate list;
  a cross-encoder is a standard choice for that fusion step.

Takeaway: **reranking is not a free upgrade — it's a bet that the reranker's training
distribution matches your domain.** Here it didn't.

---

## Analyzer Stage — Intent & Filter Extraction: Status and Known Limitations

The Ask pipeline's analyzer (`src/rag/analyzer.py`) runs *before* retrieval: it classifies the
query's intent (`browse`/`qa`/`factual`/`pattern`) and extracts time/category filters that narrow
the vector search — so its mistakes surface downstream as retrieval failures. dataset2 carries
ground truth for all three fields, so the stage is graded on its own (`stages: [intent]`).
Latest pass (56 ask rows, 2026-08-24): **intent accuracy 0.821, time_filter 0.946,
category_filter 0.929.**

Known limitations — documented deliberately rather than fixed now:

- **The `factual`/`qa` boundary is fuzzy — in the labels and in the classifier.** 6 of the 10
  intent misses are `factual → qa`. The labeling pass showed several rows are defensible either
  way, and the classifier itself flips on exactly this boundary between identical runs
  (accuracy 0.821 vs 0.857 back-to-back — single-run numbers aren't trustworthy for this stage;
  average N runs). Whether `factual` should exist as a separate intent at all is
  an open question, **to be settled from real usage** — checking which of the two code paths
  actually produces better answers for these queries — not from more synthetic relabeling.
  See `decisions.md` (2026-08-24).
- **Time-filter over-extraction.** The analyzer sometimes reads habitual phrasing as a time
  window — e.g. `"what do I usually feel before the week starts"` → `this_week`, which then
  narrows retrieval *away from* the older notes a pattern question needs. One prompt-tuning
  attempt didn't move it much. Plan: watch real usage (`ask_log`); if it causes real misses,
  loosen the filter's effect (soft boost rather than hard cutoff) before spending more on
  prompt work.
- **Category "misses" that are arguably correct extractions.** Most category_filter mismatches
  are the analyzer extracting a category the ground truth leaves null (`"show me the tasks I've
  completed"` → `task`). The ground truth follows real logged usage — users almost never imply a
  category — but the extraction itself is reasonable. An eval-labeling judgment call, not a
  clear defect.

---

## Product Feature Implications

| Finding | Feature | Status |
|---|---|---|
| Temporal queries always fail on embeddings alone | Date range filter on search; time-filter extraction in Ask analyzer | Shipped |
| "voice note" filter queries | Filter by input type (voice/text/image) | Shipped |
| Unrealistic eval queries | Log all real queries (`ask_log`) — ground truth for future evals | Shipped; fed dataset2 |
| Retrieve vs generate distinction | Intent detection: show notes vs answer question (Ask pipeline) | Shipped |
| Long notes dilute key signals | Chunking: index segments separately | Explored ([chunking_experiments.md](chunking_experiments.md)), parked — no current need |
