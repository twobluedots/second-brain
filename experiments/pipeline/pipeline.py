"""
Retrieval pipeline — takes a query and a collection, returns ranked note IDs.

`collection` is built once per run via `index.load_or_build(config)` and
passed in by the caller, so the index isn't reopened on every query.

Config keys used:
  retriever       str   retrieval method: "vector" (only option for now)
  n_results       int   how many results to return (default 5)
"""

import chromadb


def retrieve(query: str, config: dict, collection: chromadb.Collection) -> list[str]:
    n = config.get("n_results", 5)
    retriever = config.get("retriever", "vector")

    if retriever == "vector":
        return _vector_retrieve(query, collection, n)

    raise ValueError(f"Unknown retriever: {retriever!r}. Available: 'vector'")


def _vector_retrieve(query: str, collection: chromadb.Collection, n: int) -> list[str]:
    actual_n = min(n, collection.count())
    results = collection.query(query_texts=[query], n_results=actual_n)
    return results["ids"][0]
