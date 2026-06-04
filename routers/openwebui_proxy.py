from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
import httpx
from config import settings

router = APIRouter(prefix="/openwebui", tags=["OpenWebUI Proxy"])


@router.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
)
async def proxy_to_ollama(path: str, request: Request):
    """
    Transparent reverse proxy: forwards /openwebui/{path} → Ollama at localhost:11434/{path}

    Supports all HTTP methods. Streams the response back so large outputs
    and SSE-style streaming work correctly.

    Examples:
        GET  /openwebui/api/tags           → list models
        POST /openwebui/api/chat           → Ollama native chat
        POST /openwebui/v1/chat/completions → OpenAI-compatible chat
    """
    target_url = f"{settings.ollama_base_url}/{path}"
    body = await request.body()
    query_params = dict(request.query_params)
    content_type = request.headers.get("content-type", "application/json")

    async def _stream():
        async with httpx.AsyncClient(timeout=300.0) as client:
            async with client.stream(
                method=request.method,
                url=target_url,
                content=body if body else None,
                params=query_params if query_params else None,
                headers={"Content-Type": content_type},
            ) as resp:
                async for chunk in resp.aiter_bytes():
                    yield chunk

    return StreamingResponse(
        _stream(),
        media_type="application/json",
    )
