"""
Pure aggregation: dataset2 stage_results rows -> summary dicts.

No printing, no file I/O — experiments/reporting/print.py renders these.
Each summarize_*() expects rows already filtered to that stage's applicable
rows (caller's job, since "applicable" differs per stage — see report.py).
"""

from experiments.grader import GENERATION_METRICS


def summarize_retrieval(rows: list[dict]) -> dict:
    n = len(rows)
    if n == 0:
        return {"n": 0}
    rank1 = sum(1 for r in rows if r["mrr"] == 1.0)
    found_not_first = sum(1 for r in rows if r["recall"] == 1.0 and r["mrr"] < 1.0)
    missed = sum(1 for r in rows if r["recall"] == 0.0)
    return {
        "n": n,
        "rank1": rank1,
        "found_not_first": found_not_first,
        "missed": missed,
        "avg_recall": sum(r["recall"] for r in rows) / n,
        "avg_mrr": sum(r["mrr"] for r in rows) / n,
    }


def summarize_intent(rows: list[dict]) -> dict:
    n = len(rows)
    if n == 0:
        return {"n": 0}
    confusion = {}
    for r in rows:
        key = (r.get("expected_intent"), r.get("actual_intent"))
        confusion[key] = confusion.get(key, 0) + 1
    return {
        "n": n,
        "intent_acc": sum(r["intent_match"] for r in rows) / n,
        "time_filter_acc": sum(r["time_filter_match"] for r in rows) / n,
        "category_filter_acc": sum(r["category_filter_match"] for r in rows) / n,
        "confusion": confusion,
    }


def summarize_generation(rows: list[dict]) -> dict:
    n = len(rows)
    metrics = {}
    for m in GENERATION_METRICS:
        scores = [r[m] for r in rows if r.get(m) is not None]
        if scores:
            metrics[m] = {
                "mean": sum(scores) / len(scores),
                "n": len(scores),
                "low_count": sum(1 for s in scores if s < 0.5),
            }
    return {"n": n, "metrics": metrics}


def detect_stages(rows: list[dict]) -> list[str]:
    """Stages that actually ran for this run — same for every row of a run
    (one config -> one uniform run), so the first row is representative."""
    return rows[0].get("stages") or []
