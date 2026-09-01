"""
Demo seed store — covers scripts/seed_demo.py and the opt-in env-var branch
in ui/services.get_storage(). See docs/design/demo-seed-store.md.
"""
import collections
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.seed_demo import seed_demo

MINI_MODEL = "all-MiniLM-L6-v2"  # fast, matches tests/conftest.py


def _parse_iso(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _days_between(iso_a: str, iso_b: str) -> int:
    return (_parse_iso(iso_b) - _parse_iso(iso_a)).days


@pytest.fixture
def demo_paths(tmp_path):
    return tmp_path / "demo.db", tmp_path / "demo_chroma"


def test_seed_demo_builds_expected_store(demo_paths):
    db_path, chroma_path = demo_paths
    count = seed_demo(db_path, chroma_path, embedding_model=MINI_MODEL)
    assert count == 39

    rows = sqlite3.connect(str(db_path)).execute(
        "SELECT category, content_type, created_at FROM entries"
    ).fetchall()
    assert len(rows) == 39
    assert collections.Counter(r[0] for r in rows) == {
        "achievement": 10, "task": 8, "insight": 7, "reference": 7,
        "journal": 4, "learning": 2, "mood": 1,
    }
    assert all(r[1] == "text" for r in rows), "voice cards need an audio file the demo has none of"

    dates = sorted(r[2] for r in rows)
    assert _days_between(dates[0], dates[-1]) >= 30, "dates must span weeks for the time-filter demo"


def test_seed_demo_is_idempotent(demo_paths):
    db_path, chroma_path = demo_paths
    seed_demo(db_path, chroma_path, embedding_model=MINI_MODEL)
    count = seed_demo(db_path, chroma_path, embedding_model=MINI_MODEL)
    assert count == 39

    ids = [r[0] for r in sqlite3.connect(str(db_path)).execute("SELECT id FROM entries")]
    assert len(ids) == len(set(ids)) == 39


# ── ui/services.get_storage() env-var branch ─────────────────────────────────

def _fake_storage_capture(monkeypatch):
    import ui.services as services

    captured = {}

    class FakeStorage:
        def __init__(self, **kwargs):
            captured["kwargs"] = kwargs

    monkeypatch.setattr(services, "Storage", FakeStorage)
    services.get_storage.clear()
    return services, captured


def test_get_storage_uses_env_paths_when_both_set(monkeypatch):
    services, captured = _fake_storage_capture(monkeypatch)
    monkeypatch.setenv("SECOND_BRAIN_DB", "data/demo/entries.db")
    monkeypatch.setenv("SECOND_BRAIN_CHROMA", "data/demo/chroma_data")

    services.get_storage()

    assert captured["kwargs"] == {
        "db_path": "data/demo/entries.db",
        "chroma_path": "data/demo/chroma_data",
    }
    services.get_storage.clear()


def test_get_storage_defaults_when_env_unset(monkeypatch):
    services, captured = _fake_storage_capture(monkeypatch)
    monkeypatch.delenv("SECOND_BRAIN_DB", raising=False)
    monkeypatch.delenv("SECOND_BRAIN_CHROMA", raising=False)

    services.get_storage()

    assert captured["kwargs"] == {}
    services.get_storage.clear()


def test_get_storage_defaults_when_only_one_env_set(monkeypatch):
    services, captured = _fake_storage_capture(monkeypatch)
    monkeypatch.setenv("SECOND_BRAIN_DB", "data/demo/entries.db")
    monkeypatch.delenv("SECOND_BRAIN_CHROMA", raising=False)

    services.get_storage()

    assert captured["kwargs"] == {}, "both-or-nothing — one var alone is ignored"
    services.get_storage.clear()
