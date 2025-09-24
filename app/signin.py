"""Automated sign-in workflow implementation."""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from typing import Optional

from .config import AppConfig
from .history import HistoryEntry, HistoryLogger
from .selectors import match_any_keyword
from .utils import ResponseSnapshot, now_local


@dataclass
class SigninOutcome:
    """Result of a sign-in attempt."""

    status: str
    message: str
    err_category: Optional[str] = None
    err_summary: Optional[str] = None
    http_status: Optional[int] = None
    response: Optional[ResponseSnapshot] = None


class SigninError(RuntimeError):
    """Base exception for sign-in errors."""


class AuthInvalidError(SigninError):
    """Raised when the session is considered invalid."""


def _parse_response(snapshot: ResponseSnapshot, config: AppConfig) -> tuple[str, Optional[str]]:
    """Interpret the API response."""

    body = snapshot.body or ""
    lowered = body.lower()
    selectors = config.selectors.api
    if selectors.checkin_path_contains and selectors.checkin_path_contains not in snapshot.url:
        return "unknown", "Unexpected API endpoint"

    if match_any_keyword(lowered, selectors.already_keywords):
        return "already", body

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        payload = None

    if payload and any(str(payload.get(key, "")).lower() in {"true", "ok", "success"} for key in selectors.success_keys):
        return "success", body

    if payload and any(match_any_keyword(str(payload.get(key, "")), selectors.already_keywords) for key in selectors.success_keys):
        return "already", body

    if match_any_keyword(lowered, selectors.success_keys):
        return "success", body

    return "failure", body


async def _signin_async(config: AppConfig, slot: str, history: HistoryLogger):
    from playwright.async_api import Error as PlaywrightError
    from playwright.async_api import async_playwright

    storage_path = config.playwright.storage_state_path
    if not storage_path.exists():
        raise AuthInvalidError("storage_state.json not found. Please run authorize first.")

    timestamp = now_local(config.schedule.timezone).isoformat()
    start = time.perf_counter()
    outcome = SigninOutcome(status="failure", message="Unknown error", err_category="unknown")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=config.playwright.headless, slow_mo=config.playwright.slow_mo_ms)
        context = await browser.new_context(storage_state=str(storage_path))
        page = await context.new_page()
        captured: Optional[ResponseSnapshot] = None

        async def capture_response(response) -> None:
            nonlocal captured
            selectors = config.selectors.api
            if not selectors.checkin_path_contains:
                return
            if selectors.checkin_path_contains in response.url:
                body_text: Optional[str]
                try:
                    body_text = await response.text()
                except Exception:  # pragma: no cover - defensive
                    body_text = None
                captured = ResponseSnapshot(url=response.url, status=response.status, body=body_text)

        page.on("response", capture_response)

        try:
            await page.goto(config.playwright.base_url, wait_until="domcontentloaded")
            if "github.com/login" in page.url:
                raise AuthInvalidError("Redirected to GitHub login page")

            dom_selectors = config.selectors.dom
            if dom_selectors.login_with_github:
                locator = page.locator(dom_selectors.login_with_github)
                try:
                    count = await locator.count()
                except PlaywrightError:
                    count = 0
                if count:
                    raise AuthInvalidError("Login button detected; authorization likely expired")

            if dom_selectors.checkin_button:
                button = page.locator(dom_selectors.checkin_button)
                await button.wait_for(state="visible", timeout=config.playwright.launch_timeout_ms)
                await button.click()
            else:
                print("checkin_button selector missing; waiting briefly for automatic flow...")
                await page.wait_for_timeout(1500)

            await page.wait_for_timeout(2000)

            page_content = await page.content()
            if captured:
                status, message = _parse_response(captured, config)
                if status == "success":
                    outcome = SigninOutcome(
                        status="success",
                        message="Check-in succeeded",
                        response=captured,
                        http_status=captured.status,
                    )
                elif status == "already":
                    outcome = SigninOutcome(
                        status="already",
                        message="Already checked in today",
                        response=captured,
                        http_status=captured.status,
                    )
                else:
                    outcome = SigninOutcome(
                        status="failure",
                        message="API response indicates failure",
                        err_category="http",
                        err_summary=message,
                        http_status=captured.status,
                        response=captured,
                    )
            else:
                if match_any_keyword(page_content, dom_selectors.success_keywords):
                    outcome = SigninOutcome(status="success", message="Check-in success (DOM)")
                elif match_any_keyword(page_content, dom_selectors.already_keywords):
                    outcome = SigninOutcome(status="already", message="Already checked in (DOM)")
                elif match_any_keyword(page_content, dom_selectors.failure_keywords):
                    outcome = SigninOutcome(
                        status="failure",
                        message="Detected failure message on page",
                        err_category="dom_failure",
                        err_summary="failure keyword detected",
                    )
                else:
                    outcome = SigninOutcome(
                        status="failure",
                        message="Unable to determine outcome",
                        err_category="unknown",
                        err_summary="No API response and no DOM keywords",
                    )

        finally:
            await browser.close()

    duration_ms = int((time.perf_counter() - start) * 1000)
    history.append(
        HistoryEntry(
            timestamp=timestamp,
            slot=slot,
            stage="signin",
            result=outcome.status,
            err_category=outcome.err_category,
            err_summary=outcome.err_summary or outcome.message,
            http_status=outcome.http_status,
            duration_ms=duration_ms,
            extra={"response": outcome.response.to_json() if outcome.response else None},
        )
    )
    return outcome


def signin(config: AppConfig, slot: str, history: HistoryLogger) -> SigninOutcome:
    """Public entry point for sign-in."""

    try:
        return asyncio.run(_signin_async(config, slot, history))
    except ModuleNotFoundError:  # Playwright missing
        timestamp = now_local(config.schedule.timezone).isoformat()
        message = "playwright is not installed. Run 'pip install -r requirements.txt' and 'playwright install chromium'."
        history.append(
            HistoryEntry(
                timestamp=timestamp,
                slot=slot,
                stage="signin",
                result="failure",
                err_category="dependency_missing",
                err_summary=message,
            )
        )
        return SigninOutcome(status="failure", message=message, err_category="dependency_missing", err_summary=message)
    except AuthInvalidError as exc:
        timestamp = now_local(config.schedule.timezone).isoformat()
        history.append(
            HistoryEntry(
                timestamp=timestamp,
                slot=slot,
                stage="signin",
                result="failure",
                err_category="auth_invalid",
                err_summary=str(exc),
            )
        )
        return SigninOutcome(status="failure", message=str(exc), err_category="auth_invalid", err_summary=str(exc))
    except Exception as exc:
        timestamp = now_local(config.schedule.timezone).isoformat()
        history.append(
            HistoryEntry(
                timestamp=timestamp,
                slot=slot,
                stage="signin",
                result="failure",
                err_category="unknown",
                err_summary=str(exc),
            )
        )
        return SigninOutcome(status="failure", message=str(exc), err_category="unknown", err_summary=str(exc))
