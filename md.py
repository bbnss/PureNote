"""Tiny Markdown -> Kivy markup converter for the preview pane.

Supports the subset that makes sense on a phone note: headings, bold,
italic, inline code, bullet lists and ``- [ ]`` / ``- [x]`` checklists.
Kivy Labels render a BBCode-like markup when ``markup=True``.
"""

import re

from theme import GREEN, MAGENTA, AMBER, TEXT_DIM


def _rgba_to_hex(rgba):
    r, g, b, _ = rgba
    return f"{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"


_GREEN = _rgba_to_hex(GREEN)
_MAGENTA = _rgba_to_hex(MAGENTA)
_AMBER = _rgba_to_hex(AMBER)
_DIM = _rgba_to_hex(TEXT_DIM)


def _escape(text):
    # Kivy markup uses [ ] for tags; escape literals so they render.
    return text.replace("&", "&amp;").replace("[", "&bl;").replace("]", "&br;")


def _content(text):
    """Escape literals then apply inline markdown -> markup."""
    return _inline(_escape(text))


def _inline(text):
    """Convert inline markdown (already escaped) to Kivy markup."""
    # `code`
    text = re.sub(r"`([^`]+)`", rf"[color=#{_AMBER}]\1[/color]", text)
    # **bold** or __bold__
    text = re.sub(r"(\*\*|__)(.+?)\1", r"[b]\2[/b]", text)
    # *italic* or _italic_
    text = re.sub(r"(?<!\*)\*(?!\*)([^*]+)\*(?!\*)", r"[i]\1[/i]", text)
    text = re.sub(r"(?<!_)_(?!_)([^_]+)_(?!_)", r"[i]\1[/i]", text)
    return text


# A checklist line: optional leading space, - or *, then [ ], [x] or [X].
CHECK_RE = re.compile(r"[-*]\s+\[( |x|X)\]\s+(.*)")


def _line_markup(raw):
    """Convert a single non-checklist line to Kivy markup."""
    stripped = raw.strip()

    # Headings
    m = re.match(r"(#{1,3})\s+(.*)", stripped)
    if m:
        level = len(m.group(1))
        size = {1: 26, 2: 22, 3: 19}[level]
        return (
            f"[size={size}sp][b][color=#{_GREEN}]{_content(m.group(2))}"
            f"[/color][/b][/size]"
        )

    # Bullet list
    m = re.match(r"[-*]\s+(.*)", stripped)
    if m:
        return f"  [color=#{_MAGENTA}]>[/color] {_content(m.group(1))}"

    return _content(raw)


def _check_label(checked, text):
    """Markup for the text part of a checklist item (dimmed when checked)."""
    body = _content(text)
    return f"[color=#{_DIM}]{body}[/color]" if checked else body


def to_markup(source):
    """Render the whole source to a single markup string (static preview)."""
    out = []
    for raw in (source or "").split("\n"):
        m = CHECK_RE.match(raw.strip())
        if m:
            checked = m.group(1).lower() == "x"
            box = (
                f"[color=#{_GREEN}]&bl;x&br;[/color]"
                if checked
                else f"[color=#{_DIM}]&bl; &br;[/color]"
            )
            out.append(f"  {box} {_check_label(checked, m.group(2))}")
        else:
            out.append(_line_markup(raw))
    return "\n".join(out)


def to_blocks(source):
    """Split the source into render blocks for an interactive preview.

    Returns a list of dicts. Consecutive non-checklist lines are merged into
    one ``{"type": "markup", "text": ...}`` block; every checklist line becomes
    its own ``{"type": "check", "checked": bool, "label": markup, "line": idx}``
    block, where ``line`` is the 0-based index into ``source.split("\\n")`` so a
    tap can toggle that exact line back in the body text.
    """
    blocks = []
    buf = []

    def flush():
        if buf:
            blocks.append({"type": "markup", "text": "\n".join(buf)})
            buf.clear()

    for idx, raw in enumerate((source or "").split("\n")):
        m = CHECK_RE.match(raw.strip())
        if m:
            flush()
            checked = m.group(1).lower() == "x"
            blocks.append(
                {
                    "type": "check",
                    "checked": checked,
                    "label": _check_label(checked, m.group(2)),
                    "line": idx,
                }
            )
        else:
            buf.append(_line_markup(raw))
    flush()
    return blocks
