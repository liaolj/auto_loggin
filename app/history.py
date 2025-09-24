"""History persistence utilities."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from .utils import ensure_parent_dir, json_dumps


HISTORY_HEADERS = [
    "timestamp",
    "slot",
    "stage",
    "result",
    "err_category",
    "err_summary",
    "http_status",
    "duration_ms",
    "extra",
]


@dataclass
class HistoryEntry:
    """Represents a single history row."""

    timestamp: str
    slot: Optional[str]
    stage: str
    result: str
    err_category: Optional[str] = None
    err_summary: Optional[str] = None
    http_status: Optional[int] = None
    duration_ms: Optional[int] = None
    extra: Optional[dict] = None

    def as_row(self) -> List[str]:
        record = {
            "timestamp": self.timestamp,
            "slot": self.slot or "",
            "stage": self.stage,
            "result": self.result,
            "err_category": self.err_category or "",
            "err_summary": self.err_summary or "",
            "http_status": str(self.http_status) if self.http_status is not None else "",
            "duration_ms": str(self.duration_ms) if self.duration_ms is not None else "",
            "extra": json_dumps(self.extra) if self.extra else "",
        }
        return [record[key] for key in HISTORY_HEADERS]


class HistoryLogger:
    """Persist history entries to a CSV file."""

    def __init__(self, path: Path, max_rows: int = 2000) -> None:
        self.path = path
        self.max_rows = max_rows
        ensure_parent_dir(self.path)
        if not self.path.exists():
            with self.path.open("w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                writer.writerow(HISTORY_HEADERS)

    def append(self, entry: HistoryEntry) -> None:
        with self.path.open("a", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(entry.as_row())
        self._truncate_if_needed()

    def tail(self, limit: int = 20) -> List[HistoryEntry]:
        if limit <= 0:
            return []
        entries: List[HistoryEntry] = []
        if not self.path.exists():
            return entries
        with self.path.open("r", newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                entries.append(
                    HistoryEntry(
                        timestamp=row.get("timestamp", ""),
                        slot=row.get("slot") or None,
                        stage=row.get("stage", ""),
                        result=row.get("result", ""),
                        err_category=row.get("err_category") or None,
                        err_summary=row.get("err_summary") or None,
                        http_status=int(row["http_status"]) if row.get("http_status") else None,
                        duration_ms=int(row["duration_ms"]) if row.get("duration_ms") else None,
                        extra=None,
                    )
                )
        return entries[-limit:]

    def _truncate_if_needed(self) -> None:
        if self.max_rows <= 0:
            return
        with self.path.open("r", newline="", encoding="utf-8") as fh:
            reader = list(csv.reader(fh))
        header, *rows = reader
        if len(rows) <= self.max_rows:
            return
        trimmed = rows[-self.max_rows :]
        with self.path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(header)
            writer.writerows(trimmed)
