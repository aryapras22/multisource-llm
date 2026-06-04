import httpx
import json
import re
from config import settings
from services.settings_manager import get_setting
from fastapi import HTTPException


async def chat_completion(
    system_prompt: str,
    user_message: str,
    model: str,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> dict:
    """
    Send a chat completion request to the local Ollama instance
    using the OpenAI-compatible /v1/chat/completions endpoint.

    Returns the parsed JSON from the model's response content.
    """
    url = f"{settings.ollama_base_url}/v1/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": temperature if temperature is not None else get_setting("temperature"),
        "max_tokens": max_tokens if max_tokens is not None else get_setting("max_tokens"),
        "top_p": get_setting("top_p"),
        "stream": False,
    }

    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.post(url, json=payload)
        resp.raise_for_status()
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Cannot reach Ollama at {settings.ollama_base_url}: {exc}",
        )
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Ollama returned HTTP {exc.response.status_code}: {exc.response.text[:500]}",
        )

    try:
        content = resp.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected Ollama response structure: {exc}",
        )

    return _parse_json_content(content)


def _parse_json_content(raw: str) -> dict:
    """
    Parse JSON from model output, handling common LLM quirks:
    - Markdown code fences (```json ... ```)
    - Leading/trailing whitespace
    - Multiple JSON code blocks (pick the first)
    """
    text = raw.strip()

    # Try to extract JSON from markdown fences first
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                f"LLM returned non-JSON content. "
                f"Parse error: {exc}. "
                f"Raw output (first 500 chars): {raw[:500]}"
            ),
        )
