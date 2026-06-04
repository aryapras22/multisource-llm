"""
In-memory settings manager for models and hyperparameters with runtime API support.

Settings are initialised from config.py (.env) and can be overridden at runtime
via the /settings API. Changes are persisted to a local JSON file so they
survive restarts.
"""

import json
from pathlib import Path
from config import settings as _env_settings

_PERSIST_FILE = Path(__file__).parent.parent / "prompts" / "_settings_overrides.json"

# Valid setting keys
SETTING_KEYS = (
    "queries_model",
    "userstory_model",
    "insight_model",
    "temperature",
    "max_tokens",
    "top_p",
)

# In-memory store — initialised from .env defaults
_store: dict[str, str | float | int] = {
    "queries_model": _env_settings.queries_model,
    "userstory_model": _env_settings.userstory_model,
    "insight_model": _env_settings.insight_model,
    "temperature": _env_settings.temperature,
    "max_tokens": _env_settings.max_tokens,
    "top_p": _env_settings.top_p,
}

# Defaults snapshot for reset
_DEFAULTS: dict[str, str | float | int] = dict(_store)

# On startup, load any previously-persisted overrides
if _PERSIST_FILE.exists():
    try:
        _overrides = json.loads(_PERSIST_FILE.read_text(encoding="utf-8"))
        for key in SETTING_KEYS:
            if key in _overrides:
                _store[key] = _overrides[key]
    except Exception:
        pass


def get_setting(key: str) -> str | float | int:
    """Return the current value for the given setting key."""
    return _store[key]


def set_setting(key: str, value: str | float | int) -> None:
    """Update a setting at runtime and persist to disk."""
    _store[key] = value
    _persist()


def reset_setting(key: str) -> str | float | int:
    """Reset a setting back to its .env default and return the default."""
    _store[key] = _DEFAULTS[key]
    _persist()
    return _store[key]


def get_all_settings() -> dict[str, str | float | int]:
    """Return all current settings."""
    return dict(_store)


def _persist() -> None:
    """Write current overrides to a JSON file so they survive restarts."""
    try:
        _PERSIST_FILE.write_text(
            json.dumps(_store, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass
