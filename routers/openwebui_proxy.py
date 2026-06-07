from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse
import httpx
from config import settings

router = APIRouter(prefix="/openwebui", tags=["OpenWebUI Proxy"])


@router.get("/models")
async def check_available_models():
    """
    Check list of models available via Ollama (proxied from openwebui)
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/tags")
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
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

    # Forward headers safely (filtering out host to avoid proxying issues)
    # Only forward Content-Type if there's actually a body (solves DELETE/GET body rejection issues in HTTP clients).
    headers = {}
    if body:
        headers["Content-Type"] = request.headers.get(
            "content-type", "application/json"
        )

    async def _stream():
        async with httpx.AsyncClient(timeout=300.0) as client:
            # Build request objects explicitly to gracefully handle complex body payloads on any method (like DELETE)
            req = client.build_request(
                method=request.method,
                url=target_url,
                content=body if body else None,
                params=query_params if query_params else None,
                headers=headers,
            )
            async with client.send(req, stream=True) as resp:
                async for chunk in resp.aiter_bytes():
                    yield chunk

    return StreamingResponse(
        _stream(),
        # By default we can fallback to json, but ideally we match what was sent
        media_type=request.headers.get("accept", "application/json"),
    )
