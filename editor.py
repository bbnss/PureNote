"""Editor session independent of Kivy; scheduling is injected for testing."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from typing import Protocol

from db import NoteStore


class ScheduledCall(Protocol):
    def cancel(self) -> None: ...


Schedule = Callable[[Callable, float], ScheduledCall]


class EditorSession:
    DEBOUNCE = 0.3
    MAX_WAIT = 2.0

    def __init__(
        self, store: NoteStore, schedule: Schedule, on_change: Callable[[], None] = lambda: None
    ):
        self.store = store
        self.schedule = schedule
        self.on_change = on_change
        self.note_id: int | None = None
        self.text = ""
        self.dirty = False
        self.error = ""
        self._debounce: ScheduledCall | None = None
        self._deadline: ScheduledCall | None = None

    def open(self, note_id: int | None) -> bool:
        if not self.flush():
            return False
        note = self.store.get(note_id) if note_id else None
        if note_id and (note is None or note.trashed):
            raise ValueError("La nota non è disponibile.")
        self.store.remember(note_id)
        self.note_id = note_id
        self.text = note.body if note else ""
        self.error = ""
        self.on_change()
        return True

    def edit(self, text: str) -> None:
        if text == self.text:
            return
        self.text = text
        self.dirty = True
        if self._debounce:
            self._debounce.cancel()
        self._debounce = self.schedule(self.flush, self.DEBOUNCE)
        if self._deadline is None:
            self._deadline = self.schedule(self.flush, self.MAX_WAIT)
        self.on_change()

    def _cancel_pending(self) -> None:
        for event in (self._debounce, self._deadline):
            if event:
                event.cancel()
        self._debounce = self._deadline = None

    def flush(self, *_args) -> bool:
        self._cancel_pending()
        if not self.dirty:
            return True
        try:
            # A blank draft never creates an empty database row.
            if self.note_id is not None or self.text.strip():
                self.note_id = self.store.save_note(self.text, self.note_id)
        except (sqlite3.Error, OSError, ValueError) as error:
            self.error = str(error)
            self._deadline = self.schedule(self.flush, self.MAX_WAIT)
            self.on_change()
            return False
        self.dirty = False
        self.error = ""
        self.on_change()
        return True

    def dispose(self) -> None:
        self._cancel_pending()
