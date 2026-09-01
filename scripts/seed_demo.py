#!/usr/bin/env python3
"""
Build the demo store — a synthetic SQLite + ChromaDB seeded from
scripts/fixtures/demo_notes.jsonl, for README screenshots and a
"try it with sample data" path. No real notes involved.

Wipe-and-rebuild: safe to re-run any time the fixture or schema changes.

Usage:
    uv run python scripts/seed_demo.py

Then point the app at it (one-command shell prefix, nothing to unset after):
    SECOND_BRAIN_DB=data/demo/entries.db \\
    SECOND_BRAIN_CHROMA=data/demo/chroma_data \\
    uv run streamlit run ui/app.py
"""

import json
import shutil
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from chromadb.api.shared_system_client import SharedSystemClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import DEMO_CHROMA_PATH, DEMO_DB_PATH, EMBEDDING_MODEL
from src.logger import logger
from src.models.entry import Entry
from src.storage.storage import Storage

FIXTURE = Path(__file__).parent / "fixtures" / "demo_notes.jsonl"


def _iso(dt: datetime) -> str:
    """Match Storage._iso_now(): ISO 8601, UTC, Z suffix."""
    return dt.isoformat().replace("+00:00", "") + "Z"


def seed_demo(db_path, chroma_path, embedding_model: str = EMBEDDING_MODEL, fixture: Path = FIXTURE) -> int:
    """Build a fresh demo store at the given paths. Returns the entry count."""
    db_path, chroma_path = Path(db_path), Path(chroma_path)

    # Wipe any previous build so re-runs stay idempotent. clear_system_cache()
    # drops ChromaDB's process-wide client cache so a rebuilt path in the same
    # process (e.g. tests calling this twice) doesn't reopen a deleted store.
    if db_path.exists():
        db_path.unlink()
    if chroma_path.exists():
        shutil.rmtree(chroma_path)
    SharedSystemClient.clear_system_cache()

    notes = [json.loads(line) for line in fixture.read_text().splitlines() if line.strip()]

    storage = Storage(db_path=str(db_path), chroma_path=str(chroma_path), embedding_model=embedding_model)

    # Save through the normal path (lands at "now"), then backdate created_at
    # from each fixture row's days_ago. Categories come straight from the
    # fixture — no LLM call, so the build is deterministic and key-free.
    now = datetime.now(timezone.utc)
    backdated: dict[str, str] = {}
    for note in notes:
        entry = Entry(content=note["text"], content_type="text", category=note["category"])
        entry_id = storage.save(entry)
        storage.log_category_event(
            entry_id, ai_suggested=None, final_category=note["category"], event_type="seed"
        )
        backdated[entry_id] = _iso(now - timedelta(days=note.get("days_ago", 0)))

    with sqlite3.connect(str(db_path)) as conn:
        conn.executemany(
            "UPDATE entries SET created_at = ? WHERE id = ?",
            [(ts, entry_id) for entry_id, ts in backdated.items()],
        )
        conn.commit()

    # Rebuild ChromaDB from SQLite so vector metadata (created_at / created_at_ts)
    # matches the backdated rows.
    count = storage.reindex_all()
    logger.info("Seeded demo store: %d entries (db=%s, chroma=%s)", count, db_path, chroma_path)
    return count


if __name__ == "__main__":
    n = seed_demo(DEMO_DB_PATH, DEMO_CHROMA_PATH)
    print(f"Done — seeded {n} demo entries into {DEMO_DB_PATH}")
    print(
        f"Run: SECOND_BRAIN_DB={DEMO_DB_PATH} SECOND_BRAIN_CHROMA={DEMO_CHROMA_PATH} "
        f"uv run streamlit run ui/app.py"
    )
