"""
Retrieval pipeline — takes a query and config, returns ranked note IDs.

Config keys used:
  dataset         str   which dataset to search (must exist in config.DATASETS)
  embedding_model str   which embedding model to use (must exist in config.EMBEDDING_MODELS)
  retriever       str   retrieval method: "vector" (only option for now)
  n_results       int   how many results to return (default 5)
"""

from experiments.pipeline.index import load_or_build


def retrieve(query: str, config: dict) -> list[str]:
    n = config.get("n_results", 5)
    retriever = config.get("retriever", "vector")

    if retriever == "vector":
        return _vector_retrieve(query, config, n)

    raise ValueError(f"Unknown retriever: {retriever!r}. Available: 'vector'")


def _vector_retrieve(query: str, config: dict, n: int) -> list[str]:
    collection = load_or_build(config)
    actual_n = min(n, collection.count())
    results = collection.query(query_texts=[query], n_results=actual_n)
    return results["ids"][0]
