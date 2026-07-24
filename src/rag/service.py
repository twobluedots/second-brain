"""
AskService — service layer for the Ask flow.
Peer of NoteService: NoteService owns the capture/CRUD lifecycle,
AskService owns question → answer. UI talks to services, never to storage.
"""


from src.logger import logger
from src.rag.pipeline import AskResult, ask
from src.storage.storage import Storage


class AskService:
    def __init__(self, storage: Storage):
        self.storage = storage

    def ask(self, query: str, input_type: str = "text") -> AskResult:
        """Run the RAG pipeline and log the interaction to ask_log.
        Failures are logged too (error row), then re-raised for the UI to handle."""
        try:
            result = ask(query, self.storage)
        except Exception as e:
            self.storage.log_ask_event(
                query=query, input_type=input_type, intent=None,
                retrieved_note_ids=[], answer=None, result_count=0,
                error=str(e),
            )
            raise

        self.storage.log_ask_event(
            query=query,
            input_type=input_type,
            intent=result.intent,
            time_filter=result.time_filter,
            category_filter=result.category_filter,
            k=result.k,
            retrieved_note_ids=[n.get("id") for n in result.notes],
            answer=result.answer,
            result_count=len(result.notes),
            analyzer_model=result.analyzer_model,
            generator_model=result.generator_model,
            analyzer_ms=result.analyzer_ms,
            retrieval_ms=result.retrieval_ms,
            generation_ms=result.generation_ms,
            retrieval_fallback=result.fallback,
        )
        logger.info("Ask logged: intent=%s results=%d (analyzer=%s, generator=%s)",
                    result.intent, len(result.notes), result.analyzer_model, result.generator_model)
        return result
