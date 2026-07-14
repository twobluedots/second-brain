"""
Retrieval — step 2 of the RAG pipeline.
Translates a QueryPlan into storage calls and returns notes + a fallback flag.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from src.logger import logger
from src.rag.analyzer import QueryPlan
from src.storage.storage import Storage
from src.utils import time_filter_to_iso, time_filter_to_ts


@dataclass
class RetrievalResult:
    notes: List[Dict] = field(default_factory=list)
    fallback: bool = False  # True = no strong match; notes are closest available


def _build_chroma_where(plan: QueryPlan) -> Optional[Dict]:
    """Build ChromaDB where clause from plan. Category is never a hard filter here —
    it's passed to the generator as a hint instead (see decisions.md 2026-07-13)."""
    conditions = []
    if plan.content_type:
        conditions.append({"content_type": {"$eq": plan.content_type}})
    if plan.time_filter:
        conditions.append({"created_at_ts": {"$gte": time_filter_to_ts(plan.time_filter)}})
    if not conditions:
        return None
    return conditions[0] if len(conditions) == 1 else {"$and": conditions}


def retrieve(query: str, plan: QueryPlan, storage: Storage) -> RetrievalResult:
    """
    Retrieve notes from storage based on the QueryPlan.

    Browse → SQLite get_entries() with hard category filter (user explicitly asked for it).
    Factual/QA/Pattern → ChromaDB semantic search; category passed to generator as hint only.
    If semantic search returns nothing, retries without filters and marks fallback=True.
    """
    if plan.intent == "browse":
        date_from = time_filter_to_iso(plan.time_filter) if plan.time_filter else None
        notes = storage.get_entries(
            content_type=plan.content_type,
            date_from=date_from,
            category=plan.category_filter,
            limit=20,
        )
        logger.info("Browse retrieval: %d notes (time=%s cat=%s type=%s)",
                    len(notes), plan.time_filter, plan.category_filter, plan.content_type)
        return RetrievalResult(notes=notes, fallback=len(notes) == 0)

    # Semantic path
    where = _build_chroma_where(plan)
    notes = storage.search(query, limit=plan.k, where=where)
    logger.info("Semantic retrieval: %d notes (intent=%s k=%d where=%s)",
                len(notes), plan.intent, plan.k, where)

    if notes:
        return RetrievalResult(notes=notes, fallback=False)

    # Nothing found with filters — retry without to surface closest notes
    logger.info("No results with filters, retrying without filters (fallback mode)")
    fallback_notes = storage.search(query, limit=2, where=None)
    return RetrievalResult(notes=fallback_notes, fallback=True)
