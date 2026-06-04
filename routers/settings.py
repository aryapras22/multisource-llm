from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Union
from services.settings_manager import (
    SETTING_KEYS,
    get_setting,
    set_setting,
    reset_setting,
    get_all_settings,
)


router = APIRouter(prefix="/settings", tags=["Settings Management"])


class SettingOut(BaseModel):
    key: str
    value: Union[str, float, int]


class SettingUpdateRequest(BaseModel):
    value: Union[str, float, int]


class AllSettingsOut(BaseModel):
    settings: dict[str, Union[str, float, int]]


# ── List all settings ──────────────────────────────────────────────────────

@router.get("/", response_model=AllSettingsOut)
async def list_settings():
    """Return all current model and hyperparameter settings."""
    return AllSettingsOut(settings=get_all_settings())


# ── Get one setting ────────────────────────────────────────────────────────

@router.get("/{key}", response_model=SettingOut)
async def get_single_setting(key: str):
    """
    Return the current value for a setting key.

    Valid keys: queries_model, userstory_model, insight_model,
    temperature, max_tokens, top_p
    """
    if key not in SETTING_KEYS:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown setting key '{key}'. Valid keys: {', '.join(SETTING_KEYS)}",
        )
    return SettingOut(key=key, value=get_setting(key))


# ── Update a setting ──────────────────────────────────────────────────────

@router.put("/{key}", response_model=SettingOut)
async def update_setting(key: str, body: SettingUpdateRequest):
    """
    Update a model or hyperparameter setting at runtime.

    Examples:
      PUT /settings/queries_model  {"value": "llama3.2:latest"}
      PUT /settings/temperature    {"value": 0.7}
      PUT /settings/max_tokens     {"value": 4096}
    """
    if key not in SETTING_KEYS:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown setting key '{key}'. Valid keys: {', '.join(SETTING_KEYS)}",
        )

    # Type validation
    value = body.value
    if key in ("temperature", "top_p"):
        try:
            value = float(value)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail=f"{key} must be a number")
    elif key == "max_tokens":
        try:
            value = int(value)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="max_tokens must be an integer")
    else:
        # Model keys — must be non-empty string
        value = str(value).strip()
        if not value:
            raise HTTPException(status_code=400, detail=f"{key} cannot be empty")

    set_setting(key, value)
    return SettingOut(key=key, value=get_setting(key))


# ── Reset a setting to default ────────────────────────────────────────────

@router.delete("/{key}", response_model=SettingOut)
async def reset_single_setting(key: str):
    """Reset a setting back to its .env default value."""
    if key not in SETTING_KEYS:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown setting key '{key}'. Valid keys: {', '.join(SETTING_KEYS)}",
        )
    default_value = reset_setting(key)
    return SettingOut(key=key, value=default_value)
