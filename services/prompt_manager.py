"""
In-memory prompt manager with runtime GET / PUT support.

Prompts are initialised from the defaults in prompts/*.py and can be
overridden at runtime via the /prompts API. Changes are kept in memory
(they reset on restart). For persistence, the updated prompts are
also written to a local JSON file and reloaded on startup.
"""

import json
import os
from pathlib import Path
from prompts.queries_prompt import QUERIES_SYSTEM_PROMPT
from prompts.userstory_prompt import USERSTORY_SYSTEM_PROMPT
from prompts.insight_prompt import INSIGHT_SYSTEM_PROMPT

_PERSIST_FILE = Path(__file__).parent / "prompts" / "_overrides.json"

# Valid prompt keys
PROMPT_KEYS = ("queries", "userstory", "insight")

# In-memory store — initialised from code defaults
_store: dict[str, str] = {
    "queries": QUERIES_SYSTEM_PROMPT,
    "userstory": USERSTORY_SYSTEM_PROMPT,
    "insight": INSIGHT_SYSTEM_PROMPT,
}

# On startup, load any previously-persisted overrides
if _PERSIST_FILE.exists():
    try:
        _overrides = json.loads(_PERSIST_FILE.read_text(encoding="utf-8"))
        for key in PROMPT_KEYS:
            if key in _overrides and isinstance(_overrides[key], str):
                _store[key] = _overrides[key]
    except Exception:
        pass  # Ignore corrupt file; fall back to code defaults


def get_prompt(key: str) -> str:
    """Return the current system prompt for the given key."""
    return _store[key]


def set_prompt(key: str, value: str) -> None:
    """Update the system prompt at runtime and persist to disk."""
    _store[key] = value
    _persist()


def reset_prompt(key: str) -> str:
    """Reset a prompt back to its code default and return the default."""
    defaults = {
        "queries": QUERIES_SYSTEM_PROMPT,
        "userstory": USERSTORY_SYSTEM_PROMPT,
        "insight": INSIGHT_SYSTEM_PROMPT,
    }
    _store[key] = defaults[key]
    _persist()
    return _store[key]


def get_all_prompts() -> dict[str, str]:
    """Return all current prompts."""
    return dict(_store)


def _persist() -> None:
    """Write current overrides to a JSON file so they survive restarts."""
    try:
        _PERSIST_FILE.write_text(
            json.dumps(_store, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass  # Non-critical — prompts still work in memory
