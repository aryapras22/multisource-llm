from fastapi import APIRouter, HTTPException
from schemas import (
    MessageRequest,
    UserStoriesResponse,
    UserStoriesOutput,
    UserStoryItem,
    FieldInsight,
)
from services.ollama_client import chat_completion
from services.prompt_manager import get_prompt
from services.settings_manager import get_setting

router = APIRouter(prefix="/webhook", tags=["AI User Story Generator"])

# Required keys for each user story item
_REQUIRED_KEYS = {
    "who",
    "what",
    "as_a_i_want_so_that",
    "evidence",
    "sentiment",
    "confidence",
}


@router.post("/ai-userstory-generator", response_model=UserStoriesResponse)
async def generate_user_stories(payload: MessageRequest):
    """
    Extract structured user stories from raw content.

    Called by multisource-fastapi → services/ai_requirement_service.py
    Expects: {"message": "<content_type>\\n<raw content text>"}
    Returns: {"output": {"userStories": [...]}}
    """
    result = await chat_completion(
        system_prompt=get_prompt("userstory"),
        user_message=payload.message,
        model=get_setting("userstory_model"),
    )

    # Extract the user stories list
    raw_stories = result.get("userStories", [])
    if not isinstance(raw_stories, list):
        raise HTTPException(
            status_code=500,
            detail=f"LLM returned userStories as {type(raw_stories).__name__}, expected list",
        )

    # Validate and clean each story
    cleaned: list[UserStoryItem] = []
    for item in raw_stories:
        if not isinstance(item, dict):
            continue

        # Skip items missing required keys
        missing = _REQUIRED_KEYS - item.keys()
        if missing:
            continue

        # Type coercions / safety
        item["who"] = str(item.get("who", ""))
        item["what"] = str(item.get("what", ""))
        item["why"] = str(item["why"]) if item.get("why") else None
        item["as_a_i_want_so_that"] = str(item.get("as_a_i_want_so_that", ""))
        item["evidence"] = str(item.get("evidence", ""))
        item["sentiment"] = str(item.get("sentiment", "neutral"))

        try:
            item["confidence"] = float(item["confidence"])
        except (ValueError, TypeError):
            item["confidence"] = 0.0

        # Validate field_insight if present
        fi = item.get("field_insight")
        if isinstance(fi, dict):
            try:
                item["field_insight"] = FieldInsight(**fi)
            except Exception:
                item["field_insight"] = None
        else:
            item["field_insight"] = None

        try:
            cleaned.append(UserStoryItem(**item))
        except Exception:
            continue

    return UserStoriesResponse(
        output=UserStoriesOutput(userStories=cleaned)
    )
