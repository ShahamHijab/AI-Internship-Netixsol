
import json, logging, time, uuid
from collections import defaultdict, deque
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from .core import run_graph, warm_up

logging.basicConfig(level=logging.INFO, format="%(message)s")
app = FastAPI(title="AFL Assistant API", version="1.0.0")


@app.on_event("startup")
def _startup():
    try:
        warm_up()
    except Exception as e:  # never block startup; requests will retry loading
        logging.warning(json.dumps({"event": "warmup_failed", "error": type(e).__name__}))

# --- Task 1: basic rate / abuse handling -----------------------------------------
# Simple in-memory sliding-window limiter keyed by client IP. A real deployment would
# move this to Redis/API-gateway, but the policy (window, cap, response) is the contract.
RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_MAX_REQUESTS = 30
_REQUEST_LOG: dict[str, deque] = defaultdict(deque)

def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"

def _rate_limited(key: str) -> bool:
    now = time.time()
    q = _REQUEST_LOG[key]
    q.append(now)
    while q and now - q[0] > RATE_LIMIT_WINDOW_SECONDS:
        q.popleft()
    return len(q) > RATE_LIMIT_MAX_REQUESTS


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    conversation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat")
def chat(req: ChatRequest, request: Request):
    client_key = _client_key(request)
    if _rate_limited(client_key):
        logging.warning(json.dumps({"event": "rate_limited", "client": client_key}))
        raise HTTPException(status_code=429, detail="Too many requests, please slow down.")

    started = time.perf_counter()
    try:
        result = run_graph(req.message, req.conversation_id)
    except Exception as e:
        # Node/tool-level exceptions are already handled inside run_graph; this is the
        # last-resort safety net so the API never 500s into an unstructured error.
        logging.error(json.dumps({"event": "unhandled_error", "conversation_id": req.conversation_id,
                                   "error": type(e).__name__}))
        raise HTTPException(status_code=503, detail="AFL assistant is temporarily unavailable. Please retry.")

    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    log = {
        "query": req.message,
        "conversation_id": req.conversation_id,
        "intent": result.get("intent"),
        "tools_called": [t for x in result.get("trace", []) for t in x.get("tools", [])],
        "latency_ms": latency_ms,
        # No LLM call sits in this deterministic router/retrieval/prediction pipeline,
        # so token usage is a fixed 0 today; the field is kept so a future LLM-backed
        # node (e.g. free-text factual answers) can populate it without a schema change.
        "token_usage": {"prompt_tokens": 0, "completion_tokens": 0},
        "validation_status": result.get("validation_status"),
        "abuse_flag": result.get("abuse_flag", False),
        "prediction_metadata": result.get("prediction_metadata", {}),
    }
    logging.info(json.dumps(log, default=str))

    return {
        "conversation_id": req.conversation_id,
        "response": result["final_response"],
        "intent": result["intent"],
        "prediction_metadata": result.get("prediction_metadata", {}),
        "latency_ms": latency_ms,
    }
