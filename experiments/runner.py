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
from experiments.pipeline.pipeline import retrieve


def init_db(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id            TEXT PRIMARY KEY,
            run_id        TEXT,
            created_at    TEXT,
            dataset       TEXT,
            embedding     TEXT,
            retriever     TEXT,
            n_results     INTEGER,
            query         TEXT,
            expected_id   TEXT,
            retrieved_ids TEXT,
            recall        REAL,
            precision     REAL
        )
    """)
    conn.commit()
    return conn


def run(config: dict):
    run_id = str(uuid.uuid4())[:8]
    created_at = datetime.now(timezone.utc).isoformat()

    dataset = config["dataset"]
    eval_path = DATASETS[dataset].parent / "eval_set.jsonl"
    eval_pairs = [json.loads(l) for l in open(eval_path) if l.strip()]

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    runs_dir = RESULTS_DIR / "runs"
    runs_dir.mkdir(exist_ok=True)

    db_path = RESULTS_DIR / "runs.db"
    jsonl_path = runs_dir / f"run_{run_id}.jsonl"

    conn = init_db(db_path)

    recalls, precisions = [], []

    print(f"Run {run_id} | {dataset} | {config['embedding_model']} | {config['retriever']}")
    print(f"Evaluating {len(eval_pairs)} queries...\n")

    with open(jsonl_path, "w", buffering=1) as jsonl_f:
        for pair in eval_pairs:
            query = pair["query"]
            expected_id = pair["expected_note_id"]

            retrieved_ids = retrieve(query, config)
            scores = grade(retrieved_ids, expected_id)

            recalls.append(scores["recall"])
            precisions.append(scores["precision"])

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
                "precision": scores["precision"],
            }

            conn.execute("""
                INSERT INTO results VALUES
                (:id,:run_id,:created_at,:dataset,:embedding,:retriever,
                 :n_results,:query,:expected_id,
                 json(:retrieved_ids),:recall,:precision)
            """, {**row, "retrieved_ids": json.dumps(retrieved_ids)})
            conn.commit()
            jsonl_f.write(json.dumps(row) + "\n")

    conn.close()

    avg_recall = sum(recalls) / len(recalls)
    avg_precision = sum(precisions) / len(precisions)

    print(f"Results — run {run_id}")
    print(f"  avg recall:    {avg_recall:.3f}")
    print(f"  avg precision: {avg_precision:.3f}")
    print(f"  {jsonl_path.name} written")
    print(f"  logged to runs.db")


if __name__ == "__main__":
    for embedding_model in ["default", "bge-large"]:
        run({
            "dataset": "dataset1",
            "embedding_model": embedding_model,
            "retriever": "vector",
            "n_results": 5,
        })
