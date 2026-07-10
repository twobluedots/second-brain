"""
Search pipeline tests — covers both execution paths in NoteService.search():
  - text present  → ChromaDB vector search with optional metadata pre-filters
  - no text       → SQLite get_entries() with the same filters directly
"""
from datetime import datetime, timedelta, timezone


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


_NOW = datetime.now(timezone.utc)
FAR_PAST = _iso(datetime(2020, 1, 1, tzinfo=timezone.utc))
TODAY_START = _iso(_NOW.replace(hour=0, minute=0, second=0, microsecond=0))
TOMORROW_START = _iso((_NOW + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0))


# ── ChromaDB path (text query present) ────────────────────────────────────────

def test_text_search_finds_matching_note(service):
    service.save_note("feeling anxious about the deadline", "text", category="mood")
    results = service.search("anxious deadline")
    assert any("anxious" in r["content"] for r in results)


def test_content_type_filter_returns_only_matching_type(service):
    service.save_note("a text note", "text", category="reference")
    service.save_note("a voice transcription", "voice", category="reference", file_path="fake.wav")
    results = service.search("note transcription", content_type="text")
    assert results, "expected at least one result"
    assert all(r["content_type"] == "text" for r in results)


def test_date_filter_excludes_notes_before_cutoff(service):
    service.save_note("recent thought", "text", category="insight")
    # date_from = tomorrow → notes saved now don't qualify
    results = service.search("recent thought", date_from=TOMORROW_START)
    assert results == []


def test_date_filter_includes_notes_after_cutoff(service):
    service.save_note("recent thought", "text", category="insight")
    results = service.search("recent thought", date_from=FAR_PAST)
    assert len(results) > 0


def test_combined_type_and_date_filter(service):
    service.save_note("a text note today", "text", category="task")
    service.save_note("a voice note today", "voice", category="task", file_path="fake.wav")
    results = service.search("note today", content_type="text", date_from=TODAY_START)
    assert results, "expected results for matching type + date"
    assert all(r["content_type"] == "text" for r in results)


# ── SQLite path (no text query) ───────────────────────────────────────────────

def test_empty_query_no_filters_returns_all(service):
    service.save_note("first note", "text", category="task")
    service.save_note("second note", "text", category="mood")
    results = service.search("")
    assert len(results) == 2


def test_empty_query_with_content_type_filter(service):
    service.save_note("a text note", "text", category="task")
    service.save_note("a voice note", "voice", category="task", file_path="fake.wav")
    results = service.search("", content_type="text")
    assert len(results) == 1
    assert results[0]["content_type"] == "text"


def test_empty_query_date_filter_excludes_future(service):
    service.save_note("a recent note", "text", category="task")
    results = service.search("", date_from=TOMORROW_START)
    assert results == []


def test_empty_query_date_filter_includes_recent(service):
    service.save_note("a recent note", "text", category="task")
    results = service.search("", date_from=TODAY_START)
    assert len(results) == 1


# ── Search log ────────────────────────────────────────────────────────────────

def test_search_log_written_for_text_query(service, storage):
    service.save_note("something to find", "text", category="learning")
    service.search("something", content_type="text", date_preset="All time")
    with storage._connect() as conn:
        rows = conn.execute(
            "SELECT * FROM search_log WHERE query = 'something'"
        ).fetchall()
    assert len(rows) == 1
    row = dict(rows[0])
    assert row["content_type"] == "text"
    assert row["date_preset"] == "All time"
    assert isinstance(row["result_count"], int)


def test_search_log_query_is_null_for_empty_search(service, storage):
    service.save_note("test note", "text", category="task")
    service.search("", content_type="text")
    with storage._connect() as conn:
        rows = conn.execute(
            "SELECT * FROM search_log WHERE query IS NULL"
        ).fetchall()
    assert len(rows) >= 1


# ── ChromaDB metadata ─────────────────────────────────────────────────────────

def test_created_at_ts_stored_in_chroma_on_save(service, storage):
    service.save_note("timestamp test", "text", category="learning")
    data = storage.collection.get(include=["metadatas"])
    assert data["metadatas"], "no documents found in ChromaDB"
    for meta in data["metadatas"]:
        assert "created_at_ts" in meta, f"created_at_ts missing from metadata: {meta}"
        assert isinstance(meta["created_at_ts"], int)
