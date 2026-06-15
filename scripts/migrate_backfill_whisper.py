#!/usr/bin/env python3
"""
Migration: backfill Whisper transcriptions for voice entries with description=NULL.

For voice entries where description IS NULL:
  1. Move content → description (existing content was user-typed context, not a transcription)
  2. Run Whisper on the audio file → set result as new content

Usage: uv run python scripts/migrate_backfill_whisper.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.storage.storage import Storage
from src.processing import load_model, process_voice_note


def main():
    print("Whisper backfill migration — voice entries with description=NULL")
    print("=" * 60)

    storage = Storage()

    with storage._connect() as conn:
        rows = conn.execute(
            """
            SELECT id, content, file_path
            FROM entries
            WHERE content_type = 'voice'
              AND description IS NULL
              AND deleted_at IS NULL
            """
        ).fetchall()

    entries = [dict(row) for row in rows]
    print(f"Found {len(entries)} entries to backfill\n")

    if not entries:
        print("Nothing to do.")
        return

    print("Loading Whisper model...")
    model = load_model("base")
    print()

    stats = {"updated": 0, "whisper_failed": 0, "file_missing": 0}

    for entry in entries:
        entry_id = entry["id"]
        old_content = entry["content"]
        file_path = entry["file_path"]

        print(f"[{entry_id[:8]}] file={file_path}")
        print(f"  old content (context): {repr(old_content)}")

        if not file_path or not Path(file_path).exists():
            print(f"  → SKIP: audio file not found\n")
            stats["file_missing"] += 1
            continue

        transcription = None
        try:
            transcription = process_voice_note(file_path, model)
            print(f"  → transcription: {repr(transcription)}")
        except Exception as e:
            print(f"  → Whisper failed: {e}")
            stats["whisper_failed"] += 1

        storage.update(entry_id, {
            "description": old_content,
            "content": transcription,
        })
        print(f"  → saved: description={repr(old_content)}, content={repr(transcription)}\n")
        stats["updated"] += 1

    print("=" * 60)
    print(f"updated:        {stats['updated']}")
    print(f"file missing:   {stats['file_missing']}")
    print(f"whisper failed: {stats['whisper_failed']}")


if __name__ == "__main__":
    main()
