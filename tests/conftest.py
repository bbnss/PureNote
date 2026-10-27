import pytest

from db import NoteStore


@pytest.fixture
def store(tmp_path):
    store = NoteStore(tmp_path / "notes.db")
    yield store
    store.close()
