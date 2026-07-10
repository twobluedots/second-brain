import random
from collections import Counter
from datetime import datetime, timedelta, timezone

from src.categorize import categorize
from src.logger import logger
from src.models import Entry
from src.storage.storage import Storage
from config import REDISCOVERY_CATEGORIES


class NoteService:
    def __init__(self, storage: Storage):
        self.storage = storage

    def save_note(
        self,
        content: str,
        content_type: str,
        *,
        file_path: str = None,
        description: str = None,
        category: str = None,
        tags: list = None,
    ) -> tuple[str, str]:
        """Categorize then save. Returns (entry_id, category)."""
        ai_suggested = None
        if not category:
            ai_suggested = categorize(content or "", description=description)
            category = ai_suggested
        entry = Entry(
            content=content,
            content_type=content_type,
            category=category,
            tags=tags or [],
            file_path=file_path,
            description=description,
        )
        entry_id = self.storage.save(entry)
        self.storage.log_category_event(entry_id, ai_suggested, category, event_type='ai_assignment')
        logger.info("Note saved: %s (type=%s, category=%s)", entry_id, content_type, category)
        return entry_id, category

    def update_note(self, entry_id: str, content: str) -> None:
        self.storage.update(entry_id, {"content": content})
        logger.info("Content updated: %s", entry_id)

    def delete_note(self, entry_id: str) -> None:
        self.storage.delete(entry_id)
        logger.info("Note deleted: %s", entry_id)

    def override_category(self, entry_id: str, new_category: str) -> None:
        self.storage.update(entry_id, {"category": new_category})
        self.storage.log_category_event(entry_id, ai_suggested=None, final_category=new_category, event_type='user_override')
        logger.info("Category overridden: %s → %s", entry_id, new_category)

    def get_categories(self) -> list[str]:
        return self.storage.get_categories()

    def get_recent(self, limit: int = 10):
        return self.storage.get_recent(limit)

    def search(self, query: str, content_type: str = None, date_from: str = None, date_preset: str = None):
        # Two execution paths for the same intent ("give me entries matching these criteria"):
        # - text present → ChromaDB vector search, metadata filters applied as pre-filters
        # - no text → SQLite only, filters run directly (vector search on empty string is meaningless)
        if query.strip():
            clauses = []
            if content_type and content_type != "all":
                clauses.append({"content_type": {"$eq": content_type}})
            if date_from:
                ts = int(datetime.fromisoformat(date_from.replace("Z", "+00:00")).timestamp())
                clauses.append({"created_at_ts": {"$gte": ts}})
            where = None if not clauses else (clauses[0] if len(clauses) == 1 else {"$and": clauses})
            results = self.storage.search(query, where=where)
        else:
            ct = content_type if content_type and content_type != "all" else None
            results = self.storage.get_entries(content_type=ct, date_from=date_from)
        self.storage.log_search(query=query or None, content_type=content_type, date_preset=date_preset, result_count=len(results))
        return results

    def get_by_date_range(self, start: str, end: str):
        return self.storage.get_by_date_range(start, end)

    def get_by_category(self, category: str, limit: int = 50):
        return self.storage.get_by_category(category, limit)

    def get_category_counts(self) -> dict:
        return self.storage.get_category_counts()

    def get_mirror_stats(self) -> dict:
        now = datetime.now(timezone.utc)
        seven_days_ago = now - timedelta(days=7)

        def _iso(dt: datetime) -> str:
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        week_entries = self.storage.get_by_date_range(_iso(seven_days_ago), _iso(now))

        category_breakdown = Counter(
            e["category"] for e in week_entries if e.get("category")
        )
        top_category = category_breakdown.most_common(1)[0][0] if category_breakdown else None

        active_days = {
            datetime.fromisoformat(e["created_at"].replace("Z", "+00:00")).date()
            for e in week_entries
        }

        all_counts = self.storage.get_category_counts()
        total_count = sum(all_counts.values())

        old_entries = self.storage.get_by_date_range(
            "2000-01-01T00:00:00Z", _iso(seven_days_ago)
        )
        rediscovery_pool = [
            e for e in old_entries
            if e.get("category") in REDISCOVERY_CATEGORIES
            and len(e.get("content") or e.get("description") or "") <= 300
        ]
        rediscovery = random.choice(rediscovery_pool) if rediscovery_pool else None

        return {
            "week_count": len(week_entries),
            "total_count": total_count,
            "category_breakdown": dict(category_breakdown),
            "active_days": active_days,
            "top_category": top_category,
            "rediscovery": rediscovery,
        }