"""
RAG pipeline — single entry point for the Ask page.
"""

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
    fallback: bool = False         # True = weak match, UI should show a disclaimer
    intent: str = "qa"


def ask(query: str, storage: Storage) -> AskResult:
    """
    Full RAG pipeline: analyze → retrieve → generate.
    Returns an AskResult the UI can render directly.
    """
    plan = analyze_query(query)

    result = retrieve(query, plan, storage)

    if plan.intent == "browse":
        return AskResult(answer=None, notes=result.notes, fallback=result.fallback, intent="browse")

    answer = generate(query, plan, result.notes)
    return AskResult(answer=answer, notes=result.notes, fallback=result.fallback, intent=plan.intent)
