from pathlib import Path
from chromadb.utils.embedding_functions import (
    OpenAIEmbeddingFunction,
    SentenceTransformerEmbeddingFunction,
)

ROOT = Path(__file__).parent

# Dataset name → {notes path, eval_set path}
DATASETS = {
    "dataset1": {
        "notes": ROOT / "data/dataset1/notes.jsonl",
        "eval_set": ROOT / "data/dataset1/eval_set.jsonl",
    },
    "dataset2": {
        "notes": ROOT / "data/dataset2/notes2.jsonl",
        "eval_set": ROOT / "data/dataset2/eval_set2.jsonl",
    },
}

# Run-config YAML files (experiments/configs/*.yaml) are resolved against this
CONFIGS_DIR = ROOT / "configs"

# dataset2's notes carry a `days_ago` offset instead of an absolute date.
# Fixed reference point (dataset generated 2026-08-21) so time-filter grading
# stays reproducible regardless of when the eval is actually run.
DATASET2_ANCHOR_DATE = "2026-08-21"

# Embedding model name → ChromaDB embedding function (None = ChromaDB default)
EMBEDDING_MODELS = {
    "default": None,               # all-MiniLM-L6-v2, same as the main app
    "bge-large": SentenceTransformerEmbeddingFunction(model_name="BAAI/bge-large-en-v1.5"),
    "openai-3-small": OpenAIEmbeddingFunction(model_name="text-embedding-3-small", api_key_env_var="OPENAI_API_KEY"),
    "openai-3-large": OpenAIEmbeddingFunction(model_name="text-embedding-3-large", api_key_env_var="OPENAI_API_KEY"),
}

# Reranker name → cross-encoder model id (lazy-loaded in pipeline/rerank.py)
RERANKERS = {
    "cross-encoder-ms-marco": "cross-encoder/ms-marco-MiniLM-L-6-v2",
    "bge-reranker-base": "BAAI/bge-reranker-base",
    "bge-reranker-v2-m3": "BAAI/bge-reranker-v2-m3",
}

# Where generated indexes and results are stored
ARTIFACTS_DIR = ROOT / "artifacts"
INDEXES_DIR = ARTIFACTS_DIR / "indexes"
RESULTS_DIR = ARTIFACTS_DIR / "results"
