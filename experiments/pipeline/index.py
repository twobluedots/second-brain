"""
Build or load a ChromaDB index for a (dataset, embedding_model) pair.

Index path is derived from config plus a hash of notes.jsonl's content, so a
dataset edit always gets a fresh path (and rebuilds) instead of silently
reusing a stale index. Re-running with unchanged notes.jsonl reuses the
existing index without re-embedding.
"""

import json
from pathlib import Path
import chromadb
from experiments.config import DATASETS, EMBEDDING_MODELS, INDEXES_DIR
from experiments.utils import hash_file


def get_index_path(config: dict) -> Path:
    dataset = config["dataset"]
    embedding_model = config["embedding_model"]
    notes_hash = hash_file(DATASETS[dataset])
    return INDEXES_DIR / f"{dataset}__{notes_hash}__{embedding_model}"


def load_or_build(config: dict) -> chromadb.Collection:
    index_path = get_index_path(config)
    client = chromadb.PersistentClient(path=str(index_path))

    embedding_fn = EMBEDDING_MODELS[config["embedding_model"]]
    kwargs = {"name": "notes"}
    if embedding_fn is not None:
        kwargs["embedding_function"] = embedding_fn

    collection = client.get_or_create_collection(**kwargs)

    if collection.count() > 0:
        print(f"Index loaded: {index_path.name} ({collection.count()} notes)")
        return collection

    # Index doesn't exist yet — build it
    print(f"Building index: {index_path.name} ...")
    notes_path = DATASETS[config["dataset"]]
    notes = [json.loads(line) for line in open(notes_path) if line.strip()]

    collection.add(
        ids=[n["id"] for n in notes],
        documents=[n["text"] for n in notes],
        metadatas=[{"category": n["category"], "type": n["type"]} for n in notes],
    )
    print(f"  Indexed {collection.count()} notes")
    return collection
