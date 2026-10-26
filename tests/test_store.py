import sqlite3

import pytest

from db import SCHEMA_VERSION, NoteStore, merge_legacy_title, title_from_text


def test_new_database_is_empty_and_does_not_seed_notes(store):
    assert store.all_notes() == []
    assert store.last_note() is None


def test_edit_keeps_metadata_and_empty_existing_note(store):
    note_id = store.save_note("Titolo\nCorpo")
    with store.conn:
        store.conn.execute(
            "UPDATE notes SET tags=?,pinned=1,created_at=42 WHERE id=?", ("casa,info", note_id)
        )
    store.save_note("", note_id)
    note = store.get(note_id)
    assert (note.title, note.body, note.tags, note.pinned, note.created_at) == (
        "Senza titolo",
        "",
        "casa,info",
        1,
        42,
    )


def test_last_opened_survives_restart_and_missing_note_falls_back(tmp_path):
    path = tmp_path / "notes.db"
    store = NoteStore(path)
    first = store.save_note("Prima")
    second = store.save_note("Seconda")
    store.remember(first)
    store.close()
    store = NoteStore(path)
    assert store.last_note().id == first
    store.set_trashed(first, True)
    assert store.last_note().id == second
    store.set_trashed(second, True)
    assert store.last_note() is None
    store.close()


def test_search_is_unicode_case_insensitive_and_treats_wildcards_literally(store):
    first = store.save_note("È già qui: 100%_vero")
    store.save_note("Altro testo")
    assert [n.id for n in store.list_notes("È GIÀ")] == [first]
    assert [n.id for n in store.list_notes("%_")] == [first]
    assert store.list_notes("assente") == []


def test_recent_order_ignores_old_pins_and_breaks_ties_by_id(store):
    first = store.save_note("Prima")
    second = store.save_note("Seconda")
    with store.conn:
        store.conn.execute("UPDATE notes SET updated_at=100")
        store.conn.execute("UPDATE notes SET pinned=1 WHERE id=?", (first,))
    assert [n.id for n in store.list_notes()] == [second, first]


def test_trash_restore_and_permanent_deletion_only_affect_trash(store):
    active = store.save_note("Attiva")
    deleted = store.save_note("Cestinata")
    store.set_trashed(deleted, True)
    assert [n.id for n in store.list_notes(trashed=True)] == [deleted]
    store.set_trashed(deleted, False)
    assert len(store.list_notes()) == 2
    store.delete_forever(active)
    assert store.get(active) is not None
    store.set_trashed(deleted, True)
    store.delete_forever()
    assert store.get(deleted) is None
    assert store.get(active) is not None
    with pytest.raises(ValueError):
        store.save_note("Nuovo testo", deleted)


def test_migrate_original_single_column_database_once(tmp_path):
    path = tmp_path / "notes.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE notes(note TEXT)")
        conn.executemany("INSERT INTO notes VALUES(?)", [("Originale\nÈ qui",), ("",), (None,)])
    store = NoteStore(path)
    assert [n.body for n in store.all_notes()] == ["Originale\nÈ qui", "", ""]
    assert store.conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    store.close()
    assert (tmp_path / "notes.db.pre-v3.bak").exists()
    store = NoteStore(path)
    assert len(store.all_notes()) == 3
    assert len(list(tmp_path.glob("*.bak"))) == 1
    store.close()


def make_v2_database(path, *, trashed_column=True):
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE notes(id INTEGER PRIMARY KEY,title TEXT,body TEXT,tags TEXT,"
        "pinned INTEGER,created_at INTEGER,updated_at INTEGER"
        + (",trashed INTEGER DEFAULT 0)" if trashed_column else ")")
    )
    conn.execute(
        "INSERT INTO notes(id,title,body,tags,pinned,created_at,updated_at) VALUES(7,?,?,?,?,?,?)",
        ("Titolo separato", "Corpo intatto", "lavoro", 1, 11, 22),
    )
    conn.execute(
        "INSERT INTO notes(id,title,body,tags,pinned,created_at,updated_at) VALUES(8,?,?,?,?,?,?)",
        ("Già presente", "# Già presente\nTesto", "casa", 0, 33, 44),
    )
    conn.commit()
    return conn


def test_migrate_v2_preserves_titles_dates_tags_pins_and_trash(tmp_path):
    path = tmp_path / "notes.db"
    conn = make_v2_database(path)
    conn.execute("UPDATE notes SET trashed=1 WHERE id=7")
    conn.commit()
    conn.close()
    store = NoteStore(path)
    note = store.get(7)
    assert (note.body, note.tags, note.pinned, note.created_at, note.updated_at, note.trashed) == (
        "Titolo separato\n\nCorpo intatto",
        "lavoro",
        1,
        11,
        22,
        1,
    )
    assert store.get(8).body == "# Già presente\nTesto"
    backup = sqlite3.connect(str(path) + ".pre-v3.bak")
    assert backup.execute("SELECT body FROM notes WHERE id=7").fetchone()[0] == "Corpo intatto"
    backup.close()
    store.close()


def test_failed_migration_rolls_back_data_and_schema(tmp_path):
    path = tmp_path / "notes.db"
    conn = make_v2_database(path, trashed_column=False)
    conn.execute(
        "CREATE TRIGGER reject_update BEFORE UPDATE ON notes WHEN NEW.id=8 "
        "BEGIN SELECT RAISE(ABORT, 'simulated failure'); END"
    )
    conn.commit()
    conn.close()
    with pytest.raises(sqlite3.IntegrityError, match="simulated failure"):
        NoteStore(path)
    conn = sqlite3.connect(path)
    assert conn.execute("SELECT body FROM notes WHERE id=7").fetchone()[0] == "Corpo intatto"
    assert "trashed" not in [r[1] for r in conn.execute("PRAGMA table_info(notes)")]
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 0
    conn.close()


@pytest.mark.parametrize(
    ("title", "body", "expected"),
    [
        ("Nome", "Nome\nTesto", "Nome\nTesto"),
        ("Nome", "# Nome\nTesto", "# Nome\nTesto"),
        ("Diverso", "Testo", "Diverso\n\nTesto"),
        ("", "Testo", "Testo"),
        ("Senza titolo", "", ""),
        ("x" * 60, "x" * 100, "x" * 100),
    ],
)
def test_legacy_title_conversion(title, body, expected):
    assert merge_legacy_title(title, body) == expected


def test_title_uses_first_nonblank_line_without_changing_source():
    assert title_from_text("\n  \n  Una nota  \nAltro") == "Una nota"
    assert title_from_text("  \n") == "Senza titolo"


def test_newer_schema_is_not_modified(tmp_path):
    path = tmp_path / "future.db"
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA user_version=99")
    with pytest.raises(ValueError, match="recente"):
        NoteStore(path)
    with sqlite3.connect(path) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 99
