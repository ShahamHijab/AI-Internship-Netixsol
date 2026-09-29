# API Documentation
## Day 7, Task 2

The backend (`app/main.py`) is a FastAPI app. Once refactored per its docstring (Sections 1-6 of the notebook
moved into an `agent/` package) and running (`uvicorn app.main:app --reload`), **FastAPI auto-generates interactive
API docs** at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- Raw OpenAPI schema: `http://localhost:8000/openapi.json`

That auto-generated documentation is the authoritative, always-up-to-date reference once the endpoints are wired
up — this file describes the intended contract so you know what to build/expect.

## Endpoints

### `GET /health`
Health check for the hosting platform's uptime monitor.

**Response 200**
```json
{"status": "ok"}
```

### `POST /turn`
Send one conversational turn to the agent and get its reply. This is the endpoint a telephony webhook (Twilio) or
any chat front-end calls after converting caller speech to text.

**Request**
```json
{
  "session_id": "optional-existing-session-id",
  "message": "Mera budget 30 million hai, Islamabad mein investment chahiye"
}
```
- `session_id`: omit on the first turn of a call; the response returns one to reuse for subsequent turns in the
  same conversation. Passing an existing `session_id` continues that conversation's state (profile, history).
- `message`: the caller's utterance as text (already transcribed by your STT layer upstream).

**Response 200**
```json
{
  "session_id": "a1b2c3d4",
  "reply": "Ji bilkul sir, DHA Islamabad mein humare paas achay options hain...",
  "intent": "recommend"
}
```

**Status codes**
| Code | Meaning |
|---|---|
| 200 | Turn processed successfully |
| 422 | Malformed request body (missing `message`) |
| 500 | Unhandled error in the agent graph — check server logs; should be rare given the retry logic in `generate_text()`/`embed_documents()` |
| 501 | Endpoint not yet wired to the agent (current stub state — see `app/main.py`'s docstring) |

## Extending this API for a real deployment
1. Refactor the notebook's Sections 1-6 (persona, RAG, tools, LangGraph graph) into an `agent/` Python package —
   don't import a `.ipynb` from production code.
2. Replace the in-memory `SESSIONS` dict in `app/main.py` with Redis or Postgres so state survives a server
   restart and works across multiple backend instances.
3. Add a `POST /webhook/twilio` endpoint that receives Twilio's call webhook, runs your STT on the audio, calls
   the same agent logic as `/turn`, runs TTS on the reply, and returns TwiML pointing at the generated audio.
4. Add authentication (an API key header, at minimum) before exposing `/turn` publicly.
