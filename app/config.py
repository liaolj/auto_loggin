"""Application configuration loading utilities."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, MutableMapping, Optional
import os
import tomllib


CONFIG_ENV_VAR = "AUTO_LOGGIN_CONFIG"
DEFAULT_CONFIG_FILE = "config.toml"


class ConfigError(RuntimeError):
    """Raised when the configuration file is missing or invalid."""


@dataclass
class PlaywrightConfig:
    """Playwright related configuration."""

    base_url: str
    storage_state_path: Path
    headless: bool = True
    slow_mo_ms: int = 0
    launch_timeout_ms: int = 30000


@dataclass
class ScheduleConfig:
    """Schedule configuration for morning/noon/evening slots."""

    timezone: str
    slots: Mapping[str, str] = field(default_factory=dict)


@dataclass
class HistoryConfig:
    """History persistence configuration."""

    csv_path: Path
    max_rows: int = 2000


@dataclass
class DOMSelectors:
    """Selectors used to interact with DOM elements."""

    login_with_github: Optional[str] = None
    checkin_button: Optional[str] = None
    success_keywords: Iterable[str] = field(default_factory=list)
    already_keywords: Iterable[str] = field(default_factory=list)
    failure_keywords: Iterable[str] = field(default_factory=list)


@dataclass
class APISelectors:
    """Selectors used to parse API responses."""

    checkin_path_contains: Optional[str] = None
    success_keys: Iterable[str] = field(default_factory=list)
    already_keywords: Iterable[str] = field(default_factory=list)


@dataclass
class SelectorConfig:
    """Aggregate selector configuration."""

    dom: DOMSelectors = field(default_factory=DOMSelectors)
    api: APISelectors = field(default_factory=APISelectors)


@dataclass
class AppConfig:
    """Top level application configuration."""

    playwright: PlaywrightConfig
    schedule: ScheduleConfig
    history: HistoryConfig
    selectors: SelectorConfig


def _read_toml(path: Path) -> MutableMapping[str, object]:
    try:
        with path.open("rb") as fh:
            return tomllib.load(fh)
    except FileNotFoundError as exc:  # pragma: no cover - simple IO error path
        raise ConfigError(f"Configuration file not found: {path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Configuration file is invalid TOML: {path}") from exc


def _resolve_path(value: str, *, base_dir: Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = base_dir / path
    return path


def _load_playwright_config(data: Mapping[str, object], *, base_dir: Path) -> PlaywrightConfig:
    try:
        base_url = str(data["base_url"])  # type: ignore[index]
        storage_state = _resolve_path(str(data["storage_state_path"]), base_dir=base_dir)
    except KeyError as exc:
        raise ConfigError("playwright.base_url and playwright.storage_state_path are required") from exc

    return PlaywrightConfig(
        base_url=base_url,
        storage_state_path=storage_state,
        headless=bool(data.get("headless", True)),
        slow_mo_ms=int(data.get("slow_mo_ms", 0)),
        launch_timeout_ms=int(data.get("launch_timeout_ms", 30000)),
    )


def _load_schedule_config(data: Mapping[str, object], *, base_dir: Path) -> ScheduleConfig:
    timezone = str(data.get("timezone", "Asia/Singapore"))
    slots_raw = data.get("slots", {})
    if not isinstance(slots_raw, Mapping):
        raise ConfigError("schedule.slots must be a mapping of slot name to trigger time")
    slots: Dict[str, str] = {str(key): str(value) for key, value in slots_raw.items()}
    return ScheduleConfig(timezone=timezone, slots=slots)


def _load_history_config(data: Mapping[str, object], *, base_dir: Path) -> HistoryConfig:
    csv_path_raw = data.get("csv_path", "data/history.csv")
    csv_path = _resolve_path(str(csv_path_raw), base_dir=base_dir)
    max_rows = int(data.get("max_rows", 2000))
    return HistoryConfig(csv_path=csv_path, max_rows=max_rows)


def _load_selectors_config(data: Mapping[str, object]) -> SelectorConfig:
    dom_raw = data.get("dom", {})
    api_raw = data.get("api", {})
    if not isinstance(dom_raw, Mapping):
        raise ConfigError("selectors.dom must be a mapping")
    if not isinstance(api_raw, Mapping):
        raise ConfigError("selectors.api must be a mapping")

    dom = DOMSelectors(
        login_with_github=str(dom_raw.get("login_with_github")) if dom_raw.get("login_with_github") else None,
        checkin_button=str(dom_raw.get("checkin_button")) if dom_raw.get("checkin_button") else None,
        success_keywords=list(map(str, dom_raw.get("success_keywords", []))),
        already_keywords=list(map(str, dom_raw.get("already_keywords", []))),
        failure_keywords=list(map(str, dom_raw.get("failure_keywords", []))),
    )

    api = APISelectors(
        checkin_path_contains=str(api_raw.get("checkin_path_contains"))
        if api_raw.get("checkin_path_contains")
        else None,
        success_keys=list(map(str, api_raw.get("success_keys", []))),
        already_keywords=list(map(str, api_raw.get("already_keywords", []))),
    )

    return SelectorConfig(dom=dom, api=api)


def load_config(path: Optional[Path] = None) -> AppConfig:
    """Load application configuration from TOML.

    Args:
        path: Optional explicit configuration path.

    Returns:
        Parsed :class:`AppConfig` instance.
    """

    config_path = path
    if config_path is None:
        env_path = os.environ.get(CONFIG_ENV_VAR)
        if env_path:
            config_path = Path(env_path)
        else:
            config_path = Path(DEFAULT_CONFIG_FILE)

    data = _read_toml(config_path)
    base_dir = config_path.parent

    playwright_raw = data.get("playwright")
    schedule_raw = data.get("schedule")
    history_raw = data.get("history")
    selectors_raw = data.get("selectors")

    if not isinstance(playwright_raw, Mapping):
        raise ConfigError("[playwright] section is required in the configuration")
    if not isinstance(schedule_raw, Mapping):
        raise ConfigError("[schedule] section is required in the configuration")
    if not isinstance(history_raw, Mapping):
        raise ConfigError("[history] section is required in the configuration")
    if not isinstance(selectors_raw, Mapping):
        raise ConfigError("[selectors] section is required in the configuration")

    playwright = _load_playwright_config(playwright_raw, base_dir=base_dir)
    schedule = _load_schedule_config(schedule_raw, base_dir=base_dir)
    history = _load_history_config(history_raw, base_dir=base_dir)
    selectors = _load_selectors_config(selectors_raw)

    # Ensure parent directories exist for persistence paths.
    history.csv_path.parent.mkdir(parents=True, exist_ok=True)
    playwright.storage_state_path.parent.mkdir(parents=True, exist_ok=True)

    return AppConfig(
        playwright=playwright,
        schedule=schedule,
        history=history,
        selectors=selectors,
    )
