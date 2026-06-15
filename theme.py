"""Central retro/CRT theme for PureNote.

Colors are RGBA tuples in 0..1. The palette evokes an old phosphor terminal:
near-black background, phosphor green as the primary accent and a magenta
secondary, echoing the original app's green/magenta buttons.
"""

# ------------------------------------------------------------------ palette
BG        = (0.043, 0.055, 0.047, 1)   # #0b0e0c  deep CRT black-green
BG_PANEL  = (0.078, 0.094, 0.082, 1)   # #141815  raised panels / cards
BG_INPUT  = (0.027, 0.035, 0.030, 1)   # #070907  text fields
LINE      = (0.16, 0.22, 0.17, 1)      # subtle separators / borders

GREEN     = (0.25, 0.95, 0.45, 1)      # #40f273  primary phosphor accent
GREEN_DIM = (0.18, 0.55, 0.30, 1)      # dimmed green for secondary text
MAGENTA   = (0.95, 0.25, 0.75, 1)      # #f240bf  secondary accent
AMBER     = (1.0, 0.78, 0.30, 1)       # #ffc74d  warnings / pin highlight

TEXT      = (0.82, 0.95, 0.84, 1)      # main readable text (soft green-white)
TEXT_DIM  = (0.45, 0.58, 0.48, 1)      # metadata, placeholders
TEXT_INV  = (0.043, 0.055, 0.047, 1)   # text on bright (green) backgrounds
DANGER    = (0.95, 0.35, 0.35, 1)      # delete

# ------------------------------------------------------------------- fonts
FONT_MONO  = "GS.ttf"   # Green Screen — body / terminal feel
FONT_TITLE = "TT.ttf"   # 806 Typography — headers / buttons

# -------------------------------------------------------------------- sizes
FS_TITLE  = "22sp"
FS_BODY   = "17sp"
FS_META   = "12sp"
FS_BTN    = "16sp"

RADIUS = 6
PAD    = "12dp"
GAP    = "8dp"
