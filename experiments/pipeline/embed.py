"""
Embedding backends for the chunking experiment.

Separate from experiments/config.py's EMBEDDING_MODELS — those are ChromaDB
embedding functions used to index whole notes for retrieval. These return raw
vectors + usage/cost, because chunking needs to embed individual sentences,
not whole notes, and needs cost visibility per call.
"""

from dataclasses import dataclass
from functools import lru_cache
from typing import List, Tuple

import numpy as np

# Pricing is approximate (USD per 1M tokens) — verify at the provider's current
# pricing page before trusting cost totals for anything beyond a rough estimate.
OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
OPENAI_EMBEDDING_PRICE_PER_1M = 0.02


@dataclass
class Usage:
    provider: str = "local"
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


@lru_cache(maxsize=1)
def _minilm_model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer("all-MiniLM-L6-v2")


def embed_minilm(texts: List[str]) -> Tuple[np.ndarray, Usage]:
    vectors = _minilm_model().encode(texts, convert_to_numpy=True)
    return vectors, Usage(provider="local", model="all-MiniLM-L6-v2")


def embed_minilm_token_level(text: str):
    """
    Token-level (pre-pooling) embeddings for the whole note, plus char offsets
    for each token — what late chunking needs and hosted embedding APIs don't
    expose (they only return the final pooled vector).

    Returns (token_embeddings: np.ndarray[seq_len, dim], offsets: list[(start, end)]).
    """
    import torch

    model = _minilm_model()
    tokenizer = model.tokenizer
    encoded = tokenizer(text, return_offsets_mapping=True, return_tensors="pt", truncation=True)
    offsets = encoded["offset_mapping"][0].tolist()
    model_inputs = {k: v.to(model.device) for k, v in encoded.items() if k != "offset_mapping"}

    with torch.no_grad():
        token_embeddings = model[0].auto_model(**model_inputs)[0][0]  # (seq_len, dim)

    return token_embeddings.cpu().numpy(), offsets


def embed_openai(texts: List[str]) -> Tuple[np.ndarray, Usage]:
    from openai import OpenAI

    client = OpenAI()
    response = client.embeddings.create(model=OPENAI_EMBEDDING_MODEL, input=texts)
    vectors = np.array([d.embedding for d in response.data])
    tokens = response.usage.total_tokens
    cost = tokens / 1_000_000 * OPENAI_EMBEDDING_PRICE_PER_1M
    usage = Usage(provider="openai", model=OPENAI_EMBEDDING_MODEL, input_tokens=tokens, cost_usd=cost)
    return vectors, usage


EMBEDDERS = {
    "minilm": embed_minilm,
    "openai": embed_openai,
}
