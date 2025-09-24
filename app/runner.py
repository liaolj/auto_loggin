"""Facade for running application workflows."""
from __future__ import annotations

from dataclasses import dataclass

from .config import AppConfig
from .history import HistoryLogger
from .signin import SigninOutcome, signin


@dataclass
class Runner:
    """High level runner orchestrating operations."""

    config: AppConfig
    history: HistoryLogger

    def call_signin(self, slot: str) -> SigninOutcome:
        return signin(self.config, slot, self.history)
