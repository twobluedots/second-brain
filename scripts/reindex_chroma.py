#!/usr/bin/env python3
"""
Wipe and rebuild ChromaDB index from SQLite.

Run this after switching the embedding model — existing vectors have wrong
dimensions and must be regenerated.

Usage: uv run python scripts/reindex_chroma.py
"""

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import CHROMA_PATH
from src.storage.storage import Storage

chroma_path = Path(CHROMA_PATH)
if chroma_path.exists():
    shutil.rmtree(chroma_path)
    print(f"Deleted {chroma_path}")

print("Initialising storage and downloading embedding model (first run downloads ~1.3GB)...")
storage = Storage()
count = storage.reindex_all()
print(f"Done — re-indexed {count} entries with bge-large-en-v1.5")
