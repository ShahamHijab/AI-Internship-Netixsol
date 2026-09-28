
from __future__ import annotations
import json, logging, os, re, time, uuid
from functools import lru_cache
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_ZIP = ROOT / "data" / "afl_datasets.zip"
PREDICTION_DISCLAIMER = "Predicted probability, not a certainty."

# --- Task 1: hardening constants -------------------------------------------------
TOOL_TIMEOUT_SECONDS = float(os.getenv("AFL_TOOL_TIMEOUT", "4"))         # retrieval lookups
PREDICT_TIMEOUT_SECONDS = float(os.getenv("AFL_PREDICT_TIMEOUT", "15"))  # per model inference call
MODEL_LOAD_TIMEOUT_SECONDS = float(os.getenv("AFL_MODEL_LOAD_TIMEOUT", "60"))  # one-time model/feature load
_TOOL_POOL = ThreadPoolExecutor(max_workers=8, thread_name_prefix="afl-tool")

def call_with_timeout(fn, *args, timeout: float = TOOL_TIMEOUT_SECONDS, **kwargs):
    """Run a tool/model call with a hard timeout so one slow call can't hang the graph."""
    future = _TOOL_POOL.submit(fn, *args, **kwargs)
    try:
        return future.result(timeout=timeout)
    except FutureTimeoutError:
        raise TimeoutError(f"{getattr(fn, '__name__', 'tool')} exceeded {timeout}s timeout")

# Simple in-memory abuse/rate tracking (per conversation_id). A production deployment
# would back this with Redis/DB, but the counters and thresholds are the real contract.
_OFFTOPIC_STRIKES: Dict[str, deque] = defaultdict(deque)
STRIKE_WINDOW_SECONDS = 300      # rolling 5-minute window
STRIKE_ESCALATION_THRESHOLD = 3  # repeated off-topic/injection probes in the window

def record_offtopic_strike(conversation_id: str) -> int:
    """Record an off-topic/injection probe and return the current strike count in the window."""
    now = time.time()
    q = _OFFTOPIC_STRIKES[conversation_id]
    q.append(now)
    while q and now - q[0] > STRIKE_WINDOW_SECONDS:
        q.popleft()
    return len(q)

TEAM_ALIASES = {
    "pies":"Collingwood Magpies","magpies":"Collingwood Magpies",
    "cats":"Geelong Cats","blues":"Carlton Blues","hawks":"Hawthorn Hawks",
    "tigers":"Richmond Tigers","swans":"Sydney Swans","suns":"Gold Coast Suns",
    "dockers":"Fremantle Dockers","giants":"Greater Western Sydney Giants",
    "dees":"Melbourne Demons","demons":"Melbourne Demons","power":"Port Adelaide Power",
    "crows":"Adelaide Crows","eagles":"West Coast Eagles","saints":"St Kilda Saints",
    "kangaroos":"North Melbourne Kangaroos","roos":"North Melbourne Kangaroos",
    "bombers":"Essendon Bombers","dons":"Essendon Bombers",
    "dogs":"Western Bulldogs","bulldogs":"Western Bulldogs",
    "lions":"Brisbane Lions",
}
OFFTOPIC = re.compile(r"\b(cricket|ipl|nba|nfl|valorant|python|javascript|politics|bitcoin|coding|homework)\b", re.I)
INJECTION = re.compile(r"\b(ignore|disregard|override|bypass|forget).{0,60}\b(scope|rules|instructions|afl|system)\b|\bpretend\b.{0,60}\bunrestricted\b", re.I)

class AFLState(TypedDict, total=False):
    user_query: str
    conversation_id: str
    conversation_history: List[Dict[str, str]]
    intent: str
    tool_results: List[Dict[str, Any]]
    final_response: str
    prediction_metadata: Dict[str, Any]
    trace: List[Dict[str, Any]]
    validation_status: str

def load_data():
    import zipfile
    with zipfile.ZipFile(DATA_ZIP) as z:
        files = z.namelist()
        r = next(x for x in files if "round_by_round" in x and x.endswith(".csv"))
        s = next(x for x in files if "seasonal_stats" in x and x.endswith(".csv"))
        t = next(x for x in files if "team_matches" in x and x.endswith(".csv"))
        p = next(x for x in files if "players_info" in x and x.endswith(".csv"))
        round_stats = pd.read_csv(z.open(r), low_memory=False)
        seasonal = pd.read_csv(z.open(s), low_memory=False)
        teams = pd.read_csv(z.open(t), low_memory=False)
        players = pd.read_csv(z.open(p), low_memory=False)
    for df in (round_stats, seasonal, teams):
        if "match_date" in df.columns:
            df["match_date"] = pd.to_datetime(df["match_date"], errors="coerce")
    return round_stats, seasonal, teams, players

ROUND, SEASONAL, TEAM, PLAYERS = load_data()
DATA_MAX_DATE = max(ROUND["match_date"].max(), TEAM["match_date"].max()).date()

def normalize_team(x: str) -> str:
    return re.sub(r"\s+", " ", str(x).strip()).lower()

def resolve_team(text: str) -> str:
    q = normalize_team(text)
    if q in TEAM_ALIASES:
        return TEAM_ALIASES[q]
    teams = sorted(set(TEAM["team_name"].dropna().astype(str)) if "team_name" in TEAM.columns else set(TEAM["team"].dropna().astype(str)))
    exact = [t for t in teams if normalize_team(t) == q]
    if exact: return exact[0]
    partial = [t for t in teams if q in normalize_team(t) or normalize_team(t) in q]
    if len(partial) == 1: return partial[0]
    raise ValueError(f"Could not resolve AFL team '{text}'.")

def classify(query: str, history: List[Dict[str,str]]) -> str:
    q = query.lower()
    if INJECTION.search(q) or OFFTOPIC.search(q):
        return "off_topic"
    if re.search(r"\b(who will win|who wins|predict|probability|top[- ]score|top scorer)\b", q):
        return "prediction"
    if re.search(r"\b(record|stats?|disposals?|goals?|marks?|tackles?|last match|won|lost|season)\b", q):
        return "retrieval"
    if re.search(r"\b(clearance|mark|behind|goal|free kick|quarter|afl rule|rules)\b", q):
        return "factual"
    return "off_topic"

def refusal() -> str:
    return "I’m scoped to AFL only, so I can’t help with that. I can help with AFL teams, players, matches, statistics, rules, or predictions."

def retrieval(query: str) -> Dict[str, Any]:
    q = query.lower()
    if "record against" in q or "vs" in q or "versus" in q:
        parts = re.split(r"\b(?:vs|versus|against)\b", q, maxsplit=1)
        if len(parts) == 2:
            a, b = resolve_team(parts[0].strip(" ?'\"")), resolve_team(parts[1].strip(" ?'\""))
            t = TEAM.copy()
            arows = t[(t["team_name"]==a) & (t["opponent"]==b)]
            brows = t[(t["team_name"]==b) & (t["opponent"]==a)]
            wins = int((arows["result"]=="W").sum()) + int((brows["result"]=="L").sum())
            losses = int((arows["result"]=="L").sum()) + int((brows["result"]=="W").sum())
            draws = int((arows["result"]=="D").sum() + (brows["result"]=="D").sum()) // 2
            return {"type":"h2h","team_a":a,"team_b":b,"wins":wins,"losses":losses,"draws":draws}
    m = re.search(r"(20\d{2})", q)
    year = int(m.group(1)) if m else None
    # Team season record
    for raw in sorted(set(TEAM["team_name"].dropna().astype(str)), key=len, reverse=True):
        if raw.lower() in q:
            rows = TEAM[TEAM["team_name"]==raw]
            if year is not None:
                rows = rows[rows["year"]==year]
                if not rows.empty:
                    return {"type":"team_season","team":raw,"year":year,
                            "wins":int((rows["result"]=="W").sum()),
                            "losses":int((rows["result"]=="L").sum()),
                            "draws":int((rows["result"]=="D").sum())}
    return {"type":"unsupported","message":"The requested AFL statistic was not safely resolved from the supplied structured data."}

@lru_cache(maxsize=1)
def _load_match_predictor():
    from .predictor import MatchPredictor
    return MatchPredictor(ROOT/"models")

@lru_cache(maxsize=1)
def _load_player_predictor():
    from .predictor import PlayerPredictor
    return PlayerPredictor(ROOT/"models")

def warm_up() -> None:
    """Load models once at startup so the first user request isn't slow (and can't hit the timeout)."""
    call_with_timeout(_load_match_predictor, timeout=MODEL_LOAD_TIMEOUT_SECONDS)
    call_with_timeout(_load_player_predictor, timeout=MODEL_LOAD_TIMEOUT_SECONDS)

def predict_match(home: str, away: str, date: str) -> Dict[str, Any]:
    # Models are cached after first load; every call runs under a hard timeout (Task 1).
    model = call_with_timeout(_load_match_predictor, timeout=MODEL_LOAD_TIMEOUT_SECONDS)
    return call_with_timeout(model.predict, home, away, date, timeout=PREDICT_TIMEOUT_SECONDS)

def predict_top_player(home: str, away: str, date: str) -> Dict[str, Any]:
    model = call_with_timeout(_load_player_predictor, timeout=MODEL_LOAD_TIMEOUT_SECONDS)
    return call_with_timeout(model.predict, home, away, date, timeout=PREDICT_TIMEOUT_SECONDS)

def run_graph(query: str, conversation_id: str, history: Optional[List[Dict[str,str]]] = None) -> AFLState:
    started = time.perf_counter()
    history = history or []
    intent = classify(query, history)
    state: AFLState = {"user_query":query,"conversation_id":conversation_id,
                       "conversation_history":history,"intent":intent,"tool_results":[],
                       "trace":[],"prediction_metadata":{}}
    state["trace"].append({"node":"router","intent":intent})
    if intent == "off_topic":
        strikes = record_offtopic_strike(conversation_id)
        state["final_response"] = refusal()
        state["validation_status"] = "safe"
        state["prediction_metadata"] = {}
        if strikes >= STRIKE_ESCALATION_THRESHOLD:
            state["abuse_flag"] = True
            state["trace"].append({"node":"abuse_guard","strikes":strikes,
                                    "action":"flagged_for_review"})
            logging.warning(json.dumps({"event":"repeated_offtopic_probe",
                                         "conversation_id":conversation_id,"strikes":strikes}))
    elif intent == "retrieval":
        try:
            result = call_with_timeout(retrieval, query)
            state["tool_results"] = [result]
            if result.get("type") == "team_season":
                state["final_response"] = f"{result['team']} in {result['year']}: {result['wins']} wins, {result['losses']} losses, {result['draws']} draws."
                state["validation_status"] = "validated"
            elif result.get("type") == "h2h":
                state["final_response"] = f"{result['team_a']} vs {result['team_b']} in historical supplied data: {result['wins']} wins, {result['losses']} losses, {result['draws']} draws."
                state["validation_status"] = "validated"
            else:
                state["final_response"] = result["message"]
                state["validation_status"] = "clarify"
        except TimeoutError:
            state["final_response"] = (f"That lookup took too long (>{TOOL_TIMEOUT_SECONDS:.0f}s) and was stopped. "
                "Please try a more specific team/season query.")
            state["validation_status"] = "tool_timeout"
            state["tool_results"] = [{"error":"TimeoutError"}]
        except Exception as e:
            state["final_response"] = "I couldn’t safely resolve that AFL statistic from the supplied data. Please give the team/player and season more precisely."
            state["validation_status"] = "clarify"
            state["tool_results"] = [{"error":type(e).__name__}]
        state["trace"].append({"node":"retrieval","tools":["structured_pandas"]})
    elif intent == "prediction":
        # Require an explicit matchup/date for production safety.
        dm = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", query)
        vs = re.split(r"\b(?:vs|versus)\b", query.lower())
        if not dm or len(vs) != 2:
            state["final_response"] = "I can make an AFL prediction when you provide the two teams and an exact match date (YYYY-MM-DD)."
            state["validation_status"] = "clarify"
        else:
            try:
                candidates=[]
                for raw in sorted(set(TEAM["team_name"].dropna().astype(str)), key=len, reverse=True):
                    clean=raw.strip()
                    pos=query.lower().find(normalize_team(clean))
                    if pos>=0: candidates.append((pos,clean))
                for alias, canonical in TEAM_ALIASES.items():
                    pos=re.search(r"\b"+re.escape(alias)+r"\b", query.lower())
                    if pos: candidates.append((pos.start(),canonical))
                mentioned=[]
                for _,team_name in sorted(candidates,key=lambda x:x[0]):
                    if team_name not in mentioned: mentioned.append(team_name)
                if len(mentioned) < 2: raise ValueError("Need two teams")
                home, away = mentioned[0], mentioned[1]
                result = predict_match(home, away, dm.group(1))
                state["tool_results"] = [result]
                state["prediction_metadata"] = result
                state["final_response"] = (f"{home} vs {away}: {result['predicted_label']} "
                    f"with model probability {result['probability']:.1%}. "
                    f"{PREDICTION_DISCLAIMER} Key pre-match inputs: {', '.join(result['key_inputs'][:3])}.")
                state["validation_status"] = "validated"
            except TimeoutError:
                state["final_response"] = ("The prediction model took too long to respond, so I couldn't "
                    f"complete this request within {PREDICT_TIMEOUT_SECONDS:.0f}s. Please try again shortly. " + PREDICTION_DISCLAIMER)
                state["validation_status"] = "tool_timeout"
                state["tool_results"] = [{"error":"TimeoutError"}]
            except Exception:
                state["final_response"] = "I couldn’t safely resolve that prediction request. Please provide the exact two AFL teams and date in YYYY-MM-DD format."
                state["validation_status"] = "clarify"
        state["trace"].append({"node":"prediction","tools":["match_predictor"]})
    else:
        state["final_response"] = ("I can answer AFL concepts such as rules and match terminology, "
                                    "but exact statistics should be requested with a team/player and season.")
        state["validation_status"] = "safe"
        state["trace"].append({"node":"direct_answer","tools":[]})
    state["trace"].append({"node":"validation","status":state["validation_status"]})
    state["latency_ms"] = round((time.perf_counter()-started)*1000,2)
    return state
