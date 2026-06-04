# llm-fastapi — AI Webhook Service

> A **FastAPI** microservice that acts as the AI backbone for `multisource-fastapi`.  
> It exposes three webhook-style endpoints — **Queries Generator**, **AI User Story Generator**, and **Insight Generator** — plus a **direct OpenWebUI/Ollama proxy route** for ad-hoc requests.  
> All LLM calls go to a locally-running **Ollama** instance on port `11434` (no API key required).

---

## 📐 Architecture Overview

```
multisource-fastapi
        │
        │  POST /webhook/queries-generator
        │  POST /webhook/ai-userstory-generator
        │  POST /webhook/insight-generator
        ▼
   llm-fastapi (port 8001)
        │  ◄──── system prompt + hyperparameters (per endpoint)
        │  ◄──── /openwebui/...  (direct proxy for manual requests)
        │
        │  POST /api/chat   (Ollama OpenAI-compatible)
        ▼
   Ollama (localhost:11434)
        │
        ▼
   LLM Model (e.g. gemma3:12b, llama3.2, etc.)
```

`multisource-fastapi` points its three `*_WEBHOOK` env vars to this service, replacing n8n entirely. The `/openwebui/*` proxy lets you also make direct raw requests to the Ollama API through this service.

---

## 🗂️ Project Structure

```
llm-fastapi/
├── main.py                  # FastAPI app, CORS, API-key middleware, router mounts
├── config.py                # Pydantic settings (reads from .env)
├── routers/
│   ├── __init__.py
│   ├── queries.py           # POST /webhook/queries-generator
│   ├── userstory.py         # POST /webhook/ai-userstory-generator
│   ├── insight.py           # POST /webhook/insight-generator
│   └── openwebui_proxy.py   # ANY /openwebui/{path} — transparent proxy to Ollama
├── services/
│   ├── __init__.py
│   └── ollama_client.py     # Shared async client for Ollama API
├── prompts/
│   ├── queries_prompt.py    # System prompt for query generation
│   ├── userstory_prompt.py  # System prompt for AI user story extraction
│   └── insight_prompt.py    # System prompt for insight generation
├── schemas.py               # Pydantic request / response models
├── requirements.txt
├── .env.example
├── .gitignore
└── Dockerfile               # (optional) for containerised deployment
```

---

## 🔌 Endpoints

### 1. `POST /webhook/queries-generator`

Generates a list of search queries based on a case study description.

**Called by:** `multisource-fastapi` → `services/get_queries.py`

#### Request Body
```json
{
  "message": "<case study text>"
}
```

#### Response Body
```json
{
  "output": {
    "queries": ["query 1", "query 2", "query 3"]
  }
}
```

---

### 2. `POST /webhook/ai-userstory-generator`

Extracts structured AI user stories from raw content (review / news / tweet / mixed).

**Called by:** `multisource-fastapi` → `services/ai_requirement_service.py`

#### Request Body
```json
{
  "message": "<content_type>\n<raw content text>"
}
```

#### Response Body
```json
{
  "output": {
    "userStories": [
      {
        "who": "...",
        "what": "...",
        "why": "...",
        "as_a_i_want_so_that": "...",
        "evidence": "...",
        "sentiment": "positive | neutral | negative",
        "confidence": 0.85,
        "field_insight": {
          "nfr": ["Performance", "Reliability"],
          "business_impact": "...",
          "pain_point_jtbd": "..."
        }
      }
    ]
  }
}
```

---

### 3. `POST /webhook/insight-generator`

Generates a strategic insight object for a single user story.

**Called by:** `multisource-fastapi` → `services/generative_service.py`

#### Request Body
```json
{
  "story": {
    "who": "...",
    "what": "...",
    "why": "...",
    "full_sentence": "..."
  }
}
```

#### Response Body
```json
{
  "output": {
    "nfr": ["Usability", "Performance"],
    "business_impact": "...",
    "pain_point_jtbd": "...",
    "fit_score": {
      "score": 0.87,
      "explanation": "..."
    }
  }
}
```

---

### 4. `ANY /openwebui/{path:path}` — Direct Ollama Proxy

A **transparent reverse proxy** that forwards any request (GET, POST, etc.) directly to the local Ollama instance. Useful for:
- Testing models manually
- Listing available models (`GET /openwebui/api/tags`)
- Sending raw chat completions without the webhook wrapper
- Integration with any OpenAI-compatible client pointed at `llm-fastapi`

#### How it works

```
Client  →  POST http://localhost:8001/openwebui/api/chat
                       ↓  (strip /openwebui prefix, forward body/headers as-is)
Ollama  ←  POST http://localhost:11434/api/chat
```

The proxy:
- Strips the `/openwebui` prefix and forwards the remainder of the path to `http://localhost:11434`
- Passes through the **request body**, **query parameters**, and **Content-Type** header unchanged
- Streams the Ollama response back to the caller

#### Example — list available models
```bash
curl http://localhost:8001/openwebui/api/tags
```

#### Example — raw chat completion
```bash
curl -X POST http://localhost:8001/openwebui/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemma3:12b",
    "messages": [
      { "role": "user", "content": "Hello!" }
    ],
    "stream": false
  }'
```

#### Example — OpenAI-compatible chat completions
```bash
curl -X POST http://localhost:8001/openwebui/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemma3:12b",
    "messages": [
      { "role": "system", "content": "You are a helpful assistant." },
      { "role": "user",   "content": "Summarise this app review." }
    ],
    "temperature": 0.3,
    "stream": false
  }'
```

#### Implementation — `routers/openwebui_proxy.py`

```python
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
import httpx

OLLAMA_BASE_URL = "http://localhost:11434"

router = APIRouter(prefix="/openwebui", tags=["OpenWebUI Proxy"])


@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_to_ollama(path: str, request: Request):
    """
    Transparent reverse proxy: forwards /openwebui/{path} → Ollama at localhost:11434/{path}
    """
    target_url = f"{OLLAMA_BASE_URL}/{path}"
    body = await request.body()

    async def stream_response():
        async with httpx.AsyncClient(timeout=300.0) as client:
            async with client.stream(
                method=request.method,
                url=target_url,
                content=body,
                params=dict(request.query_params),
                headers={"Content-Type": request.headers.get("content-type", "application/json")},
            ) as resp:
                async for chunk in resp.aiter_bytes():
                    yield chunk

    # Peek at content type to set response media type
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            head = await client.head(target_url)
            media_type = head.headers.get("content-type", "application/json")
        except Exception:
            media_type = "application/json"

    return StreamingResponse(stream_response(), media_type=media_type)
```

> **Note:** The proxy route is excluded from API-key middleware validation so you can call it freely from tools like Postman, curl, or any OpenAI-compatible SDK.

---

## ⚙️ Configuration — `.env`

```env
# ── Ollama (local, no API key needed) ─────────────────────────────────────
OLLAMA_BASE_URL=http://localhost:11434

# ── Model selection (Ollama model tag) ────────────────────────────────────
QUERIES_MODEL=gemma3:12b
USERSTORY_MODEL=gemma3:12b
INSIGHT_MODEL=gemma3:12b

# ── Generation hyperparameters ─────────────────────────────────────────────
TEMPERATURE=0.3
MAX_TOKENS=2048
TOP_P=0.9

# ── Service security ───────────────────────────────────────────────────────
# Used by multisource-fastapi to authenticate calls to this service
SERVICE_API_KEY=change-me-secret

# ── CORS ───────────────────────────────────────────────────────────────────
ALLOWED_ORIGIN=http://localhost:8000
```

Update `multisource-fastapi/.env` to point the webhooks here:
```env
QUERIES_GENERATOR_WEBHOOK=http://localhost:8001/webhook/queries-generator?key=change-me-secret
AI_USERSTORY_GENERATOR_WEBHOOK=http://localhost:8001/webhook/ai-userstory-generator?key=change-me-secret
INSIGHT_GENERATOR_WEBHOOK=http://localhost:8001/webhook/insight-generator?key=change-me-secret
```

---

## 🧠 Ollama Integration

All three webhook endpoints share the same async HTTP client in `services/ollama_client.py`, which uses Ollama's **OpenAI-compatible** endpoint (no API key required for local instances):

```
POST http://localhost:11434/v1/chat/completions
Content-Type: application/json

{
  "model": "gemma3:12b",
  "messages": [
    { "role": "system", "content": "<system prompt>" },
    { "role": "user",   "content": "<user payload>" }
  ],
  "temperature": 0.3,
  "max_tokens": 2048,
  "top_p": 0.9,
  "stream": false
}
```

The response is parsed from `choices[0].message.content`, expected to be a **raw JSON string** (the system prompt explicitly instructs the model to output only JSON, no markdown fences).

### `services/ollama_client.py` skeleton

```python
import httpx
from config import settings
from fastapi import HTTPException
import json

async def chat_completion(
    system_prompt: str,
    user_message: str,
    model: str,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> dict:
    url = f"{settings.ollama_base_url}/v1/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": temperature or settings.temperature,
        "max_tokens": max_tokens or settings.max_tokens,
        "top_p": settings.top_p,
        "stream": False,
    }
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.post(url, json=payload)
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        # Strip potential markdown fences
        content = content.strip().removeprefix("```json").removesuffix("```").strip()
        return json.loads(content)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail=f"Cannot reach Ollama: {exc}")
    except (KeyError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=500, detail=f"Unexpected LLM response format: {exc}")
```

---

## 🔐 Security

Incoming requests to the **webhook endpoints** are validated via a query-parameter API key (`?key=...`), matching the pattern in `multisource-fastapi`.

The `/openwebui/*` **proxy routes are excluded** from key validation — they are intended for local use only (the service itself only listens on `localhost:8001`).

Middleware skip list: `GET /`, `/docs`, `/redoc`, `/openapi.json`, `/openwebui/**`

---

## 🚀 Running Locally

```bash
# 1. Make sure Ollama is running
ollama serve   # or it's already running as a background service on :11434

# 2. Pull the model you want to use
ollama pull gemma3:12b

# 3. Start llm-fastapi
cd llm-fastapi
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env if needed (defaults already point to localhost:11434)

uvicorn main:app --reload --port 8001
```

- Swagger UI → `http://localhost:8001/docs`
- Proxy test → `curl http://localhost:8001/openwebui/api/tags`

---

## 📦 Dependencies (`requirements.txt`)

```txt
fastapi
uvicorn[standard]
httpx
pydantic
pydantic-settings
python-dotenv
```

---

## 🐳 Docker (optional)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8001
# host.docker.internal resolves to the Docker host — needed to reach Ollama on the host machine
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
```

> **Important:** If running inside Docker, change `OLLAMA_BASE_URL` to `http://host.docker.internal:11434` so the container can reach Ollama on the host machine.

```yaml
# docker-compose.yml
services:
  llm-fastapi:
    build: ./llm-fastapi
    env_file: ./llm-fastapi/.env
    ports:
      - "8001:8001"
    extra_hosts:
      - "host.docker.internal:host-gateway"
    restart: unless-stopped
```

---

## 🛠️ Implementation Checklist

- [ ] Scaffold project structure (`main.py`, `config.py`, `routers/`, `services/`, `prompts/`, `schemas.py`)
- [ ] Implement `services/ollama_client.py` — shared async chat completion caller (no API key)
- [ ] Write system prompts in `prompts/` for each of the three tasks (instruct model to return raw JSON only)
- [ ] Implement `routers/queries.py` — parse `message`, call LLM, return `{"output": {"queries": [...]}}`
- [ ] Implement `routers/userstory.py` — parse `message`, call LLM, validate & return user story list
- [ ] Implement `routers/insight.py` — parse `story`, call LLM, validate & return insight object
- [ ] Implement `routers/openwebui_proxy.py` — transparent proxy to `localhost:11434`
- [ ] Add API-key middleware to `main.py`, exclude `/openwebui/*` routes
- [ ] Create `.env.example`
- [ ] Update `multisource-fastapi/.env` webhook URLs
- [ ] Test proxy: `curl http://localhost:8001/openwebui/api/tags`
- [ ] Test all three webhook endpoints end-to-end with `multisource-fastapi`

---

## 📝 Notes

- Response shapes are kept **backward-compatible** with existing n8n responses consumed by `multisource-fastapi` (`output.queries`, `output.userStories`, `output`-wrapped insight).
- System prompts **must** instruct the model to return only raw JSON — no explanation text, no markdown fences. The client strips accidental fences as a safety net.
- Since Ollama runs locally with no auth, `OLLAMA_BASE_URL` defaults to `http://localhost:11434` and no `Authorization` header is sent.
- Model tags can be overridden per-endpoint via env vars (`QUERIES_MODEL`, `USERSTORY_MODEL`, `INSIGHT_MODEL`) if different tasks benefit from different models or temperatures.
