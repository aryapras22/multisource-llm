from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from config import settings
from routers.queries import router as queries_router
from routers.userstory import router as userstory_router
from routers.insight import router as insight_router
from routers.openwebui_proxy import router as openwebui_router
from routers.prompts import router as prompts_router
from routers.settings import router as settings_router
from services.settings_manager import get_all_settings

app = FastAPI(
    title="llm-fastapi",
    description="AI Webhook Service — Queries, User Stories, and Insight generation via Ollama",
    version="1.0.0",
)

# ── CORS ───────────────────────────────────────────────────────────────────
origins = [settings.allowed_origin, "http://localhost:8000", "http://localhost:5173"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Paths excluded from API-key validation ─────────────────────────────────
_SKIP_AUTH_PATHS = {"/", "/docs", "/redoc", "/openapi.json"}
_SKIP_AUTH_PREFIXES = ("/openwebui/",)


@app.middleware("http")
async def validate_api_key(request: Request, call_next):
    """
    Validate the API key from query parameter `?key=...`.
    Skips validation for:
      - CORS preflight (OPTIONS)
      - docs endpoints
      - /openwebui/* proxy routes (local use only)
    """
    # Skip for OPTIONS and safe paths
    if request.method == "OPTIONS":
        return await call_next(request)

    path = request.url.path
    if path in _SKIP_AUTH_PATHS:
        return await call_next(request)

    # Skip for proxy routes
    for prefix in _SKIP_AUTH_PREFIXES:
        if path.startswith(prefix):
            return await call_next(request)

    # Validate key
    api_key = request.query_params.get("key")

    if not settings.service_api_key:
        return JSONResponse(
            status_code=500,
            content={"detail": "SERVICE_API_KEY not configured on server"},
        )

    if api_key != settings.service_api_key:
        return JSONResponse(
            status_code=403,
            content={"detail": "Invalid or missing API key"},
        )

    response = await call_next(request)
    return response


# ── Root endpoint ──────────────────────────────────────────────────────────
@app.get("/")
async def root():
    current = get_all_settings()
    return {
        "service": "llm-fastapi",
        "status": "running",
        "ollama_url": settings.ollama_base_url,
        "models": {
            "queries": current["queries_model"],
            "userstory": current["userstory_model"],
            "insight": current["insight_model"],
        },
        "hyperparameters": {
            "temperature": current["temperature"],
            "max_tokens": current["max_tokens"],
            "top_p": current["top_p"],
        },
    }


# ── Mount routers ─────────────────────────────────────────────────────────
app.include_router(queries_router)
app.include_router(userstory_router)
app.include_router(insight_router)
app.include_router(openwebui_router)
app.include_router(prompts_router)
app.include_router(settings_router)
