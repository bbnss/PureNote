"""Offline text statistics with an explicitly approximate token count."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TextStats:
    words: int
    characters: int
    estimated_tokens: int


def count_text(text: str) -> TextStats:
    return TextStats(len(text.split()), len(text), (len(text) + 3) // 4)
