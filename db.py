"""Local notes, transactional migrations, and remembered editor state."""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

SCHEMA_VERSION = 3


def title_from_text(text: str) -> str:
    """The first nonblank line is the title; the source text stays untouched."""
    return next((line.strip()[:80] for line in text.splitlines() if line.strip()), "Senza titolo")


def merge_legacy_title(title: str, body: str) -> str:
    """Keep old explicit titles without duplicating generated/Markdown titles."""
    title = title.strip()
    first = next((line.strip() for line in body.splitlines() if line.strip()), "")
    comparable = first.lstrip("# ").strip()
    if not title or title == "Senza titolo" or title in (first, comparable, comparable[:60]):
        return body
    return f"{title}\n\n{body}" if body else title


@dataclass(frozen=True)
class Note:
    id: int
    title: str
    body: str
    tags: str
    pinned: int
    created_at: int
    updated_at: int
    trashed: int


class NoteStore:
    def __init__(self, path: str | Path):
        self.path = str(path)
        self.conn = sqlite3.connect(self.path, timeout=5)
        self.conn.row_factory = sqlite3.Row
        self.conn.create_function("casefold", 1, str.casefold, deterministic=True)
        try:
            self._migrate()
        except Exception:
            self.conn.close()
            raise

    def _columns(self, table: str) -> set[str]:
        return {row[1] for row in self.conn.execute(f"PRAGMA table_info({table})")}

    def _migrate(self) -> None:
        version = self.conn.execute("PRAGMA user_version").fetchone()[0]
        if version > SCHEMA_VERSION:
            raise ValueError("Database creato da una versione più recente di PureNote.")
        if version == SCHEMA_VERSION:
            return
        if self._columns("notes") or self._columns("notes_legacy"):
            # The backup API includes committed WAL pages, unlike a file copy.
            backup_path = self.path + ".pre-v3.bak"
            if Path(backup_path).exists():
                backup_path = self.path + f".pre-v3-{time.time_ns()}.bak"
            backup = sqlite3.connect(backup_path)
            try:
                self.conn.backup(backup)
            finally:
                backup.close()

        self.conn.execute("BEGIN IMMEDIATE")
        try:
            columns = self._columns("notes")
            if "note" in columns and "id" not in columns:
                self.conn.execute("ALTER TABLE notes RENAME TO notes_legacy")
            self.conn.execute("""CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL DEFAULT '',
                body TEXT NOT NULL DEFAULT '',
                tags TEXT NOT NULL DEFAULT '',
                pinned INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL DEFAULT 0,
                updated_at INTEGER NOT NULL DEFAULT 0,
                trashed INTEGER NOT NULL DEFAULT 0
            )""")
            if "trashed" not in self._columns("notes"):
                self.conn.execute("ALTER TABLE notes ADD COLUMN trashed INTEGER NOT NULL DEFAULT 0")
            for row in self.conn.execute("SELECT id, title, body FROM notes").fetchall():
                body = merge_legacy_title(row["title"], row["body"])
                self.conn.execute(
                    "UPDATE notes SET title=?, body=? WHERE id=?",
                    (title_from_text(body), body, row["id"]),
                )
            if "note" in self._columns("notes_legacy"):
                now = int(time.time())
                for row in self.conn.execute("SELECT note FROM notes_legacy").fetchall():
                    body = row[0] or ""
                    self.conn.execute(
                        "INSERT INTO notes(title,body,created_at,updated_at) VALUES(?,?,?,?)",
                        (title_from_text(body), body, now, now),
                    )
                self.conn.execute("DROP TABLE notes_legacy")
            self.conn.execute(
                "CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
            )
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS notes_recent ON notes(trashed, updated_at DESC, id DESC)"
            )
            self.conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def get(self, note_id: int) -> Note | None:
        row = self.conn.execute("SELECT * FROM notes WHERE id=?", (note_id,)).fetchone()
        return Note(**dict(row)) if row else None

    def list_notes(self, query: str = "", *, trashed: bool = False) -> list[Note]:
        # instr treats %, _ and backslashes as literal search characters.
        rows = self.conn.execute(
            "SELECT * FROM notes WHERE trashed=? AND "
            "(?='' OR instr(casefold(body), casefold(?)) > 0) "
            "ORDER BY updated_at DESC, id DESC",
            (int(trashed), query, query),
        )
        return [Note(**dict(row)) for row in rows]

    def save_note(self, body: str, note_id: int | None = None) -> int:
        now = int(time.time())
        with self.conn:
            if note_id is None:
                cursor = self.conn.execute(
                    "INSERT INTO notes(title,body,created_at,updated_at) VALUES(?,?,?,?)",
                    (title_from_text(body), body, now, now),
                )
                note_id = cursor.lastrowid
            else:
                cursor = self.conn.execute(
                    "UPDATE notes SET title=?,body=?,updated_at=? WHERE id=? AND trashed=0",
                    (title_from_text(body), body, now, note_id),
                )
                if cursor.rowcount != 1:
                    raise ValueError("La nota non è disponibile.")
            self._remember(note_id)
        return note_id

    def _remember(self, note_id: int | None) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO settings(key,value) VALUES('last_note',?)", (str(note_id or 0),)
        )

    def remember(self, note_id: int | None) -> None:
        with self.conn:
            self._remember(note_id)

    def last_note(self) -> Note | None:
        row = self.conn.execute("SELECT value FROM settings WHERE key='last_note'").fetchone()
        note = self.get(int(row[0])) if row else None
        if note and not note.trashed:
            return note
        row = self.conn.execute(
            "SELECT * FROM notes WHERE trashed=0 ORDER BY updated_at DESC,id DESC LIMIT 1"
        ).fetchone()
        return Note(**dict(row)) if row else None

    def set_trashed(self, note_id: int, trashed: bool) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE notes SET trashed=?,updated_at=? WHERE id=?",
                (int(trashed), int(time.time()), note_id),
            )

    def delete_forever(self, note_id: int | None = None) -> None:
        with self.conn:
            if note_id is None:
                self.conn.execute("DELETE FROM notes WHERE trashed=1")
            else:
                self.conn.execute("DELETE FROM notes WHERE id=? AND trashed=1", (note_id,))

    def all_notes(self) -> list[Note]:
        return [Note(**dict(row)) for row in self.conn.execute("SELECT * FROM notes ORDER BY id")]

    def import_notes(self, notes: list[dict]) -> int:
        """Insert an already validated backup atomically, assigning fresh IDs."""
        with self.conn:
            self.conn.executemany(
                "INSERT INTO notes(title,body,tags,pinned,created_at,updated_at,trashed) "
                "VALUES(:title,:body,:tags,:pinned,:created_at,:updated_at,:trashed)",
                notes,
            )
        return len(notes)

    def close(self) -> None:
        self.conn.close()
