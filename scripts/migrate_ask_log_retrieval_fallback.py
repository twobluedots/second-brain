"""
One-time migration (2026-07-16): add retrieval_fallback column to ask_log.

The column was added to the CREATE TABLE statement on 2026-07-15, but
CREATE TABLE IF NOT EXISTS never alters an existing table — DBs that had
already created ask_log were silently failing every insert
("table ask_log has no column named retrieval_fallback" in app.log).

Run once from the project root: python scripts/migrate_ask_log_retrieval_fallback.py
Safe to re-run — skips if the column already exists.
"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import DB_PATH


def main():
    conn = sqlite3.connect(str(DB_PATH))
    try:
        columns = [row[1] for row in conn.execute("PRAGMA table_info(ask_log)")]
        if not columns:
            print(f"ask_log does not exist in {DB_PATH} — nothing to migrate (it will be created on next app start).")
            return
        if "retrieval_fallback" in columns:
            print("retrieval_fallback already present — nothing to do.")
            return
        conn.execute("ALTER TABLE ask_log ADD COLUMN retrieval_fallback INTEGER NOT NULL DEFAULT 0")
        conn.commit()
        count = conn.execute("SELECT COUNT(*) FROM ask_log").fetchone()[0]
        print(f"Added retrieval_fallback to ask_log in {DB_PATH} ({count} existing rows backfilled with 0).")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
