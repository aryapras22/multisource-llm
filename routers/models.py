from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import httpx
import json
from config import settings

router = APIRouter(prefix="/models", tags=["Models Management"])


class PullModelRequest(BaseModel):
    name: str


@router.post("/pull")
async def pull_model(request: PullModelRequest):
    """
    Pull/download a new model from the Ollama library.
    Streams back JSON responses from Ollama showing the download progress.
    """
    url = f"{settings.ollama_base_url}/api/pull"
    payload = {"name": request.name, "stream": True}

    async def _stream_pull():
        async with httpx.AsyncClient(timeout=3600.0) as client:
            try:
                async with client.stream("POST", url, json=payload) as response:
                    response.raise_for_status()
                    async for chunk in response.aiter_text():
                        yield chunk
            except httpx.HTTPError as exc:
                yield json.dumps({"error": f"Failed to pull model: {str(exc)}"}) + "\n"

    return StreamingResponse(_stream_pull(), media_type="application/x-ndjson")


@router.get("/")
async def list_models():
    """
    List models currently available in the connected Ollama instance.
    """
    url = f"{settings.ollama_base_url}/api/tags"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to list models: {e}")
