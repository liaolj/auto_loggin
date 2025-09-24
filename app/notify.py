"""Notification stubs for future development (SMTP emails)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass
class EmailMessage:
    subject: str
    body: str
    to: Iterable[str]


def send_email(message: EmailMessage) -> None:  # pragma: no cover - placeholder
    """Placeholder email sender. Will be implemented in later milestones."""

    raise NotImplementedError("SMTP notifications will be implemented in milestone P4")
