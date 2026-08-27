"""
Retrieval pipeline — takes a query and a collection, returns ranked note IDs.

`collection` is built once per run via `index.load_or_build(config)` and
passed in by the caller, so the index isn't reopened on every query.

Vector retrieval always runs first. If `config["reranker"]` is set, the
candidate set is then reordered by a cross-encoder (see pipeline/rerank.py)
before being returned — `note_texts` is only required in that case.

Config keys used:
  retriever       str   retrieval method: "vector" (only option for now)
  n_results       int   how many results to return (default 5)
  reranker        str   optional reranker name from config.RERANKERS

Vector-retrieval results are cached in-memory per (dataset, embedding_model,
retriever, n_results, query) — reranker-only sweeps (same candidates, different
reranker) hit cache instead of re-embedding/re-querying. Cache is process-lifetime
only, not persisted to disk.
"""

import chromadb

from experiments.pipeline.rerank import load_reranker, rerank as rerank_candidates

_retrieval_cache: dict[tuple, list[str]] = {}


def retrieve(
    query: str,
    config: dict,
    collection: chromadb.Collection,
    note_texts: dict[str, str] = None,
) -> list[str]:
    n = config.get("n_results", 5)
    retriever = config.get("retriever", "vector")

    cache_key = (config["dataset"], config["embedding_model"], retriever, n, query)
    candidate_ids = _retrieval_cache.get(cache_key)
    if candidate_ids is None:
        if retriever == "vector":
            candidate_ids = _vector_retrieve(query, collection, n)
        else:
            raise ValueError(f"Unknown retriever: {retriever!r}. Available: 'vector'")
        _retrieval_cache[cache_key] = candidate_ids

    reranker_name = config.get("reranker")
    if reranker_name:
        model = load_reranker(reranker_name)
        candidate_ids = rerank_candidates(query, candidate_ids, note_texts, model)

    return candidate_ids


def _vector_retrieve(query: str, collection: chromadb.Collection, n: int) -> list[str]:
    actual_n = min(n, collection.count())
    results = collection.query(query_texts=[query], n_results=actual_n)
    return results["ids"][0]
