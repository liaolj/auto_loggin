"""Utility helpers for the AnyRouter auto sign-in tool."""
from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

import zoneinfo


def ensure_parent_dir(path: Path) -> None:
    """Ensure the parent directory of ``path`` exists."""

    path.parent.mkdir(parents=True, exist_ok=True)


def now_local(tz_name: str) -> datetime:
    """Return the current time in the given timezone."""

    tz = zoneinfo.ZoneInfo(tz_name)
    return datetime.now(tz=tz)


def json_dumps(data: Any) -> str:
    """Serialize ``data`` to JSON with deterministic formatting."""

    return json.dumps(data, ensure_ascii=False, sort_keys=True)


async def wait_for_input(prompt: str) -> str:
    """Wait for user input without blocking the event loop."""

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: input(prompt))


@dataclass
class ResponseSnapshot:
    """Stores a lightweight snapshot of a network response."""

    url: str
    status: int
    body: Optional[str] = None

    def to_json(self) -> str:
        return json_dumps(asdict(self))


def iter_lower(values: Iterable[str]) -> Iterable[str]:
    for value in values:
        yield value.lower()
