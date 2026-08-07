"""
Collects raw ask() pipeline outputs for later RAGAS grading — no scoring here.

Calls pipeline.ask() directly to avoid polluting ask_log.
Queries come from experiments/ask_eval/queries/<query_set>.json (default: "default").
Each record is written to disk immediately, so a crash mid-run never loses
the queries already answered. Grading against these saved records happens
separately in grader.py — that step can be rerun on its own without
calling ask() again.

Usage:
  python experiments/ask_eval/runner.py
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from src.rag.pipeline import ask
from src.storage.storage import Storage

RECORDS_DIR = Path(__file__).parent.parent / "artifacts/ask_eval/records"
QUERIES_DIR = Path(__file__).parent / "queries"


def _load_queries(query_set: str = "default") -> list[str]:
    path = QUERIES_DIR / f"{query_set}.json"
    if not path.exists():
        raise FileNotFoundError(f"Query set not found: {path}")
    return json.loads(path.read_text())


def collect(query_set: str = "default") -> Path:
    queries = _load_queries(query_set)
    storage = Storage()
    RECORDS_DIR.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    out_path = RECORDS_DIR / f"run_{run_id}.jsonl"

    print(f"Run {run_id} | query_set={query_set} | {len(queries)} queries")
    print(f"Writing to: {out_path}\n")

    with open(out_path, "w", buffering=1) as f:
        for q in queries:
            print(f"  Q: {q}")
            result = ask(q, storage)
            notes = [
                {"id": n.get("id"), "content": n.get("content")}
                for n in result.notes if n.get("content")
            ]

            record = {
                "run_id": run_id,
                "query_set": query_set,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "user_input": q,
                "response": result.answer or "",
                "retrieved_contexts": notes,
                "intent": result.intent,
                "fallback": result.fallback,
            }
            f.write(json.dumps(record) + "\n")
            print(f"     intent={result.intent}  retrieved_contexts={len(notes)}  response={'yes' if result.answer else 'none'}")

    print(f"\nSaved {len(queries)} records to: {out_path}")
    return out_path


if __name__ == "__main__":
    collect()
