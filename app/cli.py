"""Command line entry points for the AnyRouter auto sign-in tool."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Callable, Optional

from . import auth, runner
from .config import AppConfig, ConfigError, load_config
from .history import HistoryLogger


def _load_config(path: Optional[Path]) -> AppConfig:
    try:
        return load_config(path)
    except ConfigError as exc:
        raise SystemExit(str(exc)) from exc


def _build_history(config: AppConfig) -> HistoryLogger:
    return HistoryLogger(config.history.csv_path, max_rows=config.history.max_rows)


def cmd_authorize(args: argparse.Namespace) -> None:
    cfg = _load_config(args.config)
    history = _build_history(cfg)
    auth.authorize(cfg, history)


def cmd_signin(args: argparse.Namespace) -> None:
    cfg = _load_config(args.config)
    history = _build_history(cfg)
    run = runner.Runner(cfg, history)
    outcome = run.call_signin(args.slot)
    print(f"Sign-in result: {outcome.status} - {outcome.message}")
    if outcome.err_category:
        print(f"Category: {outcome.err_category}")
    if outcome.http_status:
        print(f"HTTP status: {outcome.http_status}")


def cmd_revoke(args: argparse.Namespace) -> None:
    cfg = _load_config(args.config)
    history = _build_history(cfg)
    auth.revoke(cfg, history)


def cmd_status(args: argparse.Namespace) -> None:
    cfg = _load_config(args.config)
    history = _build_history(cfg)
    entries = history.tail(args.last)
    if not entries:
        print("No history entries yet")
        return
    for entry in entries:
        print(
            f"[{entry.timestamp}] slot={entry.slot or '-'} stage={entry.stage} "
            f"result={entry.result} err={entry.err_category or '-'} summary={entry.err_summary or '-'}"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Automate AnyRouter sign-in via Playwright")
    parser.add_argument("--config", type=Path, default=None, help="Path to config.toml")

    subparsers = parser.add_subparsers(dest="command", required=True)

    sub_authorize = subparsers.add_parser("authorize", help="Run manual authorization flow")
    sub_authorize.set_defaults(func=cmd_authorize)

    sub_signin = subparsers.add_parser("signin", help="Trigger a sign-in attempt")
    sub_signin.add_argument("--slot", default="morning", help="Slot name (morning/noon/evening)")
    sub_signin.set_defaults(func=cmd_signin)

    sub_revoke = subparsers.add_parser("revoke", help="Clear stored authorization state")
    sub_revoke.set_defaults(func=cmd_revoke)

    sub_status = subparsers.add_parser("status", help="Display recent history entries")
    sub_status.add_argument("--last", type=int, default=20, help="Number of history records to display")
    sub_status.set_defaults(func=cmd_status)

    return parser


def main(argv: Optional[list[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    func: Callable[[argparse.Namespace], None] = getattr(args, "func")
    func(args)


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()
