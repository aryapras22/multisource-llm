from pydantic import BaseModel, Field
from typing import Optional


# ── Shared ─────────────────────────────────────────────────────────────────


class MessageRequest(BaseModel):
    """Generic request with a `message` field — used by queries & userstory endpoints."""
    message: str


# ── Queries Generator ──────────────────────────────────────────────────────


class QueriesOutput(BaseModel):
    queries: list[str]


class QueriesResponse(BaseModel):
    output: QueriesOutput


# ── AI User Story Generator ───────────────────────────────────────────────


class FieldInsight(BaseModel):
    nfr: list[str]
    business_impact: str
    pain_point_jtbd: str


class UserStoryItem(BaseModel):
    who: str
    what: str
    why: Optional[str] = None
    as_a_i_want_so_that: str
    evidence: str
    sentiment: str
    confidence: float
    field_insight: Optional[FieldInsight] = None


class UserStoriesOutput(BaseModel):
    userStories: list[UserStoryItem]


class UserStoriesResponse(BaseModel):
    output: UserStoriesOutput


# ── Insight Generator ─────────────────────────────────────────────────────


class StoryInput(BaseModel):
    who: str
    what: str
    why: Optional[str] = None
    full_sentence: Optional[str] = None


class InsightRequest(BaseModel):
    story: StoryInput


class FitScore(BaseModel):
    score: float
    explanation: str


class InsightOutput(BaseModel):
    nfr: list[str]
    business_impact: str
    pain_point_jtbd: str
    fit_score: FitScore


class InsightResponse(BaseModel):
    output: InsightOutput
