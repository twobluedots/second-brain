"""
Pure comparison: two dataset2 stage_results row-sets -> diff dicts.

Row matching is by `query` text — same convention dataset1's compare.py
already uses, no new join key needed.

A stage is only compared where it's applicable in a run: does any row
actually carry that stage's computed field (recall / intent_match /
generated_answer not None). Using row-presence rather than the run's
declared `stages` config list is what lets generation compare across a
gold-context run and a full-pipeline run despite them not sharing a
retrieval stage — generation's own applicability doesn't depend on whether
retrieval or intent ran in either run, so no special-casing is needed.

No printing — experiments/reporting/print.py renders these.
"""

from experiments.grader import GENERATION_METRICS
from experiments.reporting.summarize import summarize_generation, summarize_intent, summarize_retrieval

# "meaningfully different" cutoff for a per-query generation delta, used only
# to bucket rows into regressed/improved lists — same order of magnitude as
# the < 0.5 "low score" cutoff summarize_generation() already uses.
GENERATION_DELTA_THRESHOLD = 0.1


def _by_query(rows: list[dict], predicate) -> dict:
    return {r["query"]: r for r in rows if predicate(r)}


def applicable_retrieval(rows: list[dict]) -> dict:
    return _by_query(rows, lambda r: r.get("recall") is not None)


def applicable_intent(rows: list[dict]) -> dict:
    return _by_query(rows, lambda r: r.get("intent_match") is not None)


def applicable_generation(rows: list[dict]) -> dict:
    return _by_query(rows, lambda r: r.get("generated_answer") is not None)


def _retrieval_rank(row: dict) -> int | None:
    if row["recall"] == 0.0:
        return None
    expected_ids = row["expected_note_ids"]
    retrieved_ids = row["retrieved_ids"]
    ranks = [retrieved_ids.index(eid) + 1 for eid in expected_ids if eid in retrieved_ids]
    return min(ranks)


def compare_retrieval(rows_a: list[dict], rows_b: list[dict]) -> dict | None:
    a = applicable_retrieval(rows_a)
    b = applicable_retrieval(rows_b)
    common = sorted(set(a) & set(b))
    if not common:
        return None

    improved, regressed, same_found, same_missed = [], [], [], []
    for q in common:
        ra, rb = _retrieval_rank(a[q]), _retrieval_rank(b[q])
        if ra is None and rb is None:
            same_missed.append(q)
        elif ra == rb:
            same_found.append((q, ra))
        elif rb is not None and (ra is None or rb < ra):
            improved.append((q, ra, rb))
        else:
            regressed.append((q, ra, rb))

    return {
        "summary_a": summarize_retrieval(list(a.values())),
        "summary_b": summarize_retrieval(list(b.values())),
        "n_common": len(common),
        "improved": improved,
        "regressed": regressed,
        "same_found": same_found,
        "same_missed": same_missed,
    }


def _intent_ok(row: dict) -> bool:
    return bool(row["intent_match"] and row["time_filter_match"] and row["category_filter_match"])


def compare_intent(rows_a: list[dict], rows_b: list[dict]) -> dict | None:
    a = applicable_intent(rows_a)
    b = applicable_intent(rows_b)
    common = sorted(set(a) & set(b))
    if not common:
        return None

    fixed, broken, same_ok, same_bad = [], [], [], []
    for q in common:
        ok_a, ok_b = _intent_ok(a[q]), _intent_ok(b[q])
        if ok_a == ok_b:
            (same_ok if ok_a else same_bad).append(q)
        elif ok_b:
            fixed.append(q)
        else:
            broken.append(q)

    return {
        "summary_a": summarize_intent(list(a.values())),
        "summary_b": summarize_intent(list(b.values())),
        "n_common": len(common),
        "fixed": fixed,
        "broken": broken,
        "same_ok": same_ok,
        "same_bad": same_bad,
    }


def compare_generation(rows_a: list[dict], rows_b: list[dict]) -> dict | None:
    a = applicable_generation(rows_a)
    b = applicable_generation(rows_b)
    common = sorted(set(a) & set(b))
    if not common:
        return None

    per_metric_deltas = {m: [] for m in GENERATION_METRICS}
    regressed, improved = [], []
    for q in common:
        row_deltas = {}
        for m in GENERATION_METRICS:
            sa, sb = a[q].get(m), b[q].get(m)
            if sa is not None and sb is not None:
                d = sb - sa
                per_metric_deltas[m].append(d)
                row_deltas[m] = d
        if not row_deltas:
            continue
        worst = min(row_deltas.values())
        best = max(row_deltas.values())
        if worst < -GENERATION_DELTA_THRESHOLD:
            regressed.append((q, row_deltas))
        elif best > GENERATION_DELTA_THRESHOLD:
            improved.append((q, row_deltas))

    metric_stats = {
        m: {"mean_delta": sum(ds) / len(ds), "n": len(ds)}
        for m, ds in per_metric_deltas.items() if ds
    }

    return {
        "summary_a": summarize_generation(list(a.values())),
        "summary_b": summarize_generation(list(b.values())),
        "n_common": len(common),
        "metric_stats": metric_stats,
        "regressed": regressed,
        "improved": improved,
    }
