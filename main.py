"""PureNote: one quiet place to write, with local, automatic persistence."""

from __future__ import annotations

import os
import sqlite3
import time
from collections.abc import Callable
from pathlib import Path

from kivy.app import App
from kivy.clock import Clock
from kivy.core.clipboard import Clipboard
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.logger import Logger
from kivy.metrics import dp
from kivy.properties import BooleanProperty, ListProperty, NumericProperty, StringProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.recycleview import RecycleView  # noqa: F401 - registers the KV class
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.utils import platform

import theme
from backup import MAX_BACKUP_BYTES, export_backup, read_backup
from db import NoteStore
from editor import EditorSession
from stats import count_text

BASE_DIR = Path(__file__).resolve().parent


class QuietButton(ButtonBehavior, Label):
    primary = BooleanProperty(False)
    danger = BooleanProperty(False)


class IconButton(QuietButton):
    """Small canvas icons keep navigation independent of font glyph coverage."""

    icon = StringProperty("menu")


class NoteInput(TextInput):
    pass


class NoteRow(ButtonBehavior, BoxLayout):
    note_id = NumericProperty(0)
    title = StringProperty()
    snippet = StringProperty()
    date = StringProperty()

    def on_release(self):
        App.get_running_app().open_editor(self.note_id)


class ListScreen(Screen):
    query = StringProperty()
    empty_message = StringProperty()
    summary = StringProperty()


class EditorScreen(Screen):
    counts = StringProperty("0 parole   ·   0 caratteri   ·   ≈0 token")
    status = StringProperty("Salvataggio automatico")
    save_error = BooleanProperty(False)
    words = StringProperty("0")
    characters = StringProperty("0")
    tokens = StringProperty("≈0")
    loading = False

    def on_text_changed(self, text):
        app = App.get_running_app()
        if not self.loading and hasattr(app, "session"):
            app.session.edit(text)


class RootManager(ScreenManager):
    pass


class InsetPopup(Popup):
    """Keep Kivy's modal centering inside the area above the Android keyboard."""

    safe_center = ListProperty([0, 0])

    def _align_center(self, *_):
        if self._is_open:
            self.center = self.safe_center


class PureNoteApp(App):
    insets = ListProperty([0, 0, 0, 0])

    def build(self):
        if platform == "android":
            theme.configure_android_scaling()
        self.title = "PureNote"
        self.icon = str(BASE_DIR / "logo.png")
        Window.clearcolor = theme.BG
        Window.softinput_mode = ""
        self.documents = None
        self.android_window = None
        self._popup: Popup | None = None
        self._undo_id: int | None = None
        self._undo_event = None
        self._stats_trigger = Clock.create_trigger(self._update_stats, 0.06)
        self._search_trigger = Clock.create_trigger(self.refresh_list, 0.12)
        # Keep the old desktop path so upgrading finds the existing database.
        directory = Path(self.user_data_dir) if platform == "android" else BASE_DIR
        path = Path(os.environ.get("PURENOTE_DB", str(directory / "notes.db")))
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.store = NoteStore(path)
        except (sqlite3.Error, OSError, ValueError) as error:
            Logger.exception("PureNote: cannot open notes")
            return self.message_label(
                f"Impossibile aprire le note.\n\n{error}\n\n"
                "Il database originale è stato conservato."
            )
        self.session = EditorSession(self.store, Clock.schedule_once, self._session_changed)
        Window.bind(on_keyboard=self._on_key, on_request_close=self._on_request_close)
        return Builder.load_file(str(BASE_DIR / "purenote_ui.kv"))

    def on_start(self):
        if not hasattr(self, "session"):
            return
        if platform == "android":
            from android_window import AndroidWindow
            from documents import AndroidDocuments

            self.documents = AndroidDocuments(self.show_message)
            self.android_window = AndroidWindow(self._set_insets)
        note = self.store.last_note()
        self.open_editor(note.id if note else None)

    def _set_insets(self, left, top, right, bottom):
        self.insets = [left, top, right, bottom]

    @property
    def editor(self) -> EditorScreen:
        return self.root.get_screen("editor")

    def _session_changed(self):
        if not self.root:
            return
        editor = self.editor
        editor.save_error = bool(self.session.error)
        if self.session.error:
            editor.status = "Salvataggio non riuscito · tocca per riprovare"
        elif self.session.dirty:
            editor.status = "Salvataggio…"
        elif self.session.note_id:
            editor.status = "Tutto salvato"
        else:
            editor.status = "Salvataggio automatico"
        self._stats_trigger()

    def _update_stats(self, *_):
        stats = count_text(self.session.text)
        self.editor.words = str(stats.words)
        self.editor.characters = str(stats.characters)
        self.editor.tokens = f"≈{stats.estimated_tokens}"
        self.editor.counts = (
            f"{stats.words} parole   ·   {stats.characters} caratteri"
            f"   ·   ≈{stats.estimated_tokens} token"
        )

    def flush(self) -> bool:
        if self.session.flush():
            return True
        self.show_message(
            "Il testo resta aperto. Non è stato possibile salvarlo.\n\n"
            f"{self.session.error}\n\nPuoi riprovare o condividere il testo dal menu."
        )
        return False

    def open_editor(self, note_id: int | None = None):
        try:
            if not self.session.open(note_id):
                self.flush()
                return
        except (sqlite3.Error, OSError, ValueError) as error:
            self.show_message(str(error))
            return
        self.editor.loading = True
        self.editor.ids.body.text = self.session.text
        self.editor.ids.body.cursor = (0, 0)
        self.editor.loading = False
        self.root.current = "editor"
        self._update_stats()
        # Focus on new sheets only, so reading the last note doesn't open the IME.
        self.editor.ids.body.focus = note_id is None

    def new_note(self):
        self.open_editor()

    def go_list(self):
        if not self.flush():
            return
        self.editor.ids.body.focus = False
        self.root.current = "list"
        self.refresh_list()

    def set_query(self, query: str):
        if not self.root:
            return
        self.root.get_screen("list").query = query
        self._search_trigger()

    def refresh_list(self, *_):
        screen = self.root.get_screen("list")
        notes = self.store.list_notes(screen.query.strip())
        screen.summary = f"{len(notes)} " + ("nota" if len(notes) == 1 else "note")
        screen.empty_message = (
            "Nessuna corrispondenza.\nProva un’altra ricerca."
            if screen.query.strip()
            else "Uno spazio per i tuoi pensieri.\nTocca + per la prima nota."
        )
        screen.ids.notes.data = [
            {
                "note_id": note.id,
                "title": note.title,
                "snippet": self._snippet(note.body),
                "date": time.strftime("%d.%m.%Y · %H:%M", time.localtime(note.updated_at)),
            }
            for note in notes
        ]
        screen.ids.empty.opacity = 0 if notes else 1

    @staticmethod
    def _snippet(text: str) -> str:
        lines = text.lstrip().splitlines()
        return " ".join(" ".join(lines[1:]).split())[:140]

    def _on_key(self, _window, key, *_):
        if key == 27 and self._popup is None and self.root.current == "editor":
            if self.editor.ids.body.focus:
                self.editor.ids.body.focus = False
            else:
                self.go_list()
            return True
        return False

    def _on_request_close(self, *_):
        return hasattr(self, "session") and not self.flush()

    def on_pause(self):
        if hasattr(self, "session"):
            self.session.flush()
        return True

    def on_resume(self):
        if hasattr(self, "session"):
            self.session.flush()

    def on_stop(self):
        if hasattr(self, "session"):
            if not self.session.flush():
                Logger.error("PureNote: stopped with unsaved changes: %s", self.session.error)
            self.session.dispose()
            self.store.close()
        if self.documents:
            self.documents.close()
        if self.android_window:
            self.android_window.close()
        Window.unbind(on_keyboard=self._on_key, on_request_close=self._on_request_close)

    # Dialogs use the same typography and touch sizes as the writing surface.
    @staticmethod
    def message_label(text: str, *, scrollable=False) -> Label:
        label = Label(
            text=text,
            font_name=theme.FONT_BODY,
            font_size=theme.font(16),
            color=theme.TEXT,
            halign="left",
            valign="middle",
        )
        if scrollable:
            label.size_hint_y = None
            label.valign = "top"
            label.bind(
                width=lambda widget, width: setattr(widget, "text_size", (width, None)),
                texture_size=lambda widget, size: setattr(widget, "height", size[1]),
            )
        else:
            label.bind(size=lambda widget, size: setattr(widget, "text_size", size))
        return label

    def _dialog(self, title: str, content, *, height=0.65, preferred_height=None) -> Popup:
        if self._popup:
            self._popup.dismiss()
        popup = InsetPopup(
            title=title,
            content=content,
            size_hint=(None, None),
            background="",
            background_color=theme.PANEL,
            separator_color=theme.LINE,
            title_font=theme.FONT_BODY,
            title_color=theme.ACCENT,
            title_size=theme.font(18),
            title_align="left",
            padding=dp(16),
        )

        def fit(*_):
            left, top, right, bottom = self.insets
            width = max(dp(160), Window.width - left - right - dp(32))
            available = max(dp(140), Window.height - top - bottom - dp(32))
            popup.width = min(dp(440), width)
            popup.height = min(preferred_height or available * height, available)
            popup.safe_center = [
                left + (Window.width - left - right) / 2,
                bottom + (Window.height - top - bottom) / 2,
            ]
            popup.pos_hint = {
                "center_x": popup.safe_center[0] / Window.width,
                "center_y": popup.safe_center[1] / Window.height,
            }
            popup.center = popup.safe_center

        def dismissed(*_):
            Window.unbind(size=fit)
            self.unbind(insets=fit)
            if self._popup is popup:
                self._popup = None

        Window.bind(size=fit)
        self.bind(insets=fit)
        popup.bind(on_dismiss=dismissed)
        popup.bind(on_open=fit)
        fit()
        self._popup = popup
        popup.open()
        return popup

    def _button(self, text: str, callback: Callable, *, danger=False, primary=False):
        button = QuietButton(text=text, danger=danger, primary=primary)
        button.bind(on_release=lambda *_: callback())
        return button

    def _actions(self, title: str, actions: list[tuple[str, Callable]], message=""):
        box = BoxLayout(orientation="vertical", spacing=dp(12))
        if message:
            scroll = ScrollView(do_scroll_x=False)
            label = self.message_label(message, scrollable=True)
            scroll.add_widget(label)
            box.add_widget(scroll)
        items = BoxLayout(orientation="vertical", spacing=dp(6), size_hint_y=None)
        if actions:
            scroll = ScrollView(do_scroll_x=False)
            items.bind(minimum_height=items.setter("height"))
            scroll.add_widget(items)
            box.add_widget(scroll)
        button_height = max(dp(48), theme.font(15) + dp(28))
        preferred = dp(96) + (button_height + dp(6)) * (len(actions) + 1)
        popup = self._dialog(
            title, box, preferred_height=max(preferred, dp(400)) if message else preferred
        )
        for text, action in actions:

            def invoke(fn=action):
                popup.dismiss()
                fn()

            button = self._button(text, invoke)
            button.halign = "left"
            items.add_widget(button)
        box.add_widget(self._button("Chiudi", popup.dismiss))

    def show_message(self, message: str):
        self._actions("PureNote", [], message)

    def confirm(self, title: str, message: str, callback: Callable, label="Conferma"):
        box = BoxLayout(orientation="vertical", spacing=dp(12))
        scroll = ScrollView(do_scroll_x=False)
        scroll.add_widget(self.message_label(message, scrollable=True))
        box.add_widget(scroll)
        popup = self._dialog(title, box, preferred_height=dp(400))

        def accept():
            popup.dismiss()
            self._storage_action(callback)

        box.add_widget(self._button(label, accept, danger=label == "Elimina"))
        box.add_widget(self._button("Annulla", popup.dismiss))

    def _storage_action(self, action: Callable):
        try:
            action()
        except (sqlite3.Error, OSError, ValueError) as error:
            Logger.exception("PureNote: storage operation failed")
            self.show_message(f"Operazione non riuscita.\n\n{error}")

    def open_menu(self):
        self.editor.ids.body.focus = False
        actions = []
        if self.root.current == "editor":
            actions.extend(
                [
                    ("Nuova nota", self.new_note),
                    ("Condividi nota", self.share_note),
                    ("Sposta nel cestino", self.trash_note),
                ]
            )
            if self.session.error:
                actions.append(("Riprova salvataggio", self.flush))
        if self._undo_id is not None:
            actions.append(("Annulla ultima eliminazione", self.undo_trash))
        actions.extend(
            [
                ("Cestino", self.open_trash),
                ("Esporta backup", self.export_notes),
                ("Ripristina backup", self.restore_notes),
                ("Informazioni sui contatori", self.explain_counts),
            ]
        )
        self._actions("Opzioni nota" if self.root.current == "editor" else "Opzioni", actions)

    def explain_counts(self):
        self.show_message(
            "Parole: gruppi di testo separati da spazi.\n\n"
            "Caratteri: punti di codice Unicode, inclusi spazi e ritorni a capo. "
            "Alcune emoji sono composte da più caratteri.\n\n"
            "≈ Token: stima pari ai caratteri divisi per 4, arrotondata per eccesso. "
            "Il conteggio effettivo dipende dal modello."
        )

    def trash_note(self):
        if not self.flush():
            return
        note_id = self.session.note_id
        if note_id is None:
            self.go_list()
            return

        def move():
            self.store.set_trashed(note_id, True)
            self.session.open(None)
            self._undo_id = note_id
            self.go_list()
            self.root.get_screen("list").ids.undo.disabled = False
            if self._undo_event:
                self._undo_event.cancel()
            self._undo_event = Clock.schedule_once(self._expire_undo, 8)

        self._storage_action(move)

    def _expire_undo(self, *_):
        self._undo_id = None
        self.root.get_screen("list").ids.undo.disabled = True

    def undo_trash(self):
        if self._undo_id is None:
            return

        def restore():
            note_id = self._undo_id
            self.store.set_trashed(note_id, False)
            self._expire_undo()
            self.open_editor(note_id)

        self._storage_action(restore)

    def open_trash(self):
        if not self.flush():
            return
        notes = self.store.list_notes(trashed=True)
        actions = [(note.title, lambda nid=note.id: self._trash_actions(nid)) for note in notes]
        if notes:
            actions.append(
                (
                    "Svuota cestino…",
                    lambda: self.confirm(
                        "Svuota cestino",
                        "Eliminare definitivamente tutte le note del cestino?",
                        self._empty_trash,
                        "Elimina",
                    ),
                )
            )
        self._actions("Cestino", actions, "" if notes else "Il cestino è vuoto.")

    def _trash_actions(self, note_id: int):
        note = self.store.get(note_id)
        if note is None:
            return
        self._actions(
            "Nota nel cestino",
            [
                ("Ripristina", lambda: self._storage_action(lambda: self._restore_note(note_id))),
                (
                    "Elimina definitivamente…",
                    lambda: self.confirm(
                        "Elimina nota",
                        "La nota verrà eliminata definitivamente.",
                        lambda: self._delete_note(note_id),
                        "Elimina",
                    ),
                ),
            ],
            message=note.title,
        )

    def _restore_note(self, note_id):
        self.store.set_trashed(note_id, False)
        if self._undo_id == note_id:
            self._expire_undo()
        self.refresh_list()
        self.open_editor(note_id)

    def _delete_note(self, note_id):
        self.store.delete_forever(note_id)
        if self._undo_id == note_id:
            self._expire_undo()
        self.open_trash()

    def _empty_trash(self):
        self.store.delete_forever()
        self._expire_undo()
        self.open_trash()

    def share_note(self):
        text = self.session.text
        if not text.strip():
            self.show_message("La nota è vuota.")
        elif self.documents:
            self.documents.share(text)
        else:
            Clipboard.copy(text)
            self.show_message("Nota copiata negli appunti.")

    # Snapshot exports and complete validation happen before any import writes.
    def export_notes(self):
        if not self.flush():
            return

        def export():
            data = export_backup(self.store)
            name = time.strftime("purenote-%Y%m%d-%H%M%S.json")
            if self.documents:
                self.documents.export(name, data, lambda: self.show_message("Backup esportato."))
            else:
                self._desktop_file_dialog(save_data=data, name=name)

        self._storage_action(export)

    def restore_notes(self):
        if not self.flush():
            return
        if self.documents:
            self.documents.restore(self._preview_restore)
        else:
            self._desktop_file_dialog()

    def _preview_restore(self, data: bytes):
        try:
            notes = read_backup(data)
        except ValueError as error:
            self.show_message(str(error))
            return
        if not notes:
            self.show_message("Il backup non contiene note.")
            return

        def restore():
            if not self.flush():
                return
            count = self.store.import_notes(notes)
            self.refresh_list()
            self.show_message(f"Ripristinate {count} note.")

        self.confirm(
            "Ripristina backup",
            f"Aggiungere {len(notes)} note, incluso il cestino?\n\n"
            "Le note presenti verranno conservate. Importare lo stesso backup "
            "più volte crea copie aggiuntive.",
            restore,
            "Ripristina",
        )

    def _desktop_file_dialog(self, save_data: bytes | None = None, name=""):
        box = BoxLayout(orientation="vertical", spacing=dp(8))
        chooser = FileChooserListView(
            path=str(Path(self.store.path).resolve().parent),
            filters=[] if save_data is not None else ["*.json"],
        )
        box.add_widget(chooser)
        filename = NoteInput(text=name, multiline=False, size_hint_y=None, height=dp(48))
        if save_data is not None:
            box.add_widget(filename)
        popup = self._dialog(
            "Esporta backup" if save_data is not None else "Apri backup", box, height=0.9
        )

        def choose():
            try:
                if save_data is not None:
                    if not filename.text.strip() or Path(filename.text).name != filename.text:
                        raise ValueError("Inserisci un nome file senza cartelle.")
                    target = Path(chooser.path) / filename.text
                    # Never silently replace another backup.
                    with target.open("xb") as stream:
                        stream.write(save_data)
                    popup.dismiss()
                    self.show_message("Backup esportato.")
                elif chooser.selection:
                    with Path(chooser.selection[0]).open("rb") as stream:
                        data = stream.read(MAX_BACKUP_BYTES + 1)
                    popup.dismiss()
                    self._preview_restore(data)
            except (OSError, ValueError) as error:
                self.show_message(str(error))

        box.add_widget(
            self._button("Esporta" if save_data is not None else "Apri", choose, primary=True)
        )
        box.add_widget(self._button("Annulla", popup.dismiss))


if __name__ == "__main__":
    PureNoteApp().run()
