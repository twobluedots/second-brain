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
from experiments.grader import GENERATION_METRICS
from experiments.reporting.print import (
    print_generation_summary,
    print_intent_summary,
    print_retrieval_summary,
    show_generation,
    show_intent,
    show_retrieval_multi,
)
from experiments.reporting.summarize import (
    detect_stages,
    summarize_generation,
    summarize_intent,
    summarize_retrieval,
)

RUNS_DIR = Path(__file__).parent / "artifacts/results/runs"
REPORTS_DIR = Path(__file__).parent / "artifacts/results/reports"


def load_notes(dataset: str) -> dict:
    notes = {}
    with open(DATASETS[dataset]["notes"]) as f:
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


def run_dataset2_report(args, rows: list, notes: dict):
    """dataset2 stage_results reporting — one file per stage present in the
    run (or per --stage if given), each self-contained; terminal prints every
    generated block in sequence so a full-pipeline run is still readable in
    one invocation without opening multiple files."""
    run_id = rows[0]["run_id"]
    stages_present = detect_stages(rows)
    order = ["retrieval", "intent", "generation"]

    if args.stage:
        if args.stage not in stages_present:
            print(f"Run {run_id} has no {args.stage!r} stage (stages present: {stages_present})")
            return
        stages_to_report = [args.stage]
    else:
        stages_to_report = [s for s in order if s in stages_present]

    for stage in stages_to_report:
        report_path = REPORTS_DIR / f"{run_id}_{stage}_report.txt"
        with open(report_path, "w") as f:
            sys.stdout = Tee(f)
            try:
                print(f"Run      : {run_id}")
                print(f"Stage    : {stage}")
                print(f"Config   : {rows[0]['dataset']} | {rows[0].get('embedding')} | {rows[0].get('retriever')} "
                      f"| eval_set {rows[0].get('eval_set_hash', 'n/a')}")

                if stage == "retrieval":
                    applicable = [r for r in rows if r.get("recall") is not None]
                    summary = summarize_retrieval(applicable)
                    failures = [r for r in applicable if r["recall"] == 0.0]
                    low = [r for r in applicable if r["recall"] == 1.0 and r["mrr"] < 1.0]

                    if args.all:
                        for r in applicable:
                            show_retrieval_multi(r, notes)
                    else:
                        if failures:
                            print(f"\n{'═' * 65}")
                            print(f"NOT FOUND ({len(failures)} queries)")
                            for r in failures:
                                show_retrieval_multi(r, notes)
                        if low:
                            print(f"\n{'═' * 65}")
                            print(f"LOW PRECISION — found but not at rank 1 ({len(low)} queries)")
                            for r in low:
                                show_retrieval_multi(r, notes)
                        if not failures and not low:
                            print("\n✓ no misses — every query found an expected note at rank 1")

                    print_retrieval_summary(summary)

                elif stage == "intent":
                    applicable = [r for r in rows if r.get("intent_match") is not None]
                    summary = summarize_intent(applicable)
                    mismatches = [
                        r for r in applicable
                        if not (r["intent_match"] and r["time_filter_match"] and r["category_filter_match"])
                    ]

                    if args.all:
                        for r in applicable:
                            show_intent(r)
                    else:
                        if mismatches:
                            print(f"\n{'═' * 65}")
                            print(f"MISMATCHES ({len(mismatches)} queries)")
                            for r in mismatches:
                                show_intent(r)
                        else:
                            print("\n✓ no misses — intent/filters matched on every query")

                    print_intent_summary(summary)

                elif stage == "generation":
                    applicable = [r for r in rows if r.get("generated_answer") is not None]
                    summary = summarize_generation(applicable)
                    low = [
                        r for r in applicable
                        if any(r.get(m) is not None and r[m] < 0.5 for m in GENERATION_METRICS)
                    ]

                    if args.all:
                        for r in applicable:
                            show_generation(r, notes)
                    else:
                        if low:
                            print(f"\n{'═' * 65}")
                            print(f"LOW SCORES — at least one metric < 0.5 ({len(low)} queries)")
                            for r in low:
                                show_generation(r, notes)
                        else:
                            print("\n✓ no low scores across selected metrics")

                    print_generation_summary(summary)

                print(f"\nSaved to: {report_path}")
            finally:
                sys.stdout = sys.stdout.terminal


def run_dataset1_report(args, rows: list, notes: dict):
    report_path = REPORTS_DIR / f"{args.run_id}_report.txt"

    with open(report_path, "w") as f:
        sys.stdout = Tee(f)
        try:
            print(f"Run      : {args.run_id}")
            print(f"Config   : {rows[0]['dataset']} | {rows[0]['embedding']} | {rows[0]['retriever']} "
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run_id")
    parser.add_argument("--all", action="store_true", help="show all queries not just failures")
    parser.add_argument(
        "--stage", choices=["retrieval", "intent", "generation"],
        help="dataset2 only: limit report to one stage (default: every stage present in the run)",
    )
    args = parser.parse_args()

    rows = load_run(args.run_id)
    dataset = rows[0]["dataset"]
    notes = load_notes(dataset)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    if "target_system" in rows[0]:
        run_dataset2_report(args, rows, notes)
    else:
        run_dataset1_report(args, rows, notes)


if __name__ == "__main__":
    main()
