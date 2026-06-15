#!/usr/bin/env python3
"""
M2.4 - Migrate category_events: was_overridden INTEGER → event_type TEXT

Renames the was_overridden column to event_type and converts values:
  0 → 'ai_assignment'
  1 → 'user_override'

SQLite doesn't support DROP/RENAME COLUMN directly, so this uses the
rename-table → create-new → copy → drop pattern.

Safe to run multiple times (checks for was_overridden before migrating).

Usage: uv run python scripts/migrate_m2_4_event_type.py
"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import DB_PATH


def migrate(db_path: str = DB_PATH) -> None:
    conn = sqlite3.connect(db_path)
    try:
        col_names = [r[1] for r in conn.execute("PRAGMA table_info(category_events)").fetchall()]

        if not col_names:
            print("category_events table does not exist — nothing to migrate.")
            return

        if "was_overridden" not in col_names:
            print("Already migrated — event_type column already present.")
            return

        print(f"Migrating category_events in {db_path}...")
        row_count = conn.execute("SELECT COUNT(*) FROM category_events").fetchone()[0]
        print(f"  {row_count} rows to migrate")

        conn.executescript("""
            ALTER TABLE category_events RENAME TO category_events_old;

            CREATE TABLE category_events (
                id TEXT PRIMARY KEY,
                entry_id TEXT NOT NULL,
                ai_suggested TEXT,
                final_category TEXT NOT NULL,
                event_type TEXT NOT NULL DEFAULT 'ai_assignment',
                created_at TEXT NOT NULL,
                FOREIGN KEY (entry_id) REFERENCES entries(id)
            );

            INSERT INTO category_events
            SELECT id, entry_id, ai_suggested, final_category,
                   CASE WHEN was_overridden=1 THEN 'user_override' ELSE 'ai_assignment' END,
                   created_at
            FROM category_events_old;

            DROP TABLE category_events_old;
        """)

        migrated = conn.execute("SELECT COUNT(*) FROM category_events").fetchone()[0]
        print(f"  Done — {migrated} rows migrated.")
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
