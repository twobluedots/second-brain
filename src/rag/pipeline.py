"""
RAG pipeline — analyze → retrieve → generate.
Pure pipeline: no logging side effects here; AskService owns those.
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from src.rag.analyzer import analyze_query
from src.rag.generator import generate
from src.rag.retrieval import retrieve
from src.storage.storage import Storage


@dataclass
class AskResult:
    answer: Optional[str]          # None for browse intent (show notes directly)
    notes: List[Dict] = field(default_factory=list)
    fallback: bool = False         # True = weak/no match, retrieval retried unfiltered
    intent: str = "qa"
    # Provenance + stage latencies — logged to ask_log by AskService.
    # A None model where a stage ran means that stage fell back without an LLM.
    analyzer_model: Optional[str] = None
    generator_model: Optional[str] = None
    analyzer_ms: Optional[int] = None
    retrieval_ms: Optional[int] = None
    generation_ms: Optional[int] = None


def ask(query: str, storage: Storage) -> AskResult:
    """Run the full pipeline and return an AskResult the UI can render directly."""
    t0 = time.perf_counter()
    plan = analyze_query(query)
    analyzer_ms = round((time.perf_counter() - t0) * 1000)

    t0 = time.perf_counter()
    result = retrieve(query, plan, storage)
    retrieval_ms = round((time.perf_counter() - t0) * 1000)

    if plan.intent == "browse":
        return AskResult(
            answer=None, notes=result.notes, fallback=result.fallback, intent="browse",
            analyzer_model=plan.model, analyzer_ms=analyzer_ms, retrieval_ms=retrieval_ms,
        )

    t0 = time.perf_counter()
    answer, generator_model = generate(query, plan, result.notes)
    generation_ms = round((time.perf_counter() - t0) * 1000)

    return AskResult(
        answer=answer, notes=result.notes, fallback=result.fallback, intent=plan.intent,
        analyzer_model=plan.model, generator_model=generator_model,
        analyzer_ms=analyzer_ms, retrieval_ms=retrieval_ms, generation_ms=generation_ms,
    )
