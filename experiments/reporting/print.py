"""
Terminal rendering for dataset2 stage summaries and per-row drill-down.

Mirrors the box-drawing style already used in report.py/compare.py for
dataset1, so combined terminal output (retrieval + intent + generation
printed in sequence) reads as one consistent system.
"""

from experiments.grader import GENERATION_METRICS


def print_retrieval_summary(summary: dict, label: str = "RETRIEVAL SUMMARY"):
    print(f"\n{'═' * 65}")
    print(label)
    n = summary.get("n", 0)
    if not n:
        print("  no retrieval-stage rows")
        return
    print(f"  total queries  : {n}")
    print(f"  ✓ rank 1       : {summary['rank1']}  ({summary['rank1'] / n * 100:.0f}%)")
    print(f"  ~ found, not #1: {summary['found_not_first']}  ({summary['found_not_first'] / n * 100:.0f}%)")
    print(f"  ✗ not found    : {summary['missed']}  ({summary['missed'] / n * 100:.0f}%)")
    print(f"  avg recall     : {summary['avg_recall']:.3f}")
    print(f"  avg mrr        : {summary['avg_mrr']:.3f}")


def print_intent_summary(summary: dict, label: str = "INTENT SUMMARY"):
    print(f"\n{'═' * 65}")
    print(label)
    n = summary.get("n", 0)
    if not n:
        print("  no intent-stage rows")
        return
    print(f"  total queries        : {n}")
    print(f"  intent accuracy      : {summary['intent_acc']:.3f}")
    print(f"  time_filter accuracy : {summary['time_filter_acc']:.3f}")
    print(f"  category_filter acc  : {summary['category_filter_acc']:.3f}")
    print("\n  confusion (expected → actual):")
    for (expected, actual), count in sorted(summary["confusion"].items(), key=lambda kv: -kv[1]):
        marker = "✓" if expected == actual else "✗"
        print(f"    {marker} {str(expected):>15} → {str(actual):<15}  {count}")


def print_generation_summary(summary: dict, label: str = "GENERATION SUMMARY"):
    print(f"\n{'═' * 65}")
    print(label)
    n = summary.get("n", 0)
    if not n:
        print("  no generation-stage rows")
        return
    print(f"  total queries  : {n}")
    for m in GENERATION_METRICS:
        stats = summary["metrics"].get(m)
        if stats:
            print(f"  {m:<20}: mean {stats['mean']:.3f}  (n={stats['n']}, low<0.5: {stats['low_count']})")


def show_retrieval_multi(row: dict, notes: dict):
    retrieved_ids = row["retrieved_ids"]
    expected_ids = row["expected_note_ids"]

    print(f"\n{'─' * 65}")
    print(f"query    : {row['query']}")

    rank = None
    if row["recall"] == 1.0:
        ranks = [retrieved_ids.index(eid) + 1 for eid in expected_ids if eid in retrieved_ids]
        rank = min(ranks)
    if rank:
        print(f"result   : found at rank {rank}  (mrr {row['mrr']:.2f})")
    else:
        print("result   : NOT FOUND")

    print("\nEXPECTED (any of):")
    for eid in expected_ids:
        print(f"  [{eid}] {notes.get(eid, '?')}")

    print("\nRETRIEVED:")
    for i, rid in enumerate(retrieved_ids, 1):
        marker = "✓" if rid in expected_ids else " "
        print(f"  {marker} #{i} [{rid}]")
        print(f"       {notes.get(rid, '?')[:500]}...")


def show_intent(row: dict):
    print(f"\n{'─' * 65}")
    print(f"query    : {row['query']}")
    print(f"intent   : expected {row.get('expected_intent')!r}  actual {row.get('actual_intent')!r}"
          f"  {'✓' if row.get('intent_match') else '✗'}")
    print(f"time     : expected {row.get('expected_time_filter')!r}  actual {row.get('actual_time_filter')!r}"
          f"  {'✓' if row.get('time_filter_match') else '✗'}")
    print(f"category : expected {row.get('expected_category_filter')!r}  actual {row.get('actual_category_filter')!r}"
          f"  {'✓' if row.get('category_filter_match') else '✗'}")


def _fmt_rank(r):
    return "✗" if r is None else f"#{r}"


def show_generation(row: dict, notes: dict):
    context_ids = row["retrieved_ids"] if row.get("generation_context_source") == "retrieved" else row["expected_note_ids"]

    print(f"\n{'─' * 65}")
    print(f"query    : {row['query']}")
    print(f"context  : ({row.get('generation_context_source')})")
    for cid in context_ids:
        print(f"  [{cid}] {notes.get(cid, '?')[:300]}...")

    print(f"\nanswer   : {row.get('generated_answer')}")

    print("\nscores:")
    for m in GENERATION_METRICS:
        score = row.get(m)
        if score is not None:
            flag = "  (low)" if score < 0.5 else ""
            print(f"  {m:<20}: {score:.3f}{flag}")
