#!/usr/bin/env python3
"""
M2.5 - Backfill categories for entries that have no category set.

Covers text and voice entries only — images are skipped (description too
sparse for reliable categorization).

Safe to run multiple times — only touches entries where category IS NULL.

Usage: uv run python scripts/backfill_categories.py [--dry-run]
"""

import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import DB_PATH
from src.categorize import categorize


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "") + "Z"


def backfill(db_path: str = DB_PATH, dry_run: bool = False) -> None:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    try:
        rows = conn.execute(
            """SELECT id, content, description, content_type
               FROM entries
               WHERE category IS NULL AND deleted_at IS NULL AND content_type != 'image'"""
        ).fetchall()

        skipped = conn.execute(
            "SELECT COUNT(*) FROM entries WHERE category IS NULL AND deleted_at IS NULL AND content_type = 'image'"
        ).fetchone()[0]

        if not rows:
            print(f"No uncategorized text/voice entries found. ({skipped} image entries skipped.)")
            return

        print(f"Found {len(rows)} entries to categorize ({skipped} image entries skipped).{' (dry run)' if dry_run else ''}\n")

        updated = 0
        for row in rows:
            entry_id = row["id"]
            text = "\n".join(filter(None, [row["content"], row["description"]]))
            category = categorize(text)
            print(f"  [{row['content_type']:5}] {entry_id[:8]}… → {category:12}  {text[:60].strip()!r}")

            if not dry_run:
                now = iso_now()
                conn.execute(
                    "UPDATE entries SET category = ?, modified_at = ? WHERE id = ?",
                    (category, now, entry_id),
                )
                conn.execute(
                    """INSERT INTO category_events
                       (id, entry_id, ai_suggested, final_category, event_type, created_at)
                       VALUES (?, ?, ?, ?, 'ai_assignment', ?)""",
                    (str(uuid.uuid4()), entry_id, category, category, now),
                )
                updated += 1

        if not dry_run:
            conn.commit()
            print(f"\nDone — {updated} entries categorized.")
        else:
            print("\nDry run complete — no changes written.")

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    backfill(dry_run=dry_run)
