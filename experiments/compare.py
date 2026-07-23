"""
Side-by-side comparison of two runs.

Usage:
  python experiments/compare.py run_60052450 run_41be62cc
"""

import argparse
import json
from pathlib import Path

RUNS_DIR = Path(__file__).parent / "artifacts/results/runs"


def load_run(run_id: str) -> dict:
    for name in [run_id, f"run_{run_id}"]:
        path = RUNS_DIR / f"{name}.jsonl"
        if path.exists():
            rows = [json.loads(l) for l in open(path) if l.strip()]
            return {r["query"]: r for r in rows}, rows[0]
    raise FileNotFoundError(f"No run file found for: {run_id}")


def rank_of(row: dict) -> int | None:
    if row["recall"] == 0.0:
        return None
    return row["retrieved_ids"].index(row["expected_id"]) + 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run_a")
    parser.add_argument("run_b")
    args = parser.parse_args()

    a_by_query, a_meta = load_run(args.run_a)
    b_by_query, b_meta = load_run(args.run_b)

    label_a = f"{a_meta['run_id']} ({a_meta['embedding']})"
    label_b = f"{b_meta['run_id']} ({b_meta['embedding']})"

    all_queries = sorted(set(a_by_query) | set(b_by_query))

    improved, regressed, same_found, same_missed = [], [], [], []

    for q in all_queries:
        a_row = a_by_query.get(q)
        b_row = b_by_query.get(q)
        if not a_row or not b_row:
            continue
        ra = rank_of(a_row)
        rb = rank_of(b_row)

        if ra is None and rb is None:
            same_missed.append((q, a_row["expected_id"]))
        elif ra == rb:
            same_found.append((q, ra, a_row["expected_id"]))
        elif rb is not None and (ra is None or rb < ra):
            improved.append((q, ra, rb, a_row["expected_id"]))
        else:
            regressed.append((q, ra, rb, a_row["expected_id"]))

    def summary(by_query: dict) -> dict:
        rows = list(by_query.values())
        n = len(rows)
        rank1 = sum(1 for r in rows if r["precision"] == 1.0)
        found = sum(1 for r in rows if r["recall"] == 1.0 and r["precision"] < 1.0)
        missed = sum(1 for r in rows if r["recall"] == 0.0)
        avg_r = sum(r["recall"] for r in rows) / n
        avg_p = sum(r["precision"] for r in rows) / n
        return {"n": n, "rank1": rank1, "found": found, "missed": missed,
                "avg_recall": avg_r, "avg_precision": avg_p}

    sa = summary(a_by_query)
    sb = summary(b_by_query)

    W = 38
    print(f"\n{'═' * (W * 2 + 3)}")
    print(f"  {'A: ' + label_a:<{W}}  {'B: ' + label_b:<{W}}")
    print(f"{'═' * (W * 2 + 3)}")

    def row(label, va, vb):
        print(f"  {label:<20} {str(va):<{W - 20}}  {str(vb):<{W}}")

    row("queries", sa["n"], sb["n"])
    row("✓ rank 1", f"{sa['rank1']}  ({sa['rank1']/sa['n']*100:.0f}%)", f"{sb['rank1']}  ({sb['rank1']/sb['n']*100:.0f}%)")
    row("~ found, not #1", f"{sa['found']}  ({sa['found']/sa['n']*100:.0f}%)", f"{sb['found']}  ({sb['found']/sb['n']*100:.0f}%)")
    row("✗ not found", f"{sa['missed']}  ({sa['missed']/sa['n']*100:.0f}%)", f"{sb['missed']}  ({sb['missed']/sb['n']*100:.0f}%)")
    row("avg recall", f"{sa['avg_recall']:.3f}", f"{sb['avg_recall']:.3f}")
    row("avg precision", f"{sa['avg_precision']:.3f}", f"{sb['avg_precision']:.3f}")

    def fmt_rank(r):
        return "✗" if r is None else f"#{r}"

    if improved:
        print(f"\n{'─' * (W * 2 + 3)}")
        print(f"  B IMPROVED  ({len(improved)} queries)")
        for q, ra, rb, eid in improved:
            print(f"  {fmt_rank(ra):>3} → {fmt_rank(rb):<3}  [{eid}]  {q}")

    if regressed:
        print(f"\n{'─' * (W * 2 + 3)}")
        print(f"  B REGRESSED  ({len(regressed)} queries)")
        for q, ra, rb, eid in regressed:
            print(f"  {fmt_rank(ra):>3} → {fmt_rank(rb):<3}  [{eid}]  {q}")

    if same_missed:
        print(f"\n{'─' * (W * 2 + 3)}")
        print(f"  BOTH MISSED  ({len(same_missed)} queries)")
        for q, eid in same_missed:
            print(f"  ✗ → ✗   [{eid}]  {q}")

    if same_found:
        print(f"\n{'─' * (W * 2 + 3)}")
        print(f"  SAME RANK  ({len(same_found)} queries)")
        for q, r, eid in same_found:
            print(f"  #{r} → #{r}  [{eid}]  {q}")


if __name__ == "__main__":
    main()
