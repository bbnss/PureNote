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


class ToolButton(ButtonBehavior, BoxLayout):
    """Toolbar button rendered as an icon glyph over a small text label."""
    glyph = StringProperty()
    label = StringProperty()
    accent = ColorProperty(theme.GREEN)


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
    _loading = False

    def load(self, note_id):
        self._loading = True
        self.note_id = note_id or 0
        self._set_preview(False)
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
        self._loading = False

    # ------------------------------------------------------------- text/save
    def on_text_changed(self):
        """Bound to every input's on_text: refresh counts and debounce save."""
        self.update_counts()
        if not self._loading:
            Clock.unschedule(self._autosave)
            Clock.schedule_once(self._autosave, 1.0)

    def _autosave(self, *_):
        self._persist()

    def update_counts(self, *_):
        body = self.ids.body.text
        self.counts = f"{len(body.split())} par / {len(body)} car"

    def _persist(self):
        """Write the note to the DB without navigating. Returns True if saved."""
        app = App.get_running_app()
        title = self.ids.title.text.strip()
        body = self.ids.body.text
        tags = ",".join(
            t.strip() for t in self.ids.tags.text.split(",") if t.strip()
        )
        if not title and not body.strip():
            return False
        if not title:
            title = NoteStore._title_from_body(body)
        if self.note_id:
            app.store.update(self.note_id, title, body, tags, self.pinned)
        else:
            self.note_id = app.store.add(title, body, tags, self.pinned)
        return True

    def manual_save(self):
        Clock.unschedule(self._autosave)
        if self._persist():
            App.get_running_app().flash("Salvato")
        else:
            App.get_running_app().flash("Nota vuota")

    # ---------------------------------------------------------------- actions
    def _set_preview(self, on):
        """Toggle preview mode.

        The preview pane stays in the tree but collapses to size 0 while
        editing (a 0-size widget can't intercept touches meant for the body;
        a merely-disabled full-size overlay still swallows them on Android).
        """
        if on:
            self.preview_markup = md.to_markup(self.ids.body.text)
        self.preview = on

    def toggle_preview(self):
        self._set_preview(not self.preview)

    def toggle_pin(self):
        self.pinned = not self.pinned
        if self.note_id:
            self._persist()

    def delete(self):
        app = App.get_running_app()
        Clock.unschedule(self._autosave)
        if self.note_id:
            app.confirm(
                f'Eliminare "{self.ids.title.text or "questa nota"}"?',
                self._do_delete,
            )
        else:
            app.go_list(save=False)

    def _do_delete(self):
        app = App.get_running_app()
        app.store.delete(self.note_id)
        self.note_id = 0
        app.go_list(save=False)

    def export(self):
        App.get_running_app().share_note(
            self.ids.title.text, self.ids.body.text
        )


class RootManager(ScreenManager):
    pass


# ----------------------------------------------------------------------- app
class PureNoteApp(App):
    tags = ListProperty([])
    # Safe-area insets (px). Android 15 (target API 35) draws edge-to-edge,
    # so we pad content away from the status bar (top) and nav bar (bottom).
    inset_top = NumericProperty(0)
    inset_bottom = NumericProperty(0)

    def build(self):
        self.title = "PureNote"
        Window.clearcolor = theme.BG
        self._read_android_insets()
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
        Window.bind(on_keyboard=self._on_key)
        Clock.schedule_once(lambda *_: self.refresh_list(), 0)
        return root

    def _on_key(self, window, key, *args):
        # Android back / Esc: from the editor, save and return to the list
        # (consume the event); from the list, let it close the app.
        if key == 27:
            if self.sm.current == "editor":
                self.go_list()
                return True
        return False

    def _read_android_insets(self):
        """Read system bar heights (px) so content clears the status/nav bars.

        Android 15 enforces edge-to-edge for apps targeting API 35; without
        this the top bar hides under the clock and the Save button/FAB hide
        under the gesture/nav bar. No-op on desktop.
        """
        try:
            from jnius import autoclass

            activity = autoclass("org.kivy.android.PythonActivity").mActivity
            res = activity.getResources()

            def dim(name):
                rid = res.getIdentifier(name, "dimen", "android")
                return res.getDimensionPixelSize(rid) if rid > 0 else 0

            self.inset_top = dim("status_bar_height")
            self.inset_bottom = dim("navigation_bar_height")
        except Exception:
            self.inset_top = 0
            self.inset_bottom = 0

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

    def go_list(self, save=True):
        editor = self.sm.get_screen("editor")
        Clock.unschedule(editor._autosave)
        if save:
            editor._persist()
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

    # --------------------------------------------------------- share / export
    def share_note(self, title, body):
        """Open the native Android share sheet with the note as plain text."""
        text = (f"{title}\n\n{body}".strip() if title else (body or "")).strip()
        if not text:
            self.flash("Nota vuota")
            return
        try:
            from jnius import autoclass, cast

            Intent = autoclass("android.content.Intent")
            String = autoclass("java.lang.String")
            activity = autoclass("org.kivy.android.PythonActivity").mActivity

            intent = Intent()
            intent.setAction(Intent.ACTION_SEND)
            intent.setType("text/plain")
            intent.putExtra(
                Intent.EXTRA_TEXT, cast("java.lang.CharSequence", String(text))
            )
            if title:
                intent.putExtra(
                    Intent.EXTRA_SUBJECT,
                    cast("java.lang.CharSequence", String(title)),
                )
            chooser = Intent.createChooser(
                intent, cast("java.lang.CharSequence", String("Condividi nota"))
            )
            activity.startActivity(chooser)
        except Exception:
            # Desktop fallback: write a .md file and report where.
            self._export_note_file(title, body)

    def _export_note_file(self, title, body):
        safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in title).strip()
        safe = (safe or "nota")[:40]
        out_dir = os.path.join(_user_dir(), "PureNote_export")
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, f"{safe}.md")
        content = f"# {title}\n\n{body}\n" if title else (body or "")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        self.toast(f"Esportato in:\n{path}")

    def export_db(self):
        import shutil

        out_dir = os.path.join(_user_dir(), "PureNote_export")
        os.makedirs(out_dir, exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        path = os.path.join(out_dir, f"purenote_backup_{stamp}.db")
        shutil.copyfile(self.store.path, path)
        self.toast(f"Backup salvato:\n{path}")

    # ------------------------------------------------------------- ui helpers
    def flash(self, message):
        """Brief, non-blocking confirmation that fades out."""
        from kivy.uix.label import Label
        from kivy.animation import Animation

        lbl = Label(
            text=message,
            font_name=theme.FONT_TITLE,
            font_size=theme.FS_BTN,
            color=(theme.GREEN[0], theme.GREEN[1], theme.GREEN[2], 1),
            size_hint=(None, None),
            size=(Window.width, "40dp"),
        )
        lbl.center_x = Window.width / 2
        lbl.y = Window.height * 0.12 + self.inset_bottom
        Window.add_widget(lbl)
        anim = Animation(opacity=0, duration=1.3, t="in_quad")
        anim.bind(on_complete=lambda *a: Window.remove_widget(lbl))
        anim.start(lbl)

    def toast(self, message):
        from kivy.uix.popup import Popup
        from kivy.uix.label import Label

        content = Label(
            text=message,
            font_name=theme.FONT_MONO,
            halign="center",
            valign="middle",
        )
        content.bind(size=lambda lbl, s: setattr(lbl, "text_size", s))
        Popup(title="PureNote", size_hint=(0.85, 0.4), content=content).open()

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
