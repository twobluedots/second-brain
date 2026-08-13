"""
Reranking — reorders a candidate set of note IDs by a (query, note) relevance score.

Cross-encoder scores the query and note text jointly (unlike the bi-encoder used for
retrieval), so it only runs over the small candidate set retrieval already narrowed
down to, not the whole corpus. Model is loaded once per name and reused across queries.
"""

from functools import lru_cache

from sentence_transformers import CrossEncoder

from experiments.config import RERANKERS


@lru_cache(maxsize=None)
def load_reranker(name: str) -> CrossEncoder:
    return CrossEncoder(RERANKERS[name])


def rerank(query: str, candidate_ids: list[str], note_texts: dict[str, str], model: CrossEncoder) -> list[str]:
    pairs = [(query, note_texts[cid]) for cid in candidate_ids]
    scores = model.predict(pairs)
    ranked = sorted(zip(candidate_ids, scores), key=lambda x: x[1], reverse=True)
    return [cid for cid, _ in ranked]
