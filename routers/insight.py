import json
from fastapi import APIRouter, HTTPException
from schemas import InsightRequest, InsightResponse, InsightOutput, FitScore
from services.ollama_client import chat_completion
from services.prompt_manager import get_prompt
from services.settings_manager import get_setting

router = APIRouter(prefix="/webhook", tags=["Insight Generator"])


@router.post("/insight-generator", response_model=InsightResponse)
async def generate_insight(payload: InsightRequest):
    """
    Generate a strategic insight for a single user story.

    Called by multisource-fastapi → services/generative_service.py
    Expects: {"story": {"who": ..., "what": ..., "why": ..., "full_sentence": ...}}
    Returns: {"output": {"nfr": [...], "business_impact": ..., "pain_point_jtbd": ..., "fit_score": {...}}}
    """
    # Build the user message from the story fields
    story = payload.story
    user_message = json.dumps(
        {
            "who": story.who,
            "what": story.what,
            "why": story.why,
            "full_sentence": story.full_sentence,
        },
        ensure_ascii=False,
    )

    result = await chat_completion(
        system_prompt=get_prompt("insight"),
        user_message=user_message,
        model=get_setting("insight_model"),
    )

    # Validate the result structure
    try:
        nfr = result.get("nfr", [])
        if not isinstance(nfr, list):
            nfr = []
        nfr = [str(n) for n in nfr]

        business_impact = str(result.get("business_impact", ""))
        pain_point_jtbd = str(result.get("pain_point_jtbd", ""))

        fit_score_raw = result.get("fit_score", {})
        if not isinstance(fit_score_raw, dict):
            fit_score_raw = {"score": 0.0, "explanation": "Unable to parse fit score"}

        fit_score = FitScore(
            score=float(fit_score_raw.get("score", 0.0)),
            explanation=str(fit_score_raw.get("explanation", "")),
        )

        insight = InsightOutput(
            nfr=nfr,
            business_impact=business_impact,
            pain_point_jtbd=pain_point_jtbd,
            fit_score=fit_score,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Invalid insight format from LLM: {e}",
        )

    return InsightResponse(output=insight)
