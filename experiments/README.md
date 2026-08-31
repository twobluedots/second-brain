# Experiments

> **All notes and queries quoted in these docs are synthetic test data** — none are real
> personal notes.

The evaluation side of the project: datasets, harnesses, and findings for the retrieval + RAG
pipeline behind Search and Ask.

The short version: **the evaluation shaped the system as much as it scored it.** Reading the
misses showed where off-the-shelf parts — embedding models, rerankers, RAGAS metrics — carry
training-data assumptions that don't fit a first-person memory app, what metadata the pipeline
had to expose to be gradable, and which failures were missing product features rather than model
weakness. Date filters, query logging, and stage-by-stage attribution all came out of it.

## The story

1. **Eval first.** dataset1: 35 synthetic notes, 152 queries with expected results — written by
   *predicting* what a user would search. That authoring choice became finding 3.

2. **Embeddings.** bge-large beat the MiniLM default (MRR 0.698 → 0.783): clearly better on
   polarity and emotional directionality, worse on abstract/metaphorical queries.
   → [retrieval_experiments.md](docs/retrieval_experiments.md), Experiment 1

3. **Reading the misses fixed the eval, not the model.** Failed queries split into five
   categories — only one was a model problem. The rest: eval bugs, queries with multiple valid
   answers, missing product features (temporal queries need date filters, not better
   embeddings), and unrealistic predicted queries. Each drove a fix — cleanup, LLM-as-judge for
   ambiguous queries, filters + the Ask pipeline in the product, query logging — and eventually
   dataset2, generated from real logged usage.
   → [retrieval_experiments.md](docs/retrieval_experiments.md), Failure Categories

4. **Reranking is not a free upgrade.** A reranker *lowering* MRR looked like a grading bug,
   so it was re-run before being believed — twice, identically. The full sweep (3 rerankers ×
   3 retrievers × 2 datasets): rerankers rescue a weak retriever (+0.06–0.09) and hurt every
   strong one. MS-MARCO-trained relevance doesn't transfer to this domain.
   → [retrieval_experiments.md](docs/retrieval_experiments.md), Experiments 2–3

5. **Deployment changed the answer.** Local bge-large was a deploy liability; hosted
   openai-3-small then beat it outright (MRR 0.911 vs 0.863 on dataset1, 0.786 vs 0.697 on
   dataset2), and deeper retrieval (n=10→15) was the cheap recall lever. **Production config:
   openai-3-small, n=15, no reranker** — logged with revisit triggers (corpus growth, hybrid
   retrieval), not as a permanent verdict.
   → [retrieval_experiments.md](docs/retrieval_experiments.md), Experiment 3 + Decision

6. **Stage attribution.** A bad answer could be retrieval, intent classification, or generation
   failing — one end-to-end score can't say which. dataset2 (116 queries modeled on real usage)
   plus a stage-selectable runner grade each stage alone, including generation against *gold*
   context. Realistic queries dropped every absolute score, but every relative ranking
   transferred — decisions made on the flawed benchmark survived the better one.
   → [dataset2_experiments.md](docs/dataset2_experiments.md)

7. **Audit the judges.** Faithfulness 0.73 on answers that read fine turned out to be an
   eval-harness bug: the judge's context was missing note metadata the real generator saw —
   1.0 after the fix, confirmed at the claim level. Low answer-relevancy was mostly correct
   answers being more *specific* than the vague query — in a memory app, that's what a good
   answer looks like. One real gap remains (honest "mixed evidence" verdicts get zeroed);
   a custom rubric judge is spec'd for post-release.
   → [generation_experiments.md](docs/generation_experiments.md)

8. **Chunking side quest.** All four chunking methods "agreed" — because unpunctuated voice
   transcripts had nothing to split on (1 detected sentence in a 1,353-char note). An LLM
   repunctuation pass fixed the input. Parked: no retrieval problem to solve at this corpus
   size, and recognizing that mid-experiment was the cheaper outcome.
   → [chunking_experiments.md](docs/chunking_experiments.md)

## Map

| Doc | Covers |
|---|---|
| [retrieval_experiments.md](docs/retrieval_experiments.md) | Embeddings, failure taxonomy, reranker sweep, analyzer limitations, production config |
| [generation_experiments.md](docs/generation_experiments.md) | RAGAS runs, the metadata eval bug, metric-fit failure categories, custom-judge plan |
| [dataset2_experiments.md](docs/dataset2_experiments.md) | The realistic eval set and stage-selectable harness |
| [chunking_experiments.md](docs/chunking_experiments.md) | Chunking comparison and the punctuation root cause |
| [docs/decisions.md](docs/decisions.md) | Chronological decision log — what, why, and when to reconsider |

## Infrastructure

`runner.py --config <name.yaml>` runs config-driven experiments with selectable stages
(`intent`, `retrieval`, `generation`); `grader.py` scores recall/MRR, LLM-as-judge, and RAGAS
metrics; `report.py`/`compare.py` produce per-run reports and diffs. All runs land in `runs.db`
plus per-query JSONL records. `ask_eval/` separately runs the real `ask()` pipeline end-to-end.

## Running

From the repo root. OpenAI-backed configs and RAGAS grading need `OPENAI_API_KEY`.

**Config-driven eval** (intent / retrieval / generation) — knobs (`dataset`, `embedding_model`,
`retriever`, `n_results`, `reranker`, `stages`, `generation_metrics`) live in the YAML under
`configs/`, not on the CLI:

    python -m experiments.runner --config dataset2_retrieval_baseline.yaml

Pass several configs to run them in sequence. Each run writes to
`artifacts/results/runs.db` and `artifacts/results/runs/run_<id>.jsonl`.

**Reports and diffs:**

    python experiments/report.py  run_<id> [--all] [--stage retrieval|intent|generation]
    python experiments/compare.py run_<a> run_<b> [--stage ...]

**End-to-end `ask()` pipeline eval:**

    python -m experiments.ask_eval.runner    # collect real ask() runs + grade, one shot
    python -m experiments.ask_eval.grader    # grade the latest cached records — judge calls only, no pipeline calls

**Chunking comparison** (standalone, not wired into `runner.py`):

    python experiments/chunking_experiment.py [--limit N] [--input PATH] [--tag LABEL]
