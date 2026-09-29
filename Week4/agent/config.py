import os, json, sqlite3, datetime, time, uuid, textwrap, logging
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai import errors as genai_errors

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")
_raw_keys = os.getenv("GEMINI_API_KEYS", "") or os.getenv("GEMINI_API_KEY", "")
GEMINI_API_KEYS = [k.strip() for k in _raw_keys.split(",") if k.strip()]
if not GEMINI_API_KEYS:
    raise RuntimeError("Set GEMINI_API_KEYS=key1,key2,... (or GEMINI_API_KEY=key) in a .env file.")
_clients = [genai.Client(api_key=k) for k in GEMINI_API_KEYS]
_client_idx = 0
CHAT_MODEL_NAME = "gemini-3.6-flash"
EMBED_MODEL_NAME = "gemini-embedding-001"
DB_PATH = str(PROJECT_ROOT / "nrp_agent_data.sqlite3")
logging.getLogger("google_genai").setLevel(logging.ERROR)
logging.getLogger("google_genai.models").setLevel(logging.ERROR)

def _next_client():
    global _client_idx
    c = _clients[_client_idx % len(_clients)]
    _client_idx += 1
    return c

def _is_retryable(e: Exception) -> bool:
    if isinstance(e, genai_errors.ServerError):
        return True
    return isinstance(e, genai_errors.ClientError) and getattr(e, "code", None) == 429

def generate_text(prompt: str, rounds: int = 1, base_delay: float = 1.0) -> str:
    n = len(_clients)
    last_err = None

    for _ in range(n):
        c = _next_client()

        try:
            response = c.models.generate_content(
                model=CHAT_MODEL_NAME,
                contents=prompt
            )

            return response.text.strip()

        except Exception as e:
            if not _is_retryable(e):
                raise

            last_err = e

    raise RuntimeError(
        f"Gemini API unavailable after trying {n} key(s). "
        f"Last error: {last_err}"
    )

def embed_documents(texts, task_type="RETRIEVAL_DOCUMENT"):
    texts = [str(t).strip() for t in texts if t is not None and str(t).strip()]
    
    if not texts:
        return []

    all_embeddings = []
    batch_size = 16
    max_retries = 3

    for start in range(0, len(texts), batch_size):
        batch = texts[start:start + batch_size]

        for attempt in range(max_retries * len(_clients)):
            c = _next_client()

            try:
                resp = c.models.embed_content(
                    model=EMBED_MODEL_NAME,
                    contents=batch,
                    config=types.EmbedContentConfig(
                        task_type=task_type
                    )
                )

                values = [e.values for e in resp.embeddings]

                if len(values) != len(batch):
                    raise RuntimeError(
                        f"Got {len(values)} embeddings for {len(batch)} texts."
                    )

                all_embeddings.extend(values)
                break

            except Exception as e:
                if (
                    not _is_retryable(e)
                    or attempt == max_retries * len(_clients) - 1
                ):
                    raise

                time.sleep(2 ** (attempt % max_retries))

    return all_embeddings

def embed_query(text):
    if text is None or not str(text).strip():
        raise ValueError("Cannot embed an empty query.")

    return embed_documents(
        [str(text).strip()],
        task_type="RETRIEVAL_QUERY"
    )[0]