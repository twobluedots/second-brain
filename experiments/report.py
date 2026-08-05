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

RUNS_DIR = Path(__file__).parent / "artifacts/results/runs"
REPORTS_DIR = Path(__file__).parent / "artifacts/results/reports"
NOTES_FILE = Path(__file__).parent / "data/dataset1/notes.jsonl"


def load_notes() -> dict:
    notes = {}
    with open(NOTES_FILE) as f:
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
    expected_id = row["expected_id"]
    retrieved_ids = row["retrieved_ids"]
    rank = retrieved_ids.index(expected_id) + 1 if row["recall"] == 1.0 else None

    print(f"\n{'─' * 65}")
    print(f"query    : {row['query']}")
    if rank:
        print(f"result   : found at rank {rank}  (mrr {row['mrr']:.2f})")
    else:
        print("result   : NOT FOUND")

    print(f"\nEXPECTED [{expected_id}]:")
    print(f"  {notes.get(expected_id, '?')}")

    print("\nRETRIEVED:")
    for i, rid in enumerate(retrieved_ids[:5], 1):
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

    notes = load_notes()
    rows = load_run(args.run_id)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / f"{args.run_id}_report.txt"

    with open(report_path, "w") as f:
        sys.stdout = Tee(f)

        print(f"Run      : {args.run_id}")
        print(f"Config   : {rows[0]['dataset']} | {rows[0]['embedding']} | {rows[0]['retriever']}")

        failures = [r for r in rows if r.get("recall") == 0.0]
        low = [r for r in rows if r.get("recall") == 1.0 and r.get("mrr", 1.0) < 1.0]

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

            if not failures and not low:
                print("\n✓ perfect run — all queries returned expected note at rank 1")

        print_summary(rows)
        print(f"\nSaved to: {report_path}")

        sys.stdout = sys.stdout.terminal


if __name__ == "__main__":
    main()
