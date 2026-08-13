"""
Experiment runner — ties pipeline + grader together and logs results.

Outputs per run:
  artifacts/results/runs.db              SQLite — all runs aggregated, queryable
  artifacts/results/runs/run_<id>.jsonl  JSONL  — one file per run, human-readable

Usage:
  python experiments/runner.py
"""

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from experiments.config import DATASETS, RESULTS_DIR
from experiments.grader import grade
from experiments.pipeline.index import load_or_build
from experiments.pipeline.pipeline import retrieve
from experiments.utils import hash_file


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
    conn.commit()
    return conn


def build_run_id(config: dict, now: datetime) -> str:
    parts = [
        config["dataset"],
        config["embedding_model"],
        config["retriever"],
        f"n{config.get('n_results', 5)}",
    ]
    if config.get("reranker"):
        parts.append(config["reranker"])
    parts.append(now.strftime("%Y%m%d-%H%M%S"))
    return "_".join(parts)


def run(config: dict):
    now = datetime.now(timezone.utc)
    created_at = now.isoformat()
    run_id = build_run_id(config, now)

    dataset = config["dataset"]
    eval_path = DATASETS[dataset].parent / "eval_set.jsonl"
    eval_pairs = [json.loads(line) for line in open(eval_path) if line.strip()]
    eval_set_hash = hash_file(eval_path)

    notes_path = DATASETS[dataset].parent / "notes.jsonl"
    note_texts = {}
    if notes_path.exists():
        for line in open(notes_path):
            n = json.loads(line)
            note_texts[n["id"]] = n["text"]

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    runs_dir = RESULTS_DIR / "runs"
    runs_dir.mkdir(exist_ok=True)

    db_path = RESULTS_DIR / "runs.db"
    jsonl_path = runs_dir / f"run_{run_id}.jsonl"

    conn = init_db(db_path)
    collection = load_or_build(config)

    exact_recalls, exact_mrrs, ambiguous_judge_scores = [], [], []

    reranker_label = config.get("reranker", "none")
    print(f"Run {run_id} | {dataset} (eval_set {eval_set_hash}) | {config['embedding_model']} | {config['retriever']} | reranker={reranker_label}")
    print(f"Evaluating {len(eval_pairs)} queries...\n")

    with open(jsonl_path, "w", buffering=1) as jsonl_f:
        for pair in eval_pairs:
            query = pair["query"]
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

    n_exact = len(exact_recalls)
    n_ambig = len(ambiguous_judge_scores)

    print(f"Results — run {run_id}")
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
    for embedding_model in ["default", "bge-large"]:
        run({
            "dataset": "dataset1",
            "embedding_model": embedding_model,
            "retriever": "vector",
            "n_results": 15,
            "reranker": "bge-reranker-base",
        })
