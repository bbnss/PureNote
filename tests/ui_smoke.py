"""Exercise the real Kivy event loop; run under Xvfb in CI or a desktop session."""

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

os.environ["KIVY_NO_ARGS"] = "1"
os.environ.setdefault("KIVY_HOME", "/tmp/purenote-test-kivy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kivy.clock import Clock  # noqa: E402
from kivy.core.window import Window  # noqa: E402
from kivy.metrics import dp  # noqa: E402
from kivy.uix.label import Label  # noqa: E402

from main import PureNoteApp  # noqa: E402

OUTPUT = Path(os.environ.get("PURENOTE_SCREENSHOTS", "/tmp/purenote-preview"))
OUTPUT.mkdir(parents=True, exist_ok=True)
Window.size = (dp(390), dp(780))


class SmokeApp(PureNoteApp):
    failure = None

    def on_start(self):
        super().on_start()
        self.steps = iter(
            [
                self.first_run,
                self.autosaved,
                self.editor_capture,
                self.failure_and_retry,
                self.save_error_capture,
                self.navigation,
                self.list_capture,
                self.trash_and_restore,
                self.menu_capture,
                self.keyboard_layout,
                self.keyboard_dialog,
                self.narrow_screen,
                self.counts_dialog,
                self.counts_capture,
                self.finish,
            ]
        )
        Clock.schedule_once(self.next_step, 0.5)

    def next_step(self, _dt):
        try:
            next(self.steps)()
        except StopIteration:
            self.stop()
            return
        except Exception as error:
            self.failure = error
            self.stop()
            return
        Clock.schedule_once(self.next_step, 0.4)

    def first_run(self):
        assert self.root.current == "editor"
        assert not self.store.all_notes()
        assert self.editor.ids.body.width == Window.width
        self.editor.ids.body.text = (
            "Una cosa alla volta\n\n"
            "Un posto tranquillo per raccogliere idee, parole e piccoli promemoria.\n\n"
            "Oggi voglio lasciare più spazio alle cose semplici."
        )

    def autosaved(self):
        self.first_id = self.session.note_id
        assert self.first_id
        assert self.store.get(self.first_id).body == self.editor.ids.body.text
        assert self.editor.status == "Tutto salvato"

    def editor_capture(self):
        assert self.editor.counts.startswith("22 parole")
        assert self.editor.status == "Tutto salvato"
        self.assert_editor_layout()
        self.root.export_to_png(str(OUTPUT / "editor.png"))

    def failure_and_retry(self):
        self.real_save = self.store.save_note

        def fail(*_):
            raise sqlite3.OperationalError("simulated disk full")

        self.store.save_note = fail
        self.editor.ids.body.text += "\nUna modifica preziosa."
        self.go_list()
        assert self.root.current == "editor"
        assert self.session.dirty
        assert self.editor.save_error
        self._popup.dismiss()

    def save_error_capture(self):
        self.assert_editor_layout()
        self.root.export_to_png(str(OUTPUT / "save-error.png"))
        self.store.save_note = self.real_save
        self.editor.ids.body.text = self.editor.ids.body.text.removesuffix(
            "\nUna modifica preziosa."
        )
        assert self.flush()
        self.on_pause()
        self.on_resume()

    def navigation(self):
        self.new_note()
        self.editor.ids.body.text = "Idee per domani\n\nUna passeggiata senza fretta."
        self.go_list()
        self.second_id = self.session.note_id
        assert self.store.get(self.second_id).body.startswith("Idee per domani")
        assert len(self.store.list_notes()) == 2

    def list_capture(self):
        notes = self.root.get_screen("list").ids.notes
        assert notes.pos == notes.parent.pos
        assert notes.top == notes.parent.top
        self.root.export_to_png(str(OUTPUT / "list.png"))
        self.set_query("DOMANI")
        self.refresh_list()
        assert len(self.root.get_screen("list").ids.notes.data) == 1
        self.set_query("")
        self.refresh_list()
        self.open_editor(self.first_id)

    def trash_and_restore(self):
        self.trash_note()
        assert self.store.get(self.first_id).trashed
        self.undo_trash()
        assert not self.store.get(self.first_id).trashed
        assert self.session.note_id == self.first_id
        self.open_menu()

    def menu_capture(self):
        self._popup.export_to_png(str(OUTPUT / "menu.png"))
        self._popup.dismiss()
        # Simulate the layout reduction, without pretending this is a real IME test.
        self.insets = [0, dp(24), 0, dp(290)]

    def keyboard_layout(self):
        assert self.editor.ids.body.height > dp(120)
        assert self.editor.ids.body.y >= dp(290)
        self.assert_editor_layout()
        self.root.export_to_png(str(OUTPUT / "keyboard-layout.png"))
        self.explain_counts()

    def keyboard_dialog(self):
        self._popup.export_to_png(str(OUTPUT / "keyboard-dialog.png"))
        assert self._popup.y >= self.insets[3] - 1, (
            self._popup.pos,
            self._popup.size,
            self._popup.safe_center,
            Window.size,
            self.insets,
        )
        assert self._popup.top <= Window.height - self.insets[1] + 1
        self._popup.dismiss()
        self.insets = [0, 0, 0, 0]
        Window.size = (dp(320), dp(568))

    def narrow_screen(self):
        assert self.editor.ids.body.width == dp(320)
        assert self.editor.ids.body.height > dp(160)
        self.assert_editor_layout()
        self.root.export_to_png(str(OUTPUT / "small-screen.png"))
        self.explain_counts()

    def counts_dialog(self):
        assert self._popup is not None
        assert self._popup.width <= Window.width
        assert self._popup.height <= Window.height

    def assert_editor_layout(self):
        """Catch text bleeding and overlapping regions at Android densities."""
        body = self.editor.ids.body
        toolbar = self.editor.ids.toolbar
        footer = self.editor.ids.footer
        assert body.top <= toolbar.y + 1
        assert footer.top <= body.y + 1
        for region in (toolbar, footer):
            for widget in region.walk():
                if isinstance(widget, Label) and widget.text and widget.height:
                    assert widget.texture_size[1] <= widget.height + 1, (
                        widget.text,
                        widget.texture_size,
                        widget.size,
                    )

    def counts_capture(self):
        self._popup.export_to_png(str(OUTPUT / "counts.png"))
        self._popup.dismiss()

    def finish(self):
        assert not self.session.dirty
        assert len(self.store.list_notes()) == 2
        print(
            "UI smoke: editor, autosave, save failure/retry, navigation, search, trash/undo, IME layout OK"
        )


with tempfile.TemporaryDirectory(prefix="purenote-ui-") as directory:
    os.environ["PURENOTE_DB"] = str(Path(directory) / "notes.db")
    app = SmokeApp()
    app.run()
    if app.failure:
        raise app.failure
