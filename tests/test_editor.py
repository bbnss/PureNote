import sqlite3
from dataclasses import dataclass

from editor import EditorSession


@dataclass
class Event:
    when: float
    callback: object
    cancelled: bool = False

    def cancel(self):
        self.cancelled = True


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.events = []

    def schedule(self, callback, delay):
        event = Event(self.now + delay, callback)
        self.events.append(event)
        return event

    def advance(self, delta):
        target = self.now + delta
        while pending := [e for e in self.events if not e.cancelled and e.when <= target]:
            event = min(pending, key=lambda e: e.when)
            self.now = event.when
            event.cancelled = True
            event.callback()
        self.now = target


def session_for(store):
    clock = FakeClock()
    return EditorSession(store, clock.schedule), clock


def test_debounce_saves_once_after_typing_pauses(store):
    session, clock = session_for(store)
    session.edit("C")
    clock.advance(0.2)
    session.edit("Ciao")
    clock.advance(0.299)
    assert store.all_notes() == []
    clock.advance(0.002)
    assert len(store.all_notes()) == 1
    assert store.get(session.note_id).body == "Ciao"
    assert not session.dirty


def test_continuous_typing_still_saves_within_two_seconds(store):
    session, clock = session_for(store)
    for index in range(10):
        session.edit("a" * (index + 1))
        clock.advance(0.2)
    clock.advance(0.001)
    assert store.get(session.note_id).body == "a" * 10
    session.edit("Ultima versione")
    clock.advance(0.301)
    assert len(store.all_notes()) == 1
    assert store.get(session.note_id).body == "Ultima versione"


def test_fast_navigation_flushes_old_note_and_cancels_stale_callbacks(store):
    session, clock = session_for(store)
    second = store.save_note("Seconda")
    session.edit("Prima")
    assert session.open(second)
    first = next(n for n in store.all_notes() if n.body == "Prima")
    session.edit("Seconda modificata")
    assert session.open(first.id)
    clock.advance(5)
    assert store.get(first.id).body == "Prima"
    assert store.get(second).body == "Seconda modificata"
    assert session.text == "Prima"


def test_new_blank_drafts_are_ignored_but_existing_empty_notes_saved(store):
    session, clock = session_for(store)
    session.edit(" \n")
    clock.advance(0.3)
    assert store.all_notes() == []
    session.edit("Nota")
    session.flush()
    note_id = session.note_id
    session.edit("")
    session.flush()
    assert store.get(note_id).body == ""


def test_failed_save_blocks_navigation_retains_text_and_retries(store, monkeypatch):
    session, clock = session_for(store)
    other = store.save_note("Altra")
    real_save = store.save_note

    def fail(*_):
        raise sqlite3.OperationalError("disk full")

    monkeypatch.setattr(store, "save_note", fail)
    session.edit("Testo prezioso")
    clock.advance(0.3)
    assert session.error == "disk full"
    assert session.dirty
    assert not session.open(other)
    assert session.text == "Testo prezioso"
    assert session.note_id is None
    monkeypatch.setattr(store, "save_note", real_save)
    clock.advance(2.01)
    assert not session.error
    assert not session.dirty
    assert store.get(session.note_id).body == "Testo prezioso"


def test_flush_for_background_or_close_does_not_duplicate_note(store):
    session, clock = session_for(store)
    session.edit("Subito")
    session.flush()
    session.flush()
    clock.advance(4)
    assert [note.body for note in store.all_notes()] == ["Subito"]
