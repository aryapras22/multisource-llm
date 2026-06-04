from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.prompt_manager import (
    PROMPT_KEYS,
    get_prompt,
    set_prompt,
    reset_prompt,
    get_all_prompts,
)


router = APIRouter(prefix="/prompts", tags=["Prompt Management"])


class PromptOut(BaseModel):
    key: str
    prompt: str


class PromptUpdateRequest(BaseModel):
    prompt: str


class AllPromptsOut(BaseModel):
    prompts: dict[str, str]


# ── List all prompts ───────────────────────────────────────────────────────

@router.get("/", response_model=AllPromptsOut)
async def list_prompts():
    """Return all current system prompts."""
    return AllPromptsOut(prompts=get_all_prompts())


# ── Get one prompt ─────────────────────────────────────────────────────────

@router.get("/{key}", response_model=PromptOut)
async def get_single_prompt(key: str):
    """Return the current system prompt for a given key (queries, userstory, insight)."""
    if key not in PROMPT_KEYS:
        raise HTTPException(status_code=404, detail=f"Unknown prompt key '{key}'. Valid keys: {', '.join(PROMPT_KEYS)}")
    return PromptOut(key=key, prompt=get_prompt(key))


# ── Update a prompt ───────────────────────────────────────────────────────

@router.put("/{key}", response_model=PromptOut)
async def update_prompt(key: str, body: PromptUpdateRequest):
    """
    Replace the system prompt for a given key at runtime.
    The change is persisted to disk so it survives restarts.
    """
    if key not in PROMPT_KEYS:
        raise HTTPException(status_code=404, detail=f"Unknown prompt key '{key}'. Valid keys: {', '.join(PROMPT_KEYS)}")
    if not body.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")
    set_prompt(key, body.prompt)
    return PromptOut(key=key, prompt=get_prompt(key))


# ── Reset a prompt to default ─────────────────────────────────────────────

@router.delete("/{key}", response_model=PromptOut)
async def reset_single_prompt(key: str):
    """Reset the system prompt for a given key back to the code default."""
    if key not in PROMPT_KEYS:
        raise HTTPException(status_code=404, detail=f"Unknown prompt key '{key}'. Valid keys: {', '.join(PROMPT_KEYS)}")
    default_prompt = reset_prompt(key)
    return PromptOut(key=key, prompt=default_prompt)
