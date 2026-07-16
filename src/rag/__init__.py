"""
RAG package — public API re-exports only; logic lives in named modules
(analyzer, retrieval, generator, pipeline, service).
"""

from src.rag.pipeline import AskResult, ask

__all__ = ["AskResult", "ask"]
