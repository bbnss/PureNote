"""Portable UTF-8 backups. Validate every record before touching the store."""

import json
from dataclasses import asdict

from db import NoteStore, title_from_text

MAX_BACKUP_BYTES = 32 * 1024 * 1024
FORMAT_VERSION = 1


def export_backup(store: NoteStore) -> bytes:
    notes = [
        {key: value for key, value in asdict(note).items() if key != "id"}
        for note in store.all_notes()
    ]
    data = json.dumps(
        {"app": "PureNote", "version": FORMAT_VERSION, "notes": notes}, ensure_ascii=False, indent=2
    ).encode("utf-8")
    if len(data) > MAX_BACKUP_BYTES:
        raise ValueError("Il backup supera il limite di 32 MB.")
    return data


def read_backup(data: bytes) -> list[dict]:
    if len(data) > MAX_BACKUP_BYTES:
        raise ValueError("Il backup supera il limite di 32 MB.")
    try:
        document = json.loads(data.decode("utf-8-sig"))
    except (UnicodeError, ValueError, RecursionError) as error:
        raise ValueError("Il file non è un backup JSON valido.") from error
    if (
        not isinstance(document, dict)
        or document.get("app") != "PureNote"
        or type(document.get("version")) is not int
        or document["version"] != FORMAT_VERSION
        or not isinstance(document.get("notes"), list)
    ):
        raise ValueError("Formato o versione del backup non supportati.")
    notes = []
    for record in document["notes"]:
        if not isinstance(record, dict):
            raise ValueError("Il backup contiene una nota non valida.")
        for key in ("title", "body", "tags"):
            if not isinstance(record.get(key), str):
                raise ValueError(f"Campo non valido nel backup: {key}.")
            try:
                record[key].encode("utf-8")
            except UnicodeError as error:
                raise ValueError(f"Testo Unicode non valido: {key}.") from error
        for key in ("created_at", "updated_at", "pinned", "trashed"):
            value = record.get(key)
            if type(value) is not int or not 0 <= value <= 2**63 - 1:
                raise ValueError(f"Campo non valido nel backup: {key}.")
            if key in ("pinned", "trashed") and value not in (0, 1):
                raise ValueError(f"Campo non valido nel backup: {key}.")
        notes.append(
            {
                key: record[key]
                for key in (
                    "title",
                    "body",
                    "tags",
                    "pinned",
                    "created_at",
                    "updated_at",
                    "trashed",
                )
            }
        )
        notes[-1]["title"] = title_from_text(record["body"])
    return notes
