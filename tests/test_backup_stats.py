import json
import sqlite3
from dataclasses import asdict

import pytest

from backup import MAX_BACKUP_BYTES, export_backup, read_backup
from stats import count_text


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", (0, 0, 0)),
        ("Ciao mondo", (2, 10, 3)),
        ("È già qui\n🙂", (4, 11, 3)),
        ("a  b\n\tc", (3, 7, 2)),
        ("e\u0301", (1, 2, 1)),
        ("👨‍👩‍👧", (1, 5, 2)),
    ],
)
def test_counters(text, expected):
    assert tuple(asdict(count_text(text)).values()) == expected


def make_backup(store):
    active = store.save_note("È una nota\n🙂\n- [ ] Testo Markdown")
    deleted = store.save_note("Cestino")
    with store.conn:
        store.conn.execute(
            "UPDATE notes SET tags=?,pinned=1,created_at=12 WHERE id=?", ("vecchi,tag", active)
        )
    store.set_trashed(deleted, True)
    return export_backup(store)


def test_backup_round_trip_is_additive_and_preserves_all_metadata(store):
    data = make_backup(store)
    original = store.all_notes()
    parsed = read_backup(data)
    assert store.import_notes(parsed) == 2
    copies = store.all_notes()[2:]
    for before, after in zip(original, copies):
        assert after.id != before.id
        assert {k: v for k, v in asdict(before).items() if k != "id"} == {
            k: v for k, v in asdict(after).items() if k != "id"
        }
    assert len(store.list_notes()) == 2
    assert len(store.list_notes(trashed=True)) == 2


@pytest.mark.parametrize(
    "bad",
    [
        b"",
        b"\xff",
        b"{",
        b"[]",
        b'{"app":"PureNote","version":true,"notes":[]}',
        b'{"app":"PureNote","version":99,"notes":[]}',
        b'{"app":"Other","version":1,"notes":[]}',
    ],
)
def test_corrupt_backup_is_rejected_without_changes(store, bad):
    store.save_note("Conservata")
    with pytest.raises(ValueError):
        read_backup(bad)
    assert [n.body for n in store.all_notes()] == ["Conservata"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("body", None),
        ("body", "\ud800"),
        ("pinned", 2),
        ("trashed", True),
        ("updated_at", -1),
        ("created_at", 2**80),
        ("tags", []),
    ],
)
def test_invalid_later_record_prevents_partial_import(store, field, value):
    document = json.loads(make_backup(store))
    document["notes"][1][field] = value
    before = store.all_notes()
    with pytest.raises(ValueError):
        store.import_notes(read_backup(json.dumps(document).encode()))
    assert store.all_notes() == before


def test_sql_failure_during_import_rolls_back_all_rows(store):
    records = read_backup(make_backup(store))
    records[1]["body"] = None
    before = store.all_notes()
    with pytest.raises(sqlite3.IntegrityError):
        store.import_notes(records)
    assert store.all_notes() == before


def test_size_limit(store):
    with pytest.raises(ValueError, match="32 MB"):
        read_backup(b" " * (MAX_BACKUP_BYTES + 1))


def test_empty_backup_is_valid(store):
    assert read_backup(export_backup(store)) == []
