"""PureNote — a retro/CRT local note app built with Kivy.

100% offline: notes live in a local SQLite file. Refreshed from the original
single-textbox version to a multi-note app with titles, dates, search, tags,
markdown preview and export/backup.
"""

import os
import time

from kivy.config import Config

from kivy.app import App
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import (
    BooleanProperty,
    ColorProperty,
    NumericProperty,
    ListProperty,
    StringProperty,
)
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen, ScreenManager, SlideTransition
from kivy.uix.textinput import TextInput

import theme
import md
from db import NoteStore


def _user_dir():
    """Writable base dir: app user_data_dir on Android, cwd elsewhere."""
    try:
        from android.storage import app_storage_path  # noqa

        return app_storage_path()
    except Exception:
        return os.path.dirname(os.path.abspath(__file__))


def _fmt_date(ts):
    if not ts:
        return ""
    return time.strftime("%d/%m/%Y %H:%M", time.localtime(ts))


def _snippet(body, n=90):
    text = " ".join((body or "").split())
    return text[:n] + ("..." if len(text) > n else "")


# ------------------------------------------------------------ styled widgets
# Defined in Python so `accent` always has a real (iterable) default before
# the kv canvas rules reference accent[0]/[1]/[2].
class RetroButton(ButtonBehavior, Label):
    accent = ColorProperty(theme.GREEN)


class GhostButton(ButtonBehavior, Label):
    accent = ColorProperty(theme.GREEN)


class IconButton(ButtonBehavior, Label):
    accent = ColorProperty(theme.GREEN)


class RetroInput(TextInput):
    pass


# ---------------------------------------------------------------- list screen
class NoteCard(ButtonBehavior, BoxLayout):
    note_id = NumericProperty(0)
    title = StringProperty()
    snippet = StringProperty()
    meta = StringProperty()
    pinned = BooleanProperty(False)

    def on_release(self):
        App.get_running_app().open_editor(self.note_id)

    def toggle_pin(self):
        app = App.get_running_app()
        app.store.set_pinned(self.note_id, not self.pinned)
        app.refresh_list()


class TagChip(ButtonBehavior, BoxLayout):
    tag = StringProperty()
    active = BooleanProperty(False)

    def on_release(self):
        app = App.get_running_app()
        app.set_tag_filter("" if self.active else self.tag)


class ListScreen(Screen):
    query = StringProperty("")
    active_tag = StringProperty("")


# -------------------------------------------------------------- editor screen
class EditorScreen(Screen):
    note_id = NumericProperty(0)        # 0 == new note
    preview = BooleanProperty(False)
    pinned = BooleanProperty(False)
    counts = StringProperty("")
    preview_markup = StringProperty("")

    def load(self, note_id):
        self.note_id = note_id or 0
        self.preview = False
        app = App.get_running_app()
        if note_id:
            n = app.store.get(note_id)
            self.ids.title.text = n["title"]
            self.ids.body.text = n["body"]
            self.ids.tags.text = n["tags"]
            self.pinned = bool(n["pinned"])
        else:
            self.ids.title.text = ""
            self.ids.body.text = ""
            self.ids.tags.text = ""
            self.pinned = False
        self.update_counts()

    def update_counts(self, *_):
        body = self.ids.body.text
        chars = len(body)
        words = len(body.split())
        self.counts = f"{words} parole / {chars} caratteri"

    def toggle_preview(self):
        if not self.preview:
            self.preview_markup = md.to_markup(self.ids.body.text)
        self.preview = not self.preview

    def toggle_pin(self):
        self.pinned = not self.pinned

    def save(self):
        app = App.get_running_app()
        title = self.ids.title.text.strip()
        body = self.ids.body.text
        tags = ",".join(
            t.strip() for t in self.ids.tags.text.split(",") if t.strip()
        )
        if not title and not body.strip():
            app.go_list()
            return
        if not title:
            title = NoteStore._title_from_body(body)
        if self.note_id:
            app.store.update(self.note_id, title, body, tags, self.pinned)
        else:
            self.note_id = app.store.add(title, body, tags, self.pinned)
        app.go_list()

    def delete(self):
        app = App.get_running_app()
        if self.note_id:
            app.confirm(
                f'Eliminare "{self.ids.title.text or "questa nota"}"?',
                self._do_delete,
            )
        else:
            app.go_list()

    def _do_delete(self):
        app = App.get_running_app()
        app.store.delete(self.note_id)
        app.go_list()

    def export(self):
        App.get_running_app().export_note(
            self.ids.title.text, self.ids.body.text
        )


class RootManager(ScreenManager):
    pass


# ----------------------------------------------------------------------- app
class PureNoteApp(App):
    tags = ListProperty([])

    def build(self):
        self.title = "PureNote"
        Window.clearcolor = theme.BG
        os.environ.setdefault(
            "PURENOTE_DB", os.path.join(_user_dir(), "notes.db")
        )
        # Keep the bundled legacy/seed db if the user dir is empty.
        seed = os.path.join(os.path.dirname(__file__), "notes.db")
        target = os.environ["PURENOTE_DB"]
        if seed != target and not os.path.exists(target) and os.path.exists(seed):
            import shutil

            shutil.copyfile(seed, target)
        self.store = NoteStore(target)
        root = Builder.load_file(
            os.path.join(os.path.dirname(__file__), "purenote_ui.kv")
        )
        Clock.schedule_once(lambda *_: self.refresh_list(), 0)
        return root

    # ----------------------------------------------------------- navigation
    @property
    def sm(self):
        return self.root

    def open_editor(self, note_id):
        self.sm.transition = SlideTransition(direction="left")
        self.sm.get_screen("editor").load(note_id)
        self.sm.current = "editor"

    def new_note(self):
        self.open_editor(0)

    def go_list(self):
        self.sm.transition = SlideTransition(direction="right")
        self.sm.current = "list"
        self.refresh_list()

    # -------------------------------------------------------------- list data
    def set_query(self, text):
        self.sm.get_screen("list").query = text
        self.refresh_list()

    def set_tag_filter(self, tag):
        self.sm.get_screen("list").active_tag = tag
        self.refresh_list()

    def refresh_list(self):
        ls = self.sm.get_screen("list")
        notes = self.store.list(query=ls.query, tag=ls.active_tag)
        ls.ids.rv.data = [
            {
                "note_id": n["id"],
                "title": n["title"] or "Senza titolo",
                "snippet": _snippet(n["body"]),
                "meta": _fmt_date(n["updated_at"]),
                "pinned": bool(n["pinned"]),
            }
            for n in notes
        ]
        ls.ids.empty.opacity = 0 if notes else 1
        self._rebuild_tags(ls)

    def _rebuild_tags(self, ls):
        bar = ls.ids.tagbar
        bar.clear_widgets()
        tags = self.store.all_tags()
        for t in tags:
            chip = TagChip(tag=t, active=(t == ls.active_tag))
            bar.add_widget(chip)
        ls.ids.tagscroll.opacity = 1 if tags else 0
        ls.ids.tagscroll.height = "36dp" if tags else 0

    # ----------------------------------------------------------------- export
    def export_note(self, title, body):
        safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in title).strip()
        safe = (safe or "nota")[:40]
        out_dir = os.path.join(_user_dir(), "PureNote_export")
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, f"{safe}.md")
        content = f"# {title}\n\n{body}\n" if title else (body or "")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        self._share_or_toast(path, content)

    def export_db(self):
        import shutil

        out_dir = os.path.join(_user_dir(), "PureNote_export")
        os.makedirs(out_dir, exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        path = os.path.join(out_dir, f"purenote_backup_{stamp}.db")
        shutil.copyfile(self.store.path, path)
        self.toast(f"Backup salvato:\n{path}")

    def _share_or_toast(self, path, content):
        try:
            from plyer import share  # noqa

            share.share(text=content)
            return
        except Exception:
            pass
        self.toast(f"Esportato in:\n{path}")

    # ------------------------------------------------------------- ui helpers
    def toast(self, message):
        from kivy.uix.popup import Popup
        from kivy.uix.label import Label

        Popup(
            title="PureNote",
            size_hint=(0.85, 0.4),
            content=Label(text=message, font_name=theme.FONT_MONO),
        ).open()

    def confirm(self, message, on_yes):
        from kivy.uix.popup import Popup
        from kivy.uix.label import Label
        from kivy.uix.button import Button

        box = BoxLayout(orientation="vertical", spacing=10, padding=10)
        box.add_widget(Label(text=message, font_name=theme.FONT_MONO))
        row = BoxLayout(size_hint_y=None, height="48dp", spacing=10)
        popup = Popup(title="Conferma", content=box, size_hint=(0.85, 0.45))

        def yes(*_):
            popup.dismiss()
            on_yes()

        row.add_widget(Button(text="Annulla", on_release=popup.dismiss))
        row.add_widget(Button(text="Elimina", on_release=yes))
        box.add_widget(row)
        popup.open()

    def open_backup_menu(self):
        from kivy.uix.popup import Popup
        from kivy.uix.button import Button

        box = BoxLayout(orientation="vertical", spacing=10, padding=10)
        popup = Popup(title="Backup & Export", content=box, size_hint=(0.85, 0.5))

        def do(fn):
            popup.dismiss()
            fn()

        b1 = Button(text="Esporta backup DB", font_name=theme.FONT_TITLE)
        b1.bind(on_release=lambda *_: do(self.export_db))
        box.add_widget(b1)
        b2 = Button(text="Chiudi", font_name=theme.FONT_TITLE)
        b2.bind(on_release=popup.dismiss)
        box.add_widget(b2)
        popup.open()


if __name__ == "__main__":
    PureNoteApp().run()
