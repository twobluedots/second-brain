from pathlib import Path
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

ROOT = Path(__file__).parent

# Dataset name → notes.jsonl path
DATASETS = {
    "dataset1": ROOT / "data/dataset1/notes.jsonl",
}

# Embedding model name → ChromaDB embedding function (None = ChromaDB default)
EMBEDDING_MODELS = {
    "default": None,               # all-MiniLM-L6-v2, same as the main app
    "bge-large": SentenceTransformerEmbeddingFunction(model_name="BAAI/bge-large-en-v1.5"),
    # "openai_small": ...,         # add when OpenAI key is available
}

# Where generated indexes and results are stored
ARTIFACTS_DIR = ROOT / "artifacts"
INDEXES_DIR = ARTIFACTS_DIR / "indexes"
RESULTS_DIR = ARTIFACTS_DIR / "results"
