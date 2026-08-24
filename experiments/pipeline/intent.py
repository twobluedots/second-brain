"""
Query-intent classification, pluggable per config["analyzer"] — mirrors
pipeline.py's config["retriever"] dispatch, so the intent-eval stage isn't
hardcoded to only the production analyzer and can test modified variants.
"""

from src.rag.analyzer import QueryPlan, analyze_query

ANALYZERS = {
    "default": analyze_query,
    # "experimental_v2": ...,  — register modified prompt/model variants here
}


def analyze(query: str, config: dict) -> QueryPlan:
    name = config.get("analyzer", "default")
    if name not in ANALYZERS:
        raise ValueError(f"Unknown analyzer: {name!r}. Available: {list(ANALYZERS)}")
    return ANALYZERS[name](query)
