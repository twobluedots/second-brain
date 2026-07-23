"""
One-time migration (2026-07-21): add time_filter, category_filter, k
columns to ask_log.

These were part of the originally agreed ask_log schema (spec decision,
2026-07-13) but were missed from the initial CREATE TABLE — CREATE TABLE
IF NOT EXISTS never alters an existing table, so DBs created before this
migration need these columns added explicitly (same lesson as the
retrieval_fallback migration).

Run once from the project root: python scripts/migrate_ask_log_time_category_k.py
Safe to re-run — skips columns that already exist.
"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import DB_PATH

NEW_COLUMNS = [
    ("time_filter", "TEXT"),
    ("category_filter", "TEXT"),
    ("k", "INTEGER"),
]


def main():
    conn = sqlite3.connect(str(DB_PATH))
    try:
        columns = [row[1] for row in conn.execute("PRAGMA table_info(ask_log)")]
        if not columns:
            print(f"ask_log does not exist in {DB_PATH} — nothing to migrate (it will be created on next app start).")
            return

        added = []
        for name, sql_type in NEW_COLUMNS:
            if name in columns:
                continue
            conn.execute(f"ALTER TABLE ask_log ADD COLUMN {name} {sql_type}")
            added.append(name)

        if not added:
            print("time_filter, category_filter, k already present — nothing to do.")
            return

        conn.commit()
        count = conn.execute("SELECT COUNT(*) FROM ask_log").fetchone()[0]
        print(f"Added {', '.join(added)} to ask_log in {DB_PATH} ({count} existing rows now have NULL for the new columns).")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
