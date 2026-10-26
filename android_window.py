"""Insets for system bars and the IME on Android's SDL2 window."""

from kivy.clock import Clock, mainthread


class AndroidWindow:
    def __init__(self, on_insets):
        from android.runnable import run_on_ui_thread
        from jnius import autoclass

        self.on_insets = on_insets
        self.activity = autoclass("org.kivy.android.PythonActivity").mActivity
        self.api = autoclass("android.os.Build$VERSION").SDK_INT
        self.types = autoclass("android.view.WindowInsets$Type") if self.api >= 30 else None

        @run_on_ui_thread
        def configure():
            window = self.activity.getWindow()
            # On modern Android we handle the keyboard insets ourselves. Kivy's
            # SDL2 resize mode does not report IME height reliably.
            window.setSoftInputMode(48 if self.api >= 30 else 16)
            if self.api >= 30:
                window.setDecorFitsSystemWindows(False)
                controller = window.getInsetsController()
                if controller:
                    controller.setSystemBarsAppearance(0, 8 | 16)
            window.setStatusBarColor(0xFF101914 - 2**32)
            window.setNavigationBarColor(0xFF101914 - 2**32)
            self._read()

        self._read_on_ui = run_on_ui_thread(self._read)
        configure()
        self._event = Clock.schedule_interval(lambda _dt: self._read_on_ui(), 0.25)

    def _read(self):
        view = self.activity.getWindow().getDecorView()
        insets = view.getRootWindowInsets()
        if insets is None:
            return
        if self.types:
            edges = insets.getInsets(
                self.types.systemBars() | self.types.displayCutout() | self.types.ime()
            )
            self._deliver(edges.left, edges.top, edges.right, edges.bottom)
        else:
            # Legacy Android fits system bars and resizes the native surface
            # for the IME. Adding the same insets again would pad twice.
            self._deliver(0, 0, 0, 0)

    @mainthread
    def _deliver(self, left, top, right, bottom):
        self.on_insets(left, top, right, bottom)

    def close(self):
        self._event.cancel()
