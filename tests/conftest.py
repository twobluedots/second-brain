import pytest
from src.storage.storage import Storage
from src.notes_service import NoteService


@pytest.fixture
def storage(tmp_path):
    """Isolated Storage backed by temp SQLite + ChromaDB — never touches real data."""
    return Storage(
        db_path=str(tmp_path / "test.db"),
        chroma_path=str(tmp_path / "chroma"),
        embedding_model="all-MiniLM-L6-v2",
    )


@pytest.fixture
def service(storage):
    return NoteService(storage)
