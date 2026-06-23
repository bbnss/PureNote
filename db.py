"""SQLite data layer for PureNote.

Holds the notes store and transparently migrates the legacy single-column
``notes(note text)`` table to the new schema on first run.
"""

import os
import sqlite3
import time

# On Android the cwd is read-only, so the app overrides this with the
# user data dir. On desktop we just use a file next to the source.
DB_PATH = os.environ.get("PURENOTE_DB", "notes.db")


def _now():
    return int(time.time())


class NoteStore:
    def __init__(self, path=None):
        self.path = path or DB_PATH
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    # ------------------------------------------------------------------ schema
    def _init_schema(self):
        # The legacy app shipped a ``notes`` table with a single ``note``
        # column. Detect it before creating the new table (same name) and
        # stash it aside so we can migrate its rows.
        self._stash_legacy_table()
        self.conn.execute(
            """CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL DEFAULT '',
                body TEXT NOT NULL DEFAULT '',
                tags TEXT NOT NULL DEFAULT '',
                pinned INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL DEFAULT 0,
                updated_at INTEGER NOT NULL DEFAULT 0
            )"""
        )
        self.conn.commit()
        self._ensure_columns()
        self._migrate_legacy()

    def _table_columns(self, table):
        return [r[1] for r in self.conn.execute(f"PRAGMA table_info({table})")]

    def _ensure_columns(self):
        """Add columns introduced after the first v2 schema (idempotent)."""
        cols = self._table_columns("notes")
        if "trashed" not in cols:
            self.conn.execute(
                "ALTER TABLE notes ADD COLUMN trashed INTEGER NOT NULL DEFAULT 0"
            )
            self.conn.commit()

    def _stash_legacy_table(self):
        cols = self._table_columns("notes")
        # New schema already in place -> nothing to stash.
        if "id" in cols or "title" in cols:
            return
        if "note" in cols:
            self.conn.execute("ALTER TABLE notes RENAME TO notes_legacy")
            self.conn.commit()

    def _migrate_legacy(self):
        """Move rows from the stashed ``notes_legacy`` table, if any."""
        if "note" not in self._table_columns("notes_legacy"):
            return
        rows = self.conn.execute("SELECT note FROM notes_legacy").fetchall()
        for (note,) in rows:
            body = note or ""
            self.add(self._title_from_body(body), body)
        self.conn.execute("DROP TABLE notes_legacy")
        self.conn.commit()

    @staticmethod
    def _title_from_body(body):
        first = (body or "").strip().splitlines()[0] if body.strip() else ""
        first = first.lstrip("# ").strip()
        return (first[:60]) or "Senza titolo"

    # ------------------------------------------------------------------- CRUD
    def add(self, title, body, tags="", pinned=0):
        ts = _now()
        cur = self.conn.execute(
            "INSERT INTO notes (title, body, tags, pinned, created_at, updated_at)"
            " VALUES (?,?,?,?,?,?)",
            (title, body, tags, int(pinned), ts, ts),
        )
        self.conn.commit()
        return cur.lastrowid

    def update(self, note_id, title, body, tags="", pinned=None):
        if pinned is None:
            self.conn.execute(
                "UPDATE notes SET title=?, body=?, tags=?, updated_at=? WHERE id=?",
                (title, body, tags, _now(), note_id),
            )
        else:
            self.conn.execute(
                "UPDATE notes SET title=?, body=?, tags=?, pinned=?, updated_at=? WHERE id=?",
                (title, body, tags, int(pinned), _now(), note_id),
            )
        self.conn.commit()

    def set_pinned(self, note_id, pinned):
        self.conn.execute(
            "UPDATE notes SET pinned=?, updated_at=? WHERE id=?",
            (int(pinned), _now(), note_id),
        )
        self.conn.commit()

    def trash(self, note_id):
        """Soft-delete: move a note to the trash (recoverable)."""
        self.conn.execute(
            "UPDATE notes SET trashed=1, updated_at=? WHERE id=?",
            (_now(), note_id),
        )
        self.conn.commit()

    def restore(self, note_id):
        self.conn.execute(
            "UPDATE notes SET trashed=0, updated_at=? WHERE id=?",
            (_now(), note_id),
        )
        self.conn.commit()

    def delete(self, note_id):
        """Permanently remove a note."""
        self.conn.execute("DELETE FROM notes WHERE id=?", (note_id,))
        self.conn.commit()

    def empty_trash(self):
        self.conn.execute("DELETE FROM notes WHERE trashed=1")
        self.conn.commit()

    def count_trashed(self):
        return self.conn.execute(
            "SELECT COUNT(*) FROM notes WHERE trashed=1"
        ).fetchone()[0]

    def is_empty(self):
        return self.conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0] == 0

    def get(self, note_id):
        row = self.conn.execute("SELECT * FROM notes WHERE id=?", (note_id,)).fetchone()
        return dict(row) if row else None

    # ----------------------------------------------------------------- queries
    def list(self, query="", tag="", trashed=0):
        clauses = ["trashed = ?"]
        params = [int(trashed)]
        if query:
            clauses.append("(title LIKE ? OR body LIKE ?)")
            like = f"%{query}%"
            params += [like, like]
        if tag:
            clauses.append("(',' || replace(tags,' ','') || ',') LIKE ?")
            params.append(f"%,{tag},%")
        sql = "SELECT * FROM notes WHERE " + " AND ".join(clauses)
        sql += " ORDER BY pinned DESC, updated_at DESC"
        return [dict(r) for r in self.conn.execute(sql, params).fetchall()]

    def all_tags(self):
        tags = set()
        for (raw,) in self.conn.execute(
            "SELECT tags FROM notes WHERE tags != '' AND trashed = 0"
        ):
            for t in raw.split(","):
                t = t.strip()
                if t:
                    tags.add(t)
        return sorted(tags)

    def close(self):
        self.conn.close()
