"""A restrained terminal palette, with ordinary, readable writing typography."""

from pathlib import Path

from kivy.metrics import Metrics, sp
from kivy.resources import resource_find

BG = (0.047, 0.071, 0.059, 1)
PANEL = (0.071, 0.102, 0.082, 1)
BUTTON = (0.10, 0.145, 0.115, 1)
LINE = (0.16, 0.22, 0.18, 1)
ACCENT = (0.64, 0.86, 0.69, 1)
TEXT = (0.86, 0.90, 0.87, 1)
MUTED = (0.55, 0.65, 0.58, 1)
DANGER = (1.0, 0.61, 0.58, 1)
FONT_BODY = resource_find("data/fonts/Roboto-Regular.ttf")
FONT_MONO = resource_find("data/fonts/RobotoMono-Regular.ttf")
FONT_RETRO = str(Path(__file__).resolve().parent / "GS.ttf")

_android_font = None


def font(size: float) -> float:
    """Convert text sizes through Android's font scaling curve when available."""
    return _android_font(size) if _android_font else sp(size)


def configure_android_scaling():
    """Separate display density from font scaling, including Android 14+ curves."""
    from functools import lru_cache

    from jnius import autoclass
    from kivy.logger import Logger

    global _android_font
    activity = autoclass("org.kivy.android.PythonActivity").mActivity
    resources = activity.getResources()
    display = resources.getDisplayMetrics()
    typed_value = autoclass("android.util.TypedValue")
    # Kivy 2.3.1 reads scaledDensity for dp and scales sp a second time.
    # Layout uses the physical display density; text uses Android's converter.
    Metrics.density = display.density
    Metrics.fontscale = resources.getConfiguration().fontScale

    @lru_cache(maxsize=64)
    def android_font(size):
        return typed_value.applyDimension(typed_value.COMPLEX_UNIT_SP, float(size), display)

    _android_font = android_font
    Logger.info(
        "PureNote: density=%s fontScale=%s text18px=%s",
        Metrics.density,
        Metrics.fontscale,
        font(18),
    )
