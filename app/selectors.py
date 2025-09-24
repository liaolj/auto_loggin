"""Helpers for working with selector configuration."""
from __future__ import annotations

from typing import Iterable


def match_any_keyword(text: str, keywords: Iterable[str]) -> bool:
    """Return ``True`` if any keyword appears in ``text`` (case-insensitive)."""

    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in keywords)
