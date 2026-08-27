"""
One-time migration (2026-08-24): add tag column to search_log.

Part of the tag-search feature (docs/design/tag-search.md) — CREATE TABLE
IF NOT EXISTS never alters an existing table, so DBs created before this
migration need the column added explicitly (same lesson as the ask_log
migrations).

Run once from the project root: python scripts/migrate_search_log_tag.py
Safe to re-run — skips the column if it already exists.
"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import DB_PATH


def main():
    conn = sqlite3.connect(str(DB_PATH))
    try:
        columns = [row[1] for row in conn.execute("PRAGMA table_info(search_log)")]
        if not columns:
            print(f"search_log does not exist in {DB_PATH} — nothing to migrate (it will be created on next app start).")
            return

        if "tag" in columns:
            print("tag already present on search_log — nothing to do.")
            return

        conn.execute("ALTER TABLE search_log ADD COLUMN tag TEXT")
        conn.commit()
        count = conn.execute("SELECT COUNT(*) FROM search_log").fetchone()[0]
        print(f"Added tag to search_log in {DB_PATH} ({count} existing rows now have NULL for tag).")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
