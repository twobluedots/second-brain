"""
Storage layer for second-brain.
Manages both SQLite (source of truth) and ChromaDB (search index).
All methods return dict or list[dict], never raw Row objects.
"""

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Optional, List, Dict
import uuid

from config import DB_PATH, CHROMA_PATH, DEFAULT_CATEGORIES, DEFAULT_SEARCH_LIMIT, EMBEDDING_MODEL, BGE_QUERY_INSTRUCTION
from src.logger import logger
from src.models import Entry


class Storage:
    """
    Unified storage interface for entries.
    - SQLite: structured data (source of truth)
    - ChromaDB: semantic search index
    """

    def __init__(self, db_path=DB_PATH, chroma_path=CHROMA_PATH):
        self.db_path = Path(db_path)
        self.chroma_path = Path(chroma_path)

        # Ensure directories exist
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.chroma_path.mkdir(parents=True, exist_ok=True)

        # Initialize ChromaDB
        self.chroma = chromadb.PersistentClient(path=str(self.chroma_path))
        self._ef = SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)
        self.collection = self.chroma.get_or_create_collection(
            name="entries",
            embedding_function=self._ef
        )

        # Initialize SQLite
        self._init_db()
        self._migrate_chroma_timestamps()
        logger.info("Storage initialised (db=%s, chroma=%s)", self.db_path, self.chroma_path)

    # ============================================================================
    # HELPER METHODS
    # ============================================================================

    @contextmanager
    def _connect(self):
        """Context manager for SQLite connections with automatic commit/rollback."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _dict(self, row) -> Optional[Dict]:
        """Convert sqlite3.Row to dict for UI consumption."""
        return dict(row) if row else None

    def _iso_now(self) -> str:
        """Return current time as ISO 8601 with Z suffix (UTC)."""
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "") + "Z"

    def _active_only(self, query: str) -> str:
        """Insert soft-delete filter into WHERE clause before ORDER BY/LIMIT."""
        # Handle queries with ORDER BY or LIMIT by inserting WHERE before them
        if "WHERE" in query:
            # Already has WHERE, add AND
            # Find ORDER BY or LIMIT to insert before it
            for keyword in [" ORDER BY", " LIMIT", " GROUP BY"]:
                if keyword in query:
                    return query.replace(keyword, f" AND deleted_at IS NULL{keyword}")
            # No ORDER/LIMIT/GROUP, just append AND
            return query + " AND deleted_at IS NULL"
        else:
            # No WHERE, add it
            for keyword in [" ORDER BY", " LIMIT", " GROUP BY"]:
                if keyword in query:
                    return query.replace(keyword, f" WHERE deleted_at IS NULL{keyword}")
            # No ORDER/LIMIT/GROUP, just append WHERE
            return query + " WHERE deleted_at IS NULL"

    # ============================================================================
    # DATABASE INITIALIZATION
    # ============================================================================

    def _init_db(self):
        """Initialize SQLite schema and populate default categories."""
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS entries (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    description TEXT,
                    content_type TEXT NOT NULL DEFAULT 'text',
                    category TEXT,
                    tags TEXT,
                    file_path TEXT,
                    user_id TEXT DEFAULT 'default',
                    created_at TEXT NOT NULL,
                    modified_at TEXT,
                    deleted_at TEXT
                );
                
                CREATE TABLE IF NOT EXISTS categories (
                    name TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL
                );
                
                CREATE TABLE IF NOT EXISTS category_events (
                    id TEXT PRIMARY KEY,
                    entry_id TEXT NOT NULL,
                    ai_suggested TEXT,
                    final_category TEXT NOT NULL,
                    event_type TEXT NOT NULL DEFAULT 'ai_assignment',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (entry_id) REFERENCES entries(id)
                );

                CREATE TABLE IF NOT EXISTS search_log (
                    id TEXT PRIMARY KEY,
                    query TEXT,
                    content_type TEXT,
                    date_preset TEXT,
                    result_count INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_entries_created_at ON entries(created_at);
                CREATE INDEX IF NOT EXISTS idx_entries_deleted_at ON entries(deleted_at);
                CREATE INDEX IF NOT EXISTS idx_entries_category ON entries(category);
                CREATE INDEX IF NOT EXISTS idx_entries_content_type ON entries(content_type);
            """)
            
            # Populate default categories (INSERT OR IGNORE, so safe on repeated calls)
            for cat in DEFAULT_CATEGORIES:
                conn.execute(
                    "INSERT OR IGNORE INTO categories (name, created_at) VALUES (?, ?)",
                    (cat, self._iso_now())
                )
        logger.info("SQLite schema initialised (db=%s)", self.db_path)

    def _migrate_chroma_timestamps(self):
        """Backfill created_at_ts (int) for existing ChromaDB documents that don't have it."""
        try:
            existing = self.collection.get(include=["metadatas"])
            needs_update = [
                (id_, meta)
                for id_, meta in zip(existing["ids"], existing["metadatas"])
                if "created_at_ts" not in meta and meta.get("created_at")
            ]
            for id_, meta in needs_update:
                ts = int(datetime.fromisoformat(meta["created_at"].replace("Z", "+00:00")).timestamp())
                self.collection.update(ids=[id_], metadatas=[{**meta, "created_at_ts": ts}])
            if needs_update:
                logger.info("Migrated created_at_ts for %d ChromaDB documents", len(needs_update))
        except Exception as e:
            logger.warning("ChromaDB timestamp migration failed: %s", e)

    # ============================================================================
    # WRITE OPERATIONS
    # ============================================================================

    def save(self, entry: Entry) -> str:
        """
        Save entry to both SQLite and ChromaDB.

        Returns:
            entry_id (generated)
        """
        entry_id = str(uuid.uuid4())
        tags = json.dumps(entry.tags) if entry.tags else None
        now = self._iso_now()

        # Save to SQLite
        with self._connect() as conn:
            try:
                conn.execute(
                    """INSERT INTO entries
                       (id, content, description, content_type, category, tags, file_path, created_at, user_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'default')""",
                    (entry_id, entry.content, entry.description, entry.content_type,
                     entry.category, tags, entry.file_path, now)
                )
            except sqlite3.IntegrityError as e:
                logger.error("Save failed — duplicate entry %s: %s", entry_id, e)
                raise ValueError(f"Entry {entry_id} already exists") from e

        logger.info("Saved entry %s (type=%s)", entry_id, entry.content_type)

        # Save to ChromaDB — combine content + description for richer search
        searchable_text = "\n".join(filter(None, [entry.content, entry.description]))
        if searchable_text:
            try:
                self.collection.add(
                    ids=[entry_id],
                    documents=[searchable_text],
                    metadatas=[{
                        "content_type": entry.content_type,
                        "created_at": now,
                        "created_at_ts": int(datetime.fromisoformat(now.replace("Z", "+00:00")).timestamp()),
                        "category": entry.category or "uncategorized"
                    }]
                )
            except Exception as e:
                logger.warning("ChromaDB index failed for %s: %s", entry_id, e)

        return entry_id

    def log_category_event(self, entry_id: str, ai_suggested: Optional[str], final_category: str, event_type: str = 'ai_assignment') -> None:
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO category_events (id, entry_id, ai_suggested, final_category, event_type, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (str(uuid.uuid4()), entry_id, ai_suggested, final_category, event_type, self._iso_now())
            )

    def update(self, entry_id: str, fields: Dict) -> None:
        """
        Update entry fields in SQLite and refresh ChromaDB if content changed.
        Always sets modified_at timestamp.
        
        Args:
            entry_id: ID of entry to update
            fields: Dict of fields to update (e.g., {"category": "mood", "content": "new text"})
        """
        if not fields:
            return
        
        fields["modified_at"] = self._iso_now()
        
        # Build SQL update
        set_clause = ", ".join([f"{key} = ?" for key in fields.keys()])
        values = list(fields.values()) + [entry_id]
        
        with self._connect() as conn:
            conn.execute(
                f"UPDATE entries SET {set_clause} WHERE id = ? AND deleted_at IS NULL",
                values
            )
        logger.info("Updated entry %s (fields=%s)", entry_id, list(fields.keys()))

        # If content updated, refresh ChromaDB
        if "content" in fields:
            entry = self.get_by_id(entry_id)
            if entry:
                try:
                    self.collection.update(
                        ids=[entry_id],
                        documents=[fields["content"]],
                        metadatas=[{
                            "content_type": entry.get("content_type", "text"),
                            "created_at": entry.get("created_at"),
                            "category": entry.get("category", "uncategorized")
                        }]
                    )
                except Exception as e:
                    logger.warning("ChromaDB update failed for %s: %s", entry_id, e)

    def delete(self, entry_id: str) -> None:
        """
        Soft delete: mark entry as deleted in both stores.
        """
        now = self._iso_now()
        
        # Mark as deleted in SQLite
        with self._connect() as conn:
            conn.execute(
                "UPDATE entries SET deleted_at = ? WHERE id = ?",
                (now, entry_id)
            )
        logger.info("Deleted entry %s", entry_id)

        # Remove from ChromaDB
        try:
            self.collection.delete(ids=[entry_id])
        except Exception as e:
            logger.warning("ChromaDB delete failed for %s: %s", entry_id, e)

    # ============================================================================
    # READ OPERATIONS (Single/Multiple)
    # ============================================================================

    def get_by_id(self, entry_id: str) -> Optional[Dict]:
        """Get single entry by ID (active entries only)."""
        with self._connect() as conn:
            row = conn.execute(
                self._active_only("SELECT * FROM entries WHERE id = ?"),
                (entry_id,)
            ).fetchone()
        
        if row:
            entry = self._dict(row)
            # Parse tags from JSON
            if entry.get("tags"):
                entry["tags"] = json.loads(entry["tags"])
            return entry
        return None

    def get_recent(self, limit: int = 10) -> List[Dict]:
        """Get most recent active entries."""
        with self._connect() as conn:
            rows = conn.execute(
                self._active_only(
                    "SELECT * FROM entries ORDER BY created_at DESC LIMIT ?"
                ),
                (limit,)
            ).fetchall()
        
        return [self._parse_entry(self._dict(row)) for row in rows]

    def get_by_type(self, content_type: str, limit: int = 10) -> List[Dict]:
        """Get entries of specific type (active only)."""
        with self._connect() as conn:
            rows = conn.execute(
                self._active_only(
                    "SELECT * FROM entries WHERE content_type = ? ORDER BY created_at DESC LIMIT ?"
                ),
                (content_type, limit)
            ).fetchall()
        
        return [self._parse_entry(self._dict(row)) for row in rows]

    def get_by_category(self, category: str, limit: int = 10) -> List[Dict]:
        """Get entries in specific category (active only)."""
        with self._connect() as conn:
            rows = conn.execute(
                self._active_only(
                    "SELECT * FROM entries WHERE category = ? ORDER BY created_at DESC LIMIT ?"
                ),
                (category, limit)
            ).fetchall()
        
        return [self._parse_entry(self._dict(row)) for row in rows]

    def get_by_date_range(self, start: str, end: str) -> List[Dict]:
        """
        Get entries between two ISO 8601 timestamps (active only).
        
        Args:
            start: ISO 8601 timestamp (e.g., "2026-05-12T00:00:00Z")
            end: ISO 8601 timestamp (e.g., "2026-05-12T23:59:59Z")
        """
        with self._connect() as conn:
            rows = conn.execute(
                self._active_only(
                    "SELECT * FROM entries WHERE created_at BETWEEN ? AND ? ORDER BY created_at DESC"
                ),
                (start, end)
            ).fetchall()
        
        return [self._parse_entry(self._dict(row)) for row in rows]

    def _parse_entry(self, entry: Dict) -> Dict:
        """Helper to parse JSON fields in entry dict."""
        if entry and entry.get("tags"):
            entry["tags"] = json.loads(entry["tags"])
        return entry

    def get_entries(self, content_type: Optional[str] = None, date_from: Optional[str] = None, category: Optional[str] = None, limit: int = 50) -> List[Dict]:
        """SQLite-only retrieval with optional filters. Used when there is no text query for vector search."""
        clauses = ["deleted_at IS NULL"]
        params: list = []
        if content_type:
            clauses.append("content_type = ?")
            params.append(content_type)
        if date_from:
            clauses.append("created_at >= ?")
            params.append(date_from)
        if category:
            clauses.append("category = ?")
            params.append(category)
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM entries WHERE {' AND '.join(clauses)} ORDER BY created_at DESC LIMIT ?",
                params
            ).fetchall()
        return [self._parse_entry(self._dict(row)) for row in rows]

    # ============================================================================
    # CATEGORY OPERATIONS
    # ============================================================================

    def get_categories(self) -> List[str]:
        """Get all categories."""
        with self._connect() as conn:
            rows = conn.execute("SELECT name FROM categories ORDER BY name").fetchall()
        return [row[0] for row in rows]

    def add_category(self, name: str) -> bool:
        """
        Add new category.
        
        Returns:
            True if added, False if already exists
        """
        try:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO categories (name, created_at) VALUES (?, ?)",
                    (name, self._iso_now())
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def get_category_counts(self) -> Dict[str, int]:
        """Get count of active entries per category."""
        with self._connect() as conn:
            rows = conn.execute(
                self._active_only(
                    "SELECT category, COUNT(*) as count FROM entries GROUP BY category"
                )
            ).fetchall()
        
        return {row[0] or "uncategorized": row[1] for row in rows}

    # ============================================================================
    # SEARCH OPERATIONS
    # ============================================================================

    def log_search(self, query: Optional[str], content_type: Optional[str], date_preset: Optional[str], result_count: int) -> None:
        """Log a search event — query text nullable (filter-only searches have no text)."""
        try:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO search_log (id, query, content_type, date_preset, result_count, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (str(uuid.uuid4()), query or None, content_type, date_preset, result_count, self._iso_now())
                )
        except Exception as e:
            logger.warning("Search logging failed: %s", e)

    def search(self, query: str, limit: int = DEFAULT_SEARCH_LIMIT, where: Optional[Dict] = None) -> List[Dict]:
        """
        Semantic search across entries using ChromaDB.
        Returns structured results with full entry data from SQLite.

        Args:
            query: Search query string
            limit: Max results to return
            where: Optional ChromaDB metadata filter (e.g. content_type, created_at range)

        Returns:
            List of entry dicts, ordered by relevance
        """
        actual_limit = min(limit, self.collection.count())
        if actual_limit == 0:
            return []
        try:
            kwargs: Dict = {"query_texts": [BGE_QUERY_INSTRUCTION + query], "n_results": actual_limit}
            if where:
                kwargs["where"] = where
            results = self.collection.query(**kwargs)
        except Exception as e:
            logger.error("ChromaDB search failed: %s", e)
            raise
        
        if not results or not results["ids"] or not results["ids"][0]:
            return []

        # Fetch full entries from SQLite using IDs from ChromaDB
        entry_ids = results["ids"][0]
        entries = []
        for entry_id in entry_ids:
            entry = self.get_by_id(entry_id)
            if entry:
                entries.append(entry)

        return entries

    def reindex_all(self) -> int:
        """Wipe ChromaDB collection and re-index all active entries from SQLite."""
        try:
            self.chroma.delete_collection(name="entries")
        except Exception:
            pass
        self.collection = self.chroma.create_collection(
            name="entries",
            embedding_function=self._ef
        )

        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM entries WHERE deleted_at IS NULL"
            ).fetchall()

        count = 0
        for row in rows:
            entry = self._parse_entry(self._dict(row))
            searchable_text = "\n".join(filter(None, [entry.get("content"), entry.get("description")]))
            if not searchable_text:
                continue
            created_at = entry.get("created_at", self._iso_now())
            try:
                ts = int(datetime.fromisoformat(created_at.replace("Z", "+00:00")).timestamp())
            except Exception:
                ts = 0
            try:
                self.collection.add(
                    ids=[entry["id"]],
                    documents=[searchable_text],
                    metadatas=[{
                        "content_type": entry.get("content_type", "text"),
                        "created_at": created_at,
                        "created_at_ts": ts,
                        "category": entry.get("category") or "uncategorized"
                    }]
                )
                count += 1
            except Exception as e:
                logger.warning("Reindex failed for %s: %s", entry["id"], e)

        logger.info("Reindexed %d entries in ChromaDB", count)
        return count