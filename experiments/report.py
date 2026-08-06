"""
Inspect a run's failures with full note texts for human evaluation.
Prints to terminal AND saves to artifacts/results/reports/

Usage:
  python experiments/report.py run_daaaa380
  python experiments/report.py run_daaaa380 --all
"""

import argparse
import json
import sys
from pathlib import Path

from experiments.config import DATASETS

RUNS_DIR = Path(__file__).parent / "artifacts/results/runs"
REPORTS_DIR = Path(__file__).parent / "artifacts/results/reports"


def load_notes(dataset: str) -> dict:
    notes = {}
    with open(DATASETS[dataset]) as f:
        for line in f:
            n = json.loads(line)
            notes[n["id"]] = n["text"]
    return notes


def load_run(run_id: str) -> list:
    for name in [run_id, f"run_{run_id}"]:
        path = RUNS_DIR / f"{name}.jsonl"
        if path.exists():
            return [json.loads(line) for line in open(path) if line.strip()]
    raise FileNotFoundError(f"No run file found for: {run_id}")


class Tee:
    """Write to both terminal and a file simultaneously."""
    def __init__(self, file):
        self.file = file
        self.terminal = sys.stdout

    def write(self, msg):
        self.terminal.write(msg)
        self.file.write(msg)

    def flush(self):
        self.terminal.flush()
        self.file.flush()


def show(row: dict, notes: dict):
    retrieved_ids = row["retrieved_ids"]

    print(f"\n{'─' * 65}")
    print(f"query    : {row['query']}")

    if row.get("ambiguous"):
        score = row.get("llm_judge_score")
        score_str = f"{score:.2f}" if score is not None else "n/a"
        print(f"result   : ambiguous — llm-judge score {score_str}")

        print(f"\nREFERENCE [{row['expected_id']}] (one of possibly several valid notes):")
        print(f"  {notes.get(row['expected_id'], '?')}")

        print("\nRETRIEVED (top-3, as judged):")
        for i, rid in enumerate(retrieved_ids[:3], 1):
            print(f"  #{i} [{rid}]")
            print(f"       {notes.get(rid, '?')[:500]}...")
        return

    expected_id = row["expected_id"]
    rank = retrieved_ids.index(expected_id) + 1 if row["recall"] == 1.0 else None
    if rank:
        print(f"result   : found at rank {rank}  (mrr {row['mrr']:.2f})")
    else:
        print("result   : NOT FOUND")

    print(f"\nEXPECTED [{expected_id}]:")
    print(f"  {notes.get(expected_id, '?')}")

    print("\nRETRIEVED:")
    for i, rid in enumerate(retrieved_ids, 1):
        marker = "✓" if rid == expected_id else " "
        print(f"  {marker} #{i} [{rid}]")
        print(f"       {notes.get(rid, '?')[:500]}...")


def print_summary(rows, label="SUMMARY"):
    exact = [r for r in rows if r.get("mrr") is not None]
    ambig = [r for r in rows if r.get("mrr") is None]
    n = len(exact)

    print(f"\n{'═' * 65}")
    print(label)
    print(f"  total queries  : {len(rows)}  (exact: {n}, ambiguous: {len(ambig)})")
    if n:
        perfect = sum(1 for r in exact if r["mrr"] == 1.0)
        found_not_first = sum(1 for r in exact if r["recall"] == 1.0 and r["mrr"] < 1.0)
        missed = sum(1 for r in exact if r["recall"] == 0.0)
        print(f"  ✓ rank 1       : {perfect}  ({perfect/n*100:.0f}%)")
        print(f"  ~ found, not #1: {found_not_first}  ({found_not_first/n*100:.0f}%)")
        print(f"  ✗ not found    : {missed}  ({missed/n*100:.0f}%)")
        print(f"  avg recall     : {sum(r['recall'] for r in exact)/n:.3f}")
        print(f"  avg mrr        : {sum(r['mrr'] for r in exact)/n:.3f}")
    if ambig:
        scores = [r["llm_judge_score"] for r in ambig if r.get("llm_judge_score") is not None]
        if scores:
            relevant = sum(1 for s in scores if s > 0)
            print(f"  ambiguous judge: {relevant}/{len(ambig)} relevant  (avg {sum(scores)/len(scores):.2f})")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run_id")
    parser.add_argument("--all", action="store_true", help="show all queries not just failures")
    args = parser.parse_args()

    rows = load_run(args.run_id)
    dataset = rows[0]["dataset"]
    notes = load_notes(dataset)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / f"{args.run_id}_report.txt"

    with open(report_path, "w") as f:
        sys.stdout = Tee(f)
        try:
            print(f"Run      : {args.run_id}")
            print(f"Config   : {dataset} | {rows[0]['embedding']} | {rows[0]['retriever']} "
                  f"| eval_set {rows[0].get('eval_set_hash', 'n/a')}")

            failures = [r for r in rows if r.get("recall") == 0.0]
            low = [r for r in rows if r.get("recall") == 1.0 and r.get("mrr", 1.0) < 1.0]
            ambig_bad = [r for r in rows if r.get("ambiguous") and (r.get("llm_judge_score") or 0) < 1.0]

            if args.all:
                for row in rows:
                    show(row, notes)
            else:
                if failures:
                    print(f"\n{'═' * 65}")
                    print(f"NOT FOUND ({len(failures)} queries)")
                    for row in failures:
                        show(row, notes)

                if low:
                    print(f"\n{'═' * 65}")
                    print(f"LOW PRECISION — found but not at rank 1 ({len(low)} queries)")
                    for row in low:
                        show(row, notes)

                if ambig_bad:
                    print(f"\n{'═' * 65}")
                    print(f"AMBIGUOUS — LOW JUDGE SCORE ({len(ambig_bad)} queries)")
                    for row in ambig_bad:
                        show(row, notes)

                if not failures and not low and not ambig_bad:
                    print("\n✓ no misses — every exact query hit rank 1, every ambiguous query scored fully relevant")

            print_summary(rows)
            print(f"\nSaved to: {report_path}")
        finally:
            sys.stdout = sys.stdout.terminal


if __name__ == "__main__":
    main()
