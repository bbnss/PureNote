"""Android document picker and sharing without broad storage permissions.

Provider I/O runs on a worker; callbacks return to the Kivy thread.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from threading import Thread

from kivy.clock import mainthread

from backup import MAX_BACKUP_BYTES


class AndroidDocuments:
    WRITE_BACKUP = 801
    READ_BACKUP = 802

    def __init__(self, on_error: Callable[[str], None]):
        from android import activity
        from jnius import autoclass

        self.activity_events = activity
        self.activity = autoclass("org.kivy.android.PythonActivity").mActivity
        self.Intent = autoclass("android.content.Intent")
        self.on_error = on_error
        self._pending: tuple | None = None
        activity.bind(on_activity_result=self._on_result)

    def export(self, name: str, data: bytes, on_saved: Callable[[], None]) -> None:
        self._pick(self.WRITE_BACKUP, name, data, on_saved)

    def restore(self, on_read: Callable[[bytes], None]) -> None:
        self._pick(self.READ_BACKUP, "", None, on_read)

    def _pick(self, code: int, name: str, data: bytes | None, callback: Callable) -> None:
        from android.runnable import run_on_ui_thread

        if self._pending is not None:
            self.on_error("Completa prima la selezione del file già aperta.")
            return
        self._pending = (code, data, callback)

        @run_on_ui_thread
        def launch():
            try:
                action = (
                    self.Intent.ACTION_CREATE_DOCUMENT
                    if code == self.WRITE_BACKUP
                    else self.Intent.ACTION_OPEN_DOCUMENT
                )
                intent = self.Intent(action)
                intent.addCategory(self.Intent.CATEGORY_OPENABLE)
                # Some document providers label JSON files as plain text.
                intent.setType("application/json" if code == self.WRITE_BACKUP else "*/*")
                if name:
                    intent.putExtra(self.Intent.EXTRA_TITLE, name)
                self.activity.startActivityForResult(intent, code)
            except Exception as error:
                self._failed(str(error))

        launch()

    @mainthread
    def _on_result(self, request_code, result_code, intent):
        if self._pending is None or self._pending[0] != request_code:
            return
        if result_code != -1 or intent is None or intent.getData() is None:
            self._pending = None
            return
        code, data, callback = self._pending
        uri = intent.getData()

        def transfer():
            try:
                resolver = self.activity.getContentResolver()
                mode = "w" if code == self.WRITE_BACKUP else "r"
                descriptor = resolver.openFileDescriptor(uri, mode)
                if descriptor is None:
                    raise OSError("Il documento non è accessibile.")
                # detachFd transfers ownership to Python; fdopen closes it on error too.
                fd = descriptor.detachFd()
                descriptor.close()
                with os.fdopen(fd, "wb" if data is not None else "rb") as stream:
                    if data is not None:
                        stream.write(data)
                        stream.flush()
                        result = None
                    else:
                        result = stream.read(MAX_BACKUP_BYTES + 1)
                self._completed(callback, result)
            except Exception as error:
                self._failed(str(error))

        Thread(target=transfer, name="purenote-document", daemon=True).start()

    @mainthread
    def _completed(self, callback, result):
        self._pending = None
        if result is None:
            callback()
        else:
            callback(result)

    @mainthread
    def _failed(self, message):
        self._pending = None
        self.on_error(f"Operazione sul file non riuscita.\n{message}")

    def share(self, text: str) -> None:
        from android.runnable import run_on_ui_thread
        from jnius import autoclass, cast

        @run_on_ui_thread
        def launch():
            try:
                String = autoclass("java.lang.String")
                intent = self.Intent(self.Intent.ACTION_SEND)
                intent.setType("text/plain")
                intent.putExtra(
                    self.Intent.EXTRA_TEXT, cast("java.lang.CharSequence", String(text))
                )
                chooser = self.Intent.createChooser(
                    intent, cast("java.lang.CharSequence", String("Condividi nota"))
                )
                self.activity.startActivity(chooser)
            except Exception as error:
                self._failed(str(error))

        launch()

    def close(self) -> None:
        self.activity_events.unbind(on_activity_result=self._on_result)
