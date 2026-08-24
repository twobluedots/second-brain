"""
Bridges dataset2's note schema to what src.rag.generator expects, builds a
QueryPlan from ground truth when the intent stage isn't run, and dispatches
the generation call itself through a config["generator"]-selectable
registry — mirrors pipeline/intent.py's ANALYZERS, so generation-eval isn't
hardcoded to only the production generator.
"""

from datetime import datetime, timedelta
from typing import Optional

from experiments.config import DATASET2_ANCHOR_DATE
from src.rag.analyzer import QueryPlan
from src.rag.generator import generate as _generate_default

GENERATORS = {
    "default": _generate_default,
    # "experimental_v2": ...,  — register modified prompt/model variants here
}


def generate(query: str, plan: QueryPlan, notes: list[dict], config: dict) -> tuple[str, Optional[str]]:
    name = config.get("generator", "default")
    if name not in GENERATORS:
        raise ValueError(f"Unknown generator: {name!r}. Available: {list(GENERATORS)}")
    return GENERATORS[name](query, plan, notes)


def note_to_generator_shape(note: dict) -> dict:
    """dataset2 notes are {id, type, category, days_ago, text} — the same
    text/type/category convention index.py already reads for both datasets.
    generate()/format_note() expect {content, content_type, category,
    created_at}, which is production code shared with the live ask_eval
    track, so the translation happens here rather than reshaping either side.
    """
    anchor = datetime.fromisoformat(DATASET2_ANCHOR_DATE)
    created_at = anchor - timedelta(days=note.get("days_ago", 0))
    return {
        "content": note["text"],
        "content_type": note["type"],
        "category": note["category"],
        "created_at": created_at.isoformat(),
    }


def build_plan(
    expected_intent: Optional[str],
    expected_time_filter: Optional[str],
    expected_category_filter: Optional[str],
    k: int,
) -> QueryPlan:
    """QueryPlan built straight from ground truth — used when the intent
    stage isn't selected, so generation can still run against a sensible
    plan without paying for a live analyze_query() call."""
    return QueryPlan(
        intent=expected_intent or "qa",
        time_filter=expected_time_filter,
        category_filter=expected_category_filter,
        content_type=None,
        k=k,
    )
