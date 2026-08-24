"""
Experiment runner — ties pipeline + grader together and logs results.

Outputs per run:
  artifacts/results/runs.db              SQLite — all runs aggregated, queryable
  artifacts/results/runs/run_<id>.jsonl  JSONL  — one file per run, human-readable

Usage:
  python -m experiments.runner --config <name.yaml> [<name2.yaml> ...]

Config files are bare filenames resolved against experiments/configs/. Each
file holds a list of run configs; all configs across all given files run in
sequence.
"""

import argparse
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

import yaml

from experiments.config import CONFIGS_DIR, DATASETS, RESULTS_DIR
from experiments.grader import (
    GENERATION_METRICS,
    build_generation_scorers,
    grade,
    grade_generation,
    grade_intent,
    grade_retrieval_multi,
)
from experiments.pipeline.generation import build_plan, generate as generate_answer, note_to_generator_shape
from experiments.pipeline.index import load_or_build
from experiments.pipeline.intent import analyze
from experiments.pipeline.pipeline import retrieve
from experiments.utils import hash_file
from src.rag.generator import format_note


def init_db(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id              TEXT PRIMARY KEY,
            run_id          TEXT,
            created_at      TEXT,
            dataset         TEXT,
            embedding       TEXT,
            retriever       TEXT,
            n_results       INTEGER,
            query           TEXT,
            expected_id     TEXT,
            retrieved_ids   TEXT,
            recall          REAL,
            mrr             REAL,
            ambiguous       INTEGER,
            llm_judge_score REAL,
            eval_set_hash   TEXT,
            reranker        TEXT
        )
    """)
    # dataset2's multi-stage eval (retrieval / intent / generation, selectable
    # per config). Columns for stages beyond retrieval are added here already
    # (nullable) so later stages don't need another table migration.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS stage_results (
            id                          TEXT PRIMARY KEY,
            run_id                      TEXT,
            created_at                  TEXT,
            dataset                     TEXT,
            embedding                   TEXT,
            retriever                   TEXT,
            n_results                   INTEGER,
            reranker                    TEXT,
            stages                      TEXT,
            query                       TEXT,
            note_id                     TEXT,
            target_system               TEXT,
            expected_note_ids           TEXT,
            retrieved_ids               TEXT,
            recall                      REAL,
            mrr                         REAL,
            expected_intent             TEXT,
            actual_intent               TEXT,
            intent_match                INTEGER,
            expected_time_filter        TEXT,
            actual_time_filter          TEXT,
            time_filter_match           INTEGER,
            expected_category_filter    TEXT,
            actual_category_filter      TEXT,
            category_filter_match       INTEGER,
            generation_context_source   TEXT,
            generated_answer            TEXT,
            context_relevance           REAL,
            context_utilization         REAL,
            faithfulness                REAL,
            answer_relevancy            REAL,
            eval_set_hash               TEXT
        )
    """)
    conn.commit()
    return conn


def build_run_id(config: dict, now: datetime) -> str:
    parts = [config["dataset"]]

    stages = config.get("stages")
    needs_retrieval = stages is None or "retrieval" in stages
    if needs_retrieval:
        parts.append(config.get("embedding_model", "na"))
        parts.append(config.get("retriever", "na"))
        parts.append(f"n{config.get('n_results', 5)}")
        if config.get("reranker"):
            parts.append(config["reranker"])
    if stages:
        parts.append("-".join(stages))
    parts.append(now.strftime("%Y%m%d-%H%M%S"))
    return "_".join(parts)


def load_configs(names: list[str]) -> list[dict]:
    """Load and concatenate run configs from one or more config-set files
    (bare filenames, resolved against experiments/configs/)."""
    configs = []
    for name in names:
        path = CONFIGS_DIR / name
        with open(path) as f:
            file_configs = yaml.safe_load(f)
        configs.extend(file_configs)
    return configs


def run(config: dict):
    now = datetime.now(timezone.utc)
    created_at = now.isoformat()
    run_id = build_run_id(config, now)

    dataset = config["dataset"]
    eval_path = DATASETS[dataset]["eval_set"]
    eval_pairs = [json.loads(line) for line in open(eval_path) if line.strip()]
    eval_set_hash = hash_file(eval_path)

    notes_path = DATASETS[dataset]["notes"]
    notes_by_id = {}
    if notes_path.exists():
        for line in open(notes_path):
            n = json.loads(line)
            notes_by_id[n["id"]] = n
    note_texts = {nid: n["text"] for nid, n in notes_by_id.items()}

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    runs_dir = RESULTS_DIR / "runs"
    runs_dir.mkdir(exist_ok=True)

    db_path = RESULTS_DIR / "runs.db"
    jsonl_path = runs_dir / f"run_{run_id}.jsonl"

    conn = init_db(db_path)

    stages = config.get("stages")
    needs_retrieval = stages is None or "retrieval" in stages
    needs_generation = bool(stages) and "generation" in stages
    collection = load_or_build(config) if needs_retrieval else None
    generation_scorers = build_generation_scorers() if needs_generation else None
    generation_metrics = config.get("generation_metrics", GENERATION_METRICS)

    exact_recalls, exact_mrrs, ambiguous_judge_scores = [], [], []
    multi_recalls, multi_mrrs = [], []
    intent_matches, time_filter_matches, category_filter_matches = [], [], []
    generation_score_lists = {m: [] for m in GENERATION_METRICS}

    reranker_label = config.get("reranker", "none")
    print(
        f"Run {run_id} | {dataset} (eval_set {eval_set_hash}) | "
        f"{config.get('embedding_model', '-')} | {config.get('retriever', '-')} | "
        f"reranker={reranker_label} | stages={stages or 'legacy'}"
    )
    print(f"Evaluating {len(eval_pairs)} queries...\n")

    with open(jsonl_path, "w", buffering=1) as jsonl_f:
        for pair in eval_pairs:
            query = pair["query"]

            if "expected_note_ids" in pair:
                # dataset2-style row: list of equally-valid ground-truth ids
                expected_note_ids = pair["expected_note_ids"]
                target_system = pair.get("target_system")

                if needs_retrieval:
                    retrieved_ids = retrieve(query, config, collection, note_texts)
                    scores = grade_retrieval_multi(retrieved_ids, expected_note_ids)
                    multi_recalls.append(scores["recall"])
                    multi_mrrs.append(scores["mrr"])
                else:
                    retrieved_ids = []
                    scores = {"recall": None, "mrr": None}

                # Intent/filter classification only applies to "ask" rows —
                # analyze_query() is the Ask pipeline's classifier and has no
                # counterpart in the Search page's code path.
                intent_scores = {}
                if stages and "intent" in stages and target_system == "ask":
                    plan = analyze(query, config)
                    intent_scores = grade_intent(
                        plan.intent, plan.time_filter, plan.category_filter,
                        pair.get("intent"), pair.get("expected_time_filter"), pair.get("expected_category_filter"),
                    )
                    intent_scores["actual_intent"] = plan.intent
                    intent_scores["actual_time_filter"] = plan.time_filter
                    intent_scores["actual_category_filter"] = plan.category_filter
                    intent_matches.append(intent_scores["intent_match"])
                    time_filter_matches.append(intent_scores["time_filter_match"])
                    category_filter_matches.append(intent_scores["category_filter_match"])

                # Generation only applies to "ask" rows — need an intent (live
                # from the stage above, or ground truth) to build the QueryPlan
                # the generator conditions its instructions on. Context comes
                # from retrieval if that stage ran, else straight from the
                # gold expected_note_ids — "select pieces or not" composition.
                generation_context_source = None
                generated_answer = None
                generation_scores = {}
                if needs_generation and target_system == "ask":
                    if needs_retrieval:
                        context_note_ids = retrieved_ids
                        generation_context_source = "retrieved"
                    else:
                        context_note_ids = expected_note_ids
                        generation_context_source = "gold"

                    gen_notes = [
                        note_to_generator_shape(notes_by_id[nid])
                        for nid in context_note_ids if nid in notes_by_id
                    ]

                    if stages and "intent" in stages:
                        gen_plan = plan
                        gen_plan.k = len(gen_notes)
                    else:
                        gen_plan = build_plan(
                            pair.get("intent"), pair.get("expected_time_filter"),
                            pair.get("expected_category_filter"), k=len(gen_notes),
                        )

                    # browse intent never reaches the generator in production
                    # (src/rag/pipeline.py returns notes directly, answer=None) —
                    # mirror that here instead of scoring QA-style relevancy
                    # against a query the generator was never meant to answer.
                    if gen_plan.intent != "browse":
                        generated_answer, _generator_model = generate_answer(query, gen_plan, gen_notes, config)
                        contexts = [format_note(n) for n in gen_notes]
                        generation_scores = grade_generation(
                            query, generated_answer, contexts, generation_metrics, generation_scorers,
                        )
                    for m in GENERATION_METRICS:
                        if generation_scores.get(m) is not None:
                            generation_score_lists[m].append(generation_scores[m])

                row = {
                    "id": str(uuid.uuid4()),
                    "run_id": run_id,
                    "created_at": created_at,
                    "dataset": dataset,
                    "embedding": config.get("embedding_model"),
                    "retriever": config.get("retriever"),
                    "n_results": config.get("n_results"),
                    "reranker": config.get("reranker"),
                    "stages": stages or [],
                    "query": query,
                    "note_id": pair.get("note_id"),
                    "target_system": target_system,
                    "expected_note_ids": expected_note_ids,
                    "retrieved_ids": retrieved_ids,
                    "recall": scores["recall"],
                    "mrr": scores["mrr"],
                    "expected_intent": pair.get("intent"),
                    "actual_intent": intent_scores.get("actual_intent"),
                    "intent_match": intent_scores.get("intent_match"),
                    "expected_time_filter": pair.get("expected_time_filter"),
                    "actual_time_filter": intent_scores.get("actual_time_filter"),
                    "time_filter_match": intent_scores.get("time_filter_match"),
                    "expected_category_filter": pair.get("expected_category_filter"),
                    "actual_category_filter": intent_scores.get("actual_category_filter"),
                    "category_filter_match": intent_scores.get("category_filter_match"),
                    "generation_context_source": generation_context_source,
                    "generated_answer": generated_answer,
                    "context_relevance": generation_scores.get("context_relevance"),
                    "context_utilization": generation_scores.get("context_utilization"),
                    "faithfulness": generation_scores.get("faithfulness"),
                    "answer_relevancy": generation_scores.get("answer_relevancy"),
                    "eval_set_hash": eval_set_hash,
                }
                conn.execute("""
                    INSERT INTO stage_results VALUES
                    (:id,:run_id,:created_at,:dataset,:embedding,:retriever,:n_results,:reranker,
                     :stages,:query,:note_id,:target_system,:expected_note_ids,:retrieved_ids,
                     :recall,:mrr,:expected_intent,:actual_intent,:intent_match,
                     :expected_time_filter,:actual_time_filter,:time_filter_match,
                     :expected_category_filter,:actual_category_filter,:category_filter_match,
                     :generation_context_source,:generated_answer,
                     :context_relevance,:context_utilization,:faithfulness,:answer_relevancy,
                     :eval_set_hash)
                """, {
                    **row,
                    "stages": json.dumps(row["stages"]),
                    "expected_note_ids": json.dumps(row["expected_note_ids"]),
                    "retrieved_ids": json.dumps(row["retrieved_ids"]),
                })
                conn.commit()
                jsonl_f.write(json.dumps(row) + "\n")

            else:
                # dataset1-style row: singular expected_note_id, optional ambiguous flag
                expected_id = pair["expected_note_id"]
                ambiguous = pair.get("ambiguous", False)

                retrieved_ids = retrieve(query, config, collection, note_texts)
                scores = grade(
                    retrieved_ids, expected_id,
                    query=query, ambiguous=ambiguous, note_texts=note_texts,
                )

                if ambiguous:
                    ambiguous_judge_scores.append(scores["llm_judge_score"])
                else:
                    exact_recalls.append(scores["recall"])
                    exact_mrrs.append(scores["mrr"])

                row = {
                    "id": str(uuid.uuid4()),
                    "run_id": run_id,
                    "created_at": created_at,
                    "dataset": dataset,
                    "embedding": config["embedding_model"],
                    "retriever": config["retriever"],
                    "n_results": config.get("n_results", 5),
                    "query": query,
                    "expected_id": expected_id,
                    "retrieved_ids": retrieved_ids,
                    "recall": scores["recall"],
                    "mrr": scores["mrr"],
                    "ambiguous": 1 if ambiguous else 0,
                    "llm_judge_score": scores["llm_judge_score"],
                    "eval_set_hash": eval_set_hash,
                    "reranker": config.get("reranker", ""),
                }

                conn.execute("""
                    INSERT INTO results VALUES
                    (:id,:run_id,:created_at,:dataset,:embedding,:retriever,
                     :n_results,:query,:expected_id,
                     json(:retrieved_ids),:recall,:mrr,:ambiguous,:llm_judge_score,:eval_set_hash,:reranker)
                """, {**row, "retrieved_ids": json.dumps(retrieved_ids)})
                conn.commit()
                jsonl_f.write(json.dumps(row) + "\n")

    conn.close()

    print(f"Results — run {run_id}")

    if multi_recalls:
        n_multi = len(multi_recalls)
        avg_recall = sum(multi_recalls) / n_multi
        avg_mrr = sum(multi_mrrs) / n_multi
        print(f"  dataset2 retrieval ({n_multi}):  avg recall {avg_recall:.3f}  avg mrr {avg_mrr:.3f}")

    if intent_matches:
        n_intent = len(intent_matches)
        intent_acc = sum(intent_matches) / n_intent
        time_acc = sum(time_filter_matches) / n_intent
        category_acc = sum(category_filter_matches) / n_intent
        print(
            f"  dataset2 intent ({n_intent}):    intent {intent_acc:.3f}  "
            f"time_filter {time_acc:.3f}  category_filter {category_acc:.3f}"
        )

    if needs_generation:
        n_gen = len(generation_score_lists["context_relevance"]) or len(generation_score_lists["faithfulness"])
        parts = []
        for m in GENERATION_METRICS:
            scores = generation_score_lists[m]
            if scores:
                parts.append(f"{m} {sum(scores)/len(scores):.3f}")
        print(f"  dataset2 generation ({n_gen}):  " + "  ".join(parts) if parts else "  dataset2 generation: no scores")

    n_exact = len(exact_recalls)
    n_ambig = len(ambiguous_judge_scores)
    if n_exact:
        avg_recall = sum(exact_recalls) / n_exact
        avg_mrr = sum(exact_mrrs) / n_exact
        print(f"  exact queries ({n_exact}):      avg recall {avg_recall:.3f}  avg mrr {avg_mrr:.3f}")
    if n_ambig:
        relevant = sum(1 for s in ambiguous_judge_scores if s > 0)
        avg_judge = sum(ambiguous_judge_scores) / n_ambig
        print(f"  ambiguous queries ({n_ambig}):  llm-judge {relevant}/{n_ambig} relevant  (avg {avg_judge:.2f})")

    print(f"  {jsonl_path.name} written")
    print("  logged to runs.db")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config", nargs="+", required=True,
        help="Config-set filename(s) in experiments/configs/ (bare names, no path)",
    )
    args = parser.parse_args()

    for config in load_configs(args.config):
        run(config)
