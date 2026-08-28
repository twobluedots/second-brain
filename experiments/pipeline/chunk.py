"""
Semantic chunking strategies — experimental comparison, not wired into the app
or the retrieval eval runner (see experiments/chunking_experiment.py).

Four methods:
  breakpoint    — embed sentences in isolation, split where similarity to the
                  next sentence drops past a percentile threshold. The
                  "classic" semantic chunker.
  clustering    — embed sentences, grow a running chunk while each new
                  sentence stays similar to the chunk's centroid; start a new
                  chunk when it doesn't. Same embeddings as breakpoint, a
                  different boundary rule (centroid vs. adjacent-pair).
  llm_boundary  — ask an LLM to mark topic shifts directly, no embeddings.
  late          — embed the WHOLE note first (so every token's embedding
                  carries full-note context), then pool per sentence and
                  apply the same breakpoint rule as `breakpoint`. Only
                  possible with a local model — hosted embedding APIs never
                  expose token-level (pre-pooling) embeddings.
"""

import re
from dataclasses import dataclass, field
from typing import Callable, List, Tuple

import numpy as np

from experiments.pipeline.embed import Usage, embed_minilm_token_level

# Pricing is approximate (USD per 1M tokens) — verify at the provider's current
# pricing page before trusting cost totals for anything beyond a rough estimate.
# The Haiku 4.5 figure in particular is a placeholder based on prior Haiku
# generations; confirm before relying on it.
OPENAI_CHAT_MODEL = "gpt-4o-mini"
OPENAI_CHAT_PRICE_PER_1M = {"input": 0.15, "output": 0.60}
ANTHROPIC_CHAT_MODEL = "claude-haiku-4-5-20251001"
ANTHROPIC_CHAT_PRICE_PER_1M = {"input": 0.80, "output": 4.00}  # PLACEHOLDER — verify

EmbedFn = Callable[[List[str]], Tuple[np.ndarray, Usage]]

SENTENCE_SPLIT_RE = re.compile(r'(?<=[.!?])\s+(?=[A-Z0-9"\'])')


@dataclass
class ChunkResult:
    chunks: List[str]
    usage: List[Usage] = field(default_factory=list)


def split_sentences(text: str) -> List[str]:
    """
    Naive regex sentence splitter — splits on .!? followed by whitespace and a
    capital/digit/quote. No new dependency (no spaCy/nltk). Handles ellipses
    fine (no whitespace inside '...' so it never splits mid-ellipsis) and
    markdown list items reasonably. Struggles with abbreviations. Good enough
    for a 10-note visual comparison — revisit with a real tokenizer if the
    output looks messy.
    """
    text = text.strip()
    if not text:
        return []
    sentences = SENTENCE_SPLIT_RE.split(text)
    return [s.strip() for s in sentences if s.strip()]


def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))


def _merge_by_breakpoint(sentences: List[str], vectors: np.ndarray, percentile: float) -> List[str]:
    """Shared boundary rule for `breakpoint` and `late`: cut where the distance
    to the next sentence exceeds the Nth percentile of all distances in this note."""
    if len(sentences) <= 1:
        return sentences
    distances = [1 - _cosine_sim(vectors[i], vectors[i + 1]) for i in range(len(vectors) - 1)]
    threshold = float(np.percentile(distances, percentile))

    chunks, current = [], [sentences[0]]
    for i, d in enumerate(distances):
        if d > threshold:
            chunks.append(" ".join(current))
            current = [sentences[i + 1]]
        else:
            current.append(sentences[i + 1])
    chunks.append(" ".join(current))
    return chunks


def chunk_breakpoint(text: str, embed_fn: EmbedFn, percentile: float = 80) -> ChunkResult:
    sentences = split_sentences(text)
    if len(sentences) <= 1:
        return ChunkResult(chunks=[text])
    vectors, usage = embed_fn(sentences)
    chunks = _merge_by_breakpoint(sentences, vectors, percentile)
    return ChunkResult(chunks=chunks, usage=[usage])


def chunk_clustering(text: str, embed_fn: EmbedFn, similarity_threshold: float = 0.4) -> ChunkResult:
    sentences = split_sentences(text)
    if len(sentences) <= 1:
        return ChunkResult(chunks=[text])
    vectors, usage = embed_fn(sentences)

    chunks, current_sents, current_vecs = [], [sentences[0]], [vectors[0]]
    for sent, vec in zip(sentences[1:], vectors[1:]):
        centroid = np.mean(current_vecs, axis=0)
        if _cosine_sim(vec, centroid) >= similarity_threshold:
            current_sents.append(sent)
            current_vecs.append(vec)
        else:
            chunks.append(" ".join(current_sents))
            current_sents, current_vecs = [sent], [vec]
    chunks.append(" ".join(current_sents))
    return ChunkResult(chunks=chunks, usage=[usage])


LLM_BOUNDARY_PROMPT = (
    "Split the following personal note into topically coherent segments.\n"
    "Insert the marker ||| at each point where the topic shifts.\n"
    "Return the text verbatim otherwise — do not paraphrase, summarize, or drop anything.\n\n"
    "Note:\n{text}"
)


def chunk_llm_boundary(text: str, provider: str = "anthropic") -> ChunkResult:
    prompt = LLM_BOUNDARY_PROMPT.format(text=text)

    if provider == "anthropic":
        from anthropic import Anthropic
        response = Anthropic().messages.create(
            model=ANTHROPIC_CHAT_MODEL,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        marked = response.content[0].text
        in_tok, out_tok = response.usage.input_tokens, response.usage.output_tokens
        cost = (in_tok * ANTHROPIC_CHAT_PRICE_PER_1M["input"] + out_tok * ANTHROPIC_CHAT_PRICE_PER_1M["output"]) / 1_000_000
        usage = Usage(provider="anthropic", model=ANTHROPIC_CHAT_MODEL, input_tokens=in_tok, output_tokens=out_tok, cost_usd=cost)

    elif provider == "openai":
        from openai import OpenAI
        response = OpenAI().chat.completions.create(
            model=OPENAI_CHAT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2048,
            temperature=0,
        )
        marked = response.choices[0].message.content
        in_tok, out_tok = response.usage.prompt_tokens, response.usage.completion_tokens
        cost = (in_tok * OPENAI_CHAT_PRICE_PER_1M["input"] + out_tok * OPENAI_CHAT_PRICE_PER_1M["output"]) / 1_000_000
        usage = Usage(provider="openai", model=OPENAI_CHAT_MODEL, input_tokens=in_tok, output_tokens=out_tok, cost_usd=cost)

    else:
        raise ValueError(f"Unknown provider: {provider!r}. Use 'anthropic' or 'openai'.")

    chunks = [c.strip() for c in marked.split("|||") if c.strip()]
    return ChunkResult(chunks=chunks or [text], usage=[usage])


def chunk_late(text: str, percentile: float = 80) -> ChunkResult:
    """MiniLM only — see module docstring for why hosted APIs can't do this."""
    sentences = split_sentences(text)
    if len(sentences) <= 1:
        return ChunkResult(chunks=[text])

    token_embeddings, offsets = embed_minilm_token_level(text)

    sentence_vectors = []
    cursor = 0
    for sent in sentences:
        start = text.index(sent, cursor)
        end = start + len(sent)
        cursor = end
        idxs = [i for i, (s, e) in enumerate(offsets) if s < end and e > start and not (s == 0 and e == 0)]
        pooled = token_embeddings[idxs].mean(axis=0) if idxs else token_embeddings.mean(axis=0)
        sentence_vectors.append(pooled)

    vectors = np.array(sentence_vectors)
    chunks = _merge_by_breakpoint(sentences, vectors, percentile)
    usage = Usage(provider="local", model="all-MiniLM-L6-v2 (token-level)")
    return ChunkResult(chunks=chunks, usage=[usage])
