"""Authorization helpers for AnyRouter auto sign-in."""
from __future__ import annotations

import asyncio

from .config import AppConfig
from .history import HistoryEntry, HistoryLogger
from .utils import now_local, wait_for_input


def _format_timestamp(config: AppConfig) -> str:
    return now_local(config.schedule.timezone).isoformat()


async def _authorize_async(config: AppConfig, history: HistoryLogger) -> None:
    from playwright.async_api import async_playwright  # Imported lazily

    timestamp = _format_timestamp(config)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=config.playwright.slow_mo_ms)
        context = await browser.new_context()
        page = await context.new_page()
        print("Opening AnyRouter for manual GitHub authorization...")
        await page.goto(config.playwright.base_url, wait_until="load")
        print(
            "Complete the authorization in the browser window. "
            "When the AnyRouter dashboard is visible, return to this terminal."
        )
        await wait_for_input("Press ENTER to capture the session once authorization is completed...")
        await context.storage_state(path=str(config.playwright.storage_state_path))
        await browser.close()
        print(f"Authorization stored to {config.playwright.storage_state_path}")

    history.append(
        HistoryEntry(
            timestamp=timestamp,
            slot=None,
            stage="authorize",
            result="success",
            err_summary="GitHub authorization completed",
        )
    )


def authorize(config: AppConfig, history: HistoryLogger) -> None:
    """Run the manual authorization flow."""

    asyncio.run(_authorize_async(config, history))


def revoke(config: AppConfig, history: HistoryLogger) -> None:
    """Remove the stored session information."""

    storage_path = config.playwright.storage_state_path
    timestamp = _format_timestamp(config)
    if storage_path.exists():
        storage_path.unlink()
        print(f"Removed {storage_path}")
        history.append(
            HistoryEntry(
                timestamp=timestamp,
                slot=None,
                stage="revoke",
                result="success",
                err_summary="Session revoked",
            )
        )
    else:
        print(f"No storage state found at {storage_path}")
        history.append(
            HistoryEntry(
                timestamp=timestamp,
                slot=None,
                stage="revoke",
                result="noop",
                err_summary="Storage state file missing",
            )
        )
