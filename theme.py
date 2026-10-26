"""A restrained terminal palette, with ordinary, readable writing typography."""

from pathlib import Path

from kivy.resources import resource_find

BG = (0.047, 0.071, 0.059, 1)
PANEL = (0.071, 0.102, 0.082, 1)
LINE = (0.16, 0.22, 0.18, 1)
ACCENT = (0.64, 0.86, 0.69, 1)
TEXT = (0.86, 0.90, 0.87, 1)
MUTED = (0.55, 0.65, 0.58, 1)
DANGER = (1.0, 0.61, 0.58, 1)
FONT_BODY = resource_find("data/fonts/Roboto-Regular.ttf")
FONT_MONO = resource_find("data/fonts/RobotoMono-Regular.ttf")
FONT_RETRO = str(Path(__file__).resolve().parent / "GS.ttf")
