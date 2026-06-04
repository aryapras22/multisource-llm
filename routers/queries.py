from fastapi import APIRouter
from schemas import MessageRequest, QueriesResponse, QueriesOutput
from services.ollama_client import chat_completion
from services.prompt_manager import get_prompt
from config import settings

router = APIRouter(prefix="/webhook", tags=["Queries Generator"])


@router.post("/queries-generator", response_model=QueriesResponse)
async def generate_queries(payload: MessageRequest):
    """
    Generate search queries from a case study description.

    Called by multisource-fastapi → services/get_queries.py
    Expects: {"message": "<case study text>"}
    Returns: {"output": {"queries": [...]}}
    """
    result = await chat_completion(
        system_prompt=get_prompt("queries"),
        user_message=payload.message,
        model=settings.queries_model,
    )

    # Ensure result has the expected shape
    queries = result.get("queries", [])
    if not isinstance(queries, list):
        queries = []

    # Ensure all items are strings
    queries = [str(q) for q in queries if q]

    return QueriesResponse(output=QueriesOutput(queries=queries))
