from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import Response, FileResponse
from app.voice import speech_to_text, text_to_speech
from fastapi.staticfiles import StaticFiles
from urllib.parse import quote

"""
FastAPI wrapper for the refactored NRP Voice Agent.

Run: uvicorn app.main:app --reload
"""
import uuid
from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel

from agent.graph import AgentState, fresh_state, run_turn
from agent.profile import extract_profile_update
from agent.crm import log_call, log_appointment

app = FastAPI(title="NRP Voice Agent API")

@app.get("/")
def home():
    return FileResponse("app/static/index.html")

# In-memory session store for demo purposes only.
SESSIONS = {}


class TurnRequest(BaseModel):
    session_id: Optional[str] = None
    message: str


class AppointmentRequest(BaseModel):
    property_id: str
    client_name: str
    client_email: str
    start_iso: str
    end_iso: Optional[str] = None
    timezone: str
    notes: Optional[str] = ""
    event_id: Optional[str] = None
    new_start_iso: Optional[str] = None


class TurnResponse(BaseModel):
    session_id: str
    reply: str
    intent: Optional[str] = None
    appointment_request: Optional[AppointmentRequest] = None


class CRMLogRequest(BaseModel):
    call_id: str
    intent: Optional[str] = None
    appointment_status: Optional[str] = None
    event_id: Optional[str] = None


def _appointment_request(state: AgentState) -> Optional[AppointmentRequest]:
    if state["intent"] != "book" or state["retrieved"] != ["READY_TO_BOOK"]:
        return None

    p = state["profile"]
    return AppointmentRequest(
        property_id=p["property_of_interest"],
        client_name=p["name"],
        client_email=p["email"],
        start_iso=p["start_iso"],
        timezone=p["timezone"],
        notes=p.get("notes", ""),
        event_id=p.get("event_id"),
        new_start_iso=p.get("new_start_iso"),
        end_iso=p.get("end_iso"),
    )

@app.post("/turn", response_model=TurnResponse)
def turn(req: TurnRequest):
    session_id = req.session_id or str(uuid.uuid4())[:8]
    state = SESSIONS.get(session_id) or fresh_state(session_id)

    print("DEBUG session_id:", session_id)
    print("DEBUG incoming message:", repr(req.message))

    if not req.message or not req.message.strip():
        raise ValueError("Incoming message is empty.")

    state["history"].append({
        "role": "user",
        "content": req.message.strip()
    })

    print("DEBUG history before run_turn:", state["history"])
    state["profile"] = extract_profile_update(req.message, state["profile"])
    state = run_turn(state)
    SESSIONS[session_id] = state

    return TurnResponse(
        session_id=session_id,
        reply=state["reply"],
        intent=state["intent"],
        appointment_request=_appointment_request(state),
    )

@app.post("/voice")
async def voice(
    audio: UploadFile = File(...),
    session_id: Optional[str] = None,
):
    """
    Voice turn:

    Browser microphone
        -> Deepgram STT
        -> existing LangGraph agent
        -> Fish Audio TTS
        -> MP3 response
    """

    session_id = session_id or str(uuid.uuid4())[:8]

    # Read browser-recorded audio
    audio_bytes = await audio.read()

    if not audio_bytes:
        raise HTTPException(
            status_code=400,
            detail="Audio file is empty."
        )

    # 1. Speech -> Text
    try:
        transcript = await speech_to_text(
            audio_bytes,
            audio.content_type or "audio/webm",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Speech recognition failed: {exc}",
        )

    if not transcript:
        raise HTTPException(
            status_code=400,
            detail="No speech detected."
        )

    # 2. Reuse the EXACT existing agent pipeline
    state = SESSIONS.get(session_id) or fresh_state(session_id)

    state["history"].append({
        "role": "user",
        "content": transcript,
    })

    state["profile"] = extract_profile_update(
        transcript,
        state["profile"],
    )

    try:
        state = run_turn(state)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Agent processing failed: {exc}",
        )

    SESSIONS[session_id] = state

    reply = state.get("reply", "")

    if not reply:
        raise HTTPException(
            status_code=500,
            detail="Agent returned an empty reply."
        )

    # 3. Text -> Speech
    try:
        audio_response = await text_to_speech(reply)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Text-to-speech failed: {exc}",
        )

    # Return MP3 with useful metadata in headers
    return Response(
        content=audio_response,
        media_type="audio/mpeg",
        headers={
            "X-Session-ID": session_id,
            "X-Transcript": quote(transcript[:500], safe=""),
            "X-Agent-Reply": quote(reply[:1000], safe=""),
        },
    )

@app.post("/crm/log")
def crm_log(req: CRMLogRequest):
    status = req.appointment_status or req.intent or "other"
    log_appointment(
        req.call_id,
        req.event_id,
        None,
        None,
        None,
        status,
    )
    log_call(req.call_id, "")
    return {"status": "logged"}


@app.get("/health")
def health():
    return {"status": "ok"}
