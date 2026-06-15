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


def to_markup(source):
    out = []
    for raw in (source or "").splitlines():
        stripped = raw.strip()

        # Headings
        m = re.match(r"(#{1,3})\s+(.*)", stripped)
        if m:
            level = len(m.group(1))
            size = {1: 26, 2: 22, 3: 19}[level]
            out.append(
                f"[size={size}sp][b][color=#{_GREEN}]{_content(m.group(2))}"
                f"[/color][/b][/size]"
            )
            continue

        # Checklist items: - [ ] / - [x]
        m = re.match(r"[-*]\s+\[( |x|X)\]\s+(.*)", stripped)
        if m:
            checked = m.group(1).lower() == "x"
            if checked:
                box = f"[color=#{_GREEN}]&bl;x&br;[/color]"
            else:
                box = f"[color=#{_DIM}]&bl; &br;[/color]"
            body = _content(m.group(2))
            if checked:
                body = f"[color=#{_DIM}]{body}[/color]"
            out.append(f"  {box} {body}")
            continue

        # Bullet list
        m = re.match(r"[-*]\s+(.*)", stripped)
        if m:
            out.append(f"  [color=#{_MAGENTA}]>[/color] {_content(m.group(1))}")
            continue

        out.append(_content(raw))

    return "\n".join(out)
