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
        │  ◄──── system prompt + hyperparameters (runtime-configurable via API)
        │  ◄──── /openwebui/...  (direct proxy for manual requests)
        │  ◄──── /prompts/...    (view & edit system prompts at runtime)
        │  ◄──── /settings/...   (view & edit models + hyperparams at runtime)
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
├── main.py                      # FastAPI app, CORS, API-key middleware, router mounts
├── config.py                    # Pydantic settings (reads from .env)
├── schemas.py                   # Pydantic request / response models
├── routers/
│   ├── __init__.py
│   ├── queries.py               # POST /webhook/queries-generator
│   ├── userstory.py             # POST /webhook/ai-userstory-generator
│   ├── insight.py               # POST /webhook/insight-generator
│   ├── openwebui_proxy.py       # ANY  /openwebui/{path} — transparent proxy
│   ├── prompts.py               # GET/PUT/DELETE /prompts/{key} — runtime prompt editing
│   └── settings.py              # GET/PUT/DELETE /settings/{key} — runtime model & hyperparam editing
├── services/
│   ├── __init__.py
│   ├── ollama_client.py         # Shared async client for Ollama API
│   ├── prompt_manager.py        # In-memory prompt store with JSON persistence
│   └── settings_manager.py      # In-memory settings store with JSON persistence
├── prompts/
│   ├── queries_prompt.py        # Default system prompt for query generation
│   ├── userstory_prompt.py      # Default system prompt for AI user story extraction
│   └── insight_prompt.py        # Default system prompt for insight generation
├── requirements.txt
├── .env.example
├── .gitignore
├── .dockerignore
└── Dockerfile
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

```
Client  →  POST http://localhost:8001/openwebui/api/chat
                       ↓  (strip /openwebui prefix, forward body/headers as-is)
Ollama  ←  POST http://localhost:11434/api/chat
```

#### Examples
```bash
# List available models
curl http://localhost:8001/openwebui/api/tags

# Raw Ollama chat
curl -X POST http://localhost:8001/openwebui/api/chat \
  -H "Content-Type: application/json" \
  -d '{"model": "gemma3:12b", "messages": [{"role": "user", "content": "Hello!"}], "stream": false}'

# OpenAI-compatible chat completions
curl -X POST http://localhost:8001/openwebui/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "gemma3:12b", "messages": [{"role": "system", "content": "You are helpful."}, {"role": "user", "content": "Summarise this."}], "temperature": 0.3, "stream": false}'
```

> **Note:** The proxy route is excluded from API-key middleware — call it freely from Postman, curl, or any SDK.

---

### 5. `/prompts` — Runtime Prompt Management

View and edit system prompts at runtime without restarting the service. Changes are persisted to `prompts/_overrides.json`.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/prompts/` | List all current system prompts |
| `GET` | `/prompts/{key}` | Get a single prompt |
| `PUT` | `/prompts/{key}` | Update a prompt at runtime |
| `DELETE` | `/prompts/{key}` | Reset prompt to code default |

**Valid keys:** `queries`, `userstory`, `insight`

#### Examples
```bash
# View all prompts
curl -H "Authorization: Bearer change-me-secret" "http://localhost:8001/prompts/"

# Update the queries prompt
curl -X PUT "http://localhost:8001/prompts/queries" \
  -H "Authorization: Bearer change-me-secret" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "You are a search expert. Generate 5 queries as JSON..."}'

# Reset insight prompt to default
curl -X DELETE "http://localhost:8001/prompts/insight" \
  -H "Authorization: Bearer change-me-secret"
```

---

### 6. `/settings` — Runtime Model & Hyperparameter Management

Change the LLM model and generation parameters at runtime without restarting. Changes are persisted to `prompts/_settings_overrides.json`.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/settings/` | List all current settings |
| `GET` | `/settings/{key}` | Get a single setting |
| `PUT` | `/settings/{key}` | Update a setting at runtime |
| `DELETE` | `/settings/{key}` | Reset setting to `.env` default |

**Valid keys:** `queries_model`, `userstory_model`, `insight_model`, `temperature`, `max_tokens`, `top_p`

#### Examples
```bash
# View all current settings
curl -H "Authorization: Bearer change-me-secret" "http://localhost:8001/settings/"

# Switch the queries model to llama3.2
curl -X PUT "http://localhost:8001/settings/queries_model" \
  -H "Authorization: Bearer change-me-secret" \
  -H "Content-Type: application/json" \
  -d '{"value": "llama3.2:latest"}'

# Change temperature to 0.7
curl -X PUT "http://localhost:8001/settings/temperature" \
  -H "Authorization: Bearer change-me-secret" \
  -H "Content-Type: application/json" \
  -d '{"value": 0.7}'

# Increase max tokens
curl -X PUT "http://localhost:8001/settings/max_tokens" \
  -H "Authorization: Bearer change-me-secret" \
  -H "Content-Type: application/json" \
  -d '{"value": 4096}'

# Reset insight model to .env default
curl -X DELETE "http://localhost:8001/settings/insight_model" \
  -H "Authorization: Bearer change-me-secret"
```

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

Update `multisource-fastapi/.env` to point the webhooks here (without the query parameter):
```env
QUERIES_GENERATOR_WEBHOOK=http://localhost:8001/webhook/queries-generator
AI_USERSTORY_GENERATOR_WEBHOOK=http://localhost:8001/webhook/ai-userstory-generator
INSIGHT_GENERATOR_WEBHOOK=http://localhost:8001/webhook/insight-generator
LLM_API_KEY=change-me-secret
```

---

## 🧠 Ollama Integration

All three webhook endpoints share the same async HTTP client in `services/ollama_client.py`, which uses Ollama's **OpenAI-compatible** endpoint (no API key required for local instances):

```
POST http://localhost:11434/v1/chat/completions
Content-Type: application/json

{
  "model": "<from /settings API or .env>",
  "messages": [
    { "role": "system", "content": "<from /prompts API or code default>" },
    { "role": "user",   "content": "<user payload>" }
  ],
  "temperature": "<from /settings API or .env>",
  "max_tokens": "<from /settings API or .env>",
  "top_p": "<from /settings API or .env>",
  "stream": false
}
```

The response is parsed from `choices[0].message.content`, expected to be a **raw JSON string**. The client auto-strips markdown fences as a safety net.

---

## 🔐 Security

Incoming requests to the **webhook, prompts, and settings endpoints** are validated via the `Authorization` header (`Bearer <key>`) or the `X-API-Key` header, matching the configuration in `multisource-fastapi`.

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
conda activate llm-fastapi   # or: python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env if needed (defaults already point to localhost:11434)

uvicorn main:app --reload --port 8001
```

- Swagger UI → `http://localhost:8001/docs`
- Proxy test → `curl http://localhost:8001/openwebui/api/tags`
- Settings → `curl -H "Authorization: Bearer change-me-secret" http://localhost:8001/settings/`
- Prompts → `curl -H "Authorization: Bearer change-me-secret" http://localhost:8001/prompts/`

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

## 📝 Notes

- Response shapes are kept **backward-compatible** with existing n8n responses consumed by `multisource-fastapi` (`output.queries`, `output.userStories`, `output`-wrapped insight).
- System prompts **must** instruct the model to return only raw JSON — no explanation text, no markdown fences. The client strips accidental fences as a safety net.
- Since Ollama runs locally with no auth, `OLLAMA_BASE_URL` defaults to `http://localhost:11434` and no `Authorization` header is sent.
- Model tags and hyperparameters can be overridden **at runtime** via the `/settings` API, or **at startup** via `.env` vars (`QUERIES_MODEL`, `USERSTORY_MODEL`, `INSIGHT_MODEL`, `TEMPERATURE`, `MAX_TOKENS`, `TOP_P`).
- System prompts can be overridden **at runtime** via the `/prompts` API. Changes persist across restarts via JSON files.
- Runtime overrides are stored in `prompts/_overrides.json` (prompts) and `prompts/_settings_overrides.json` (settings) — both are git-ignored.
