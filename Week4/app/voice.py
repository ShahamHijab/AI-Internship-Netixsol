import os
import httpx

from dotenv import load_dotenv

load_dotenv()

DEEPGRAM_URL = "https://api.deepgram.com/v1/listen"
FISH_API_URL = "https://api.fish.audio/v1/tts"


async def speech_to_text(
    audio_bytes: bytes,
    content_type: str = "audio/webm",
) -> str:
    """
    Convert browser audio to text using Deepgram Nova-3.

    Supports UrduLish / English + Urdu code-switching.
    """

    api_key = os.getenv("DEEPGRAM_API_KEY")

    if not api_key:
        raise RuntimeError("DEEPGRAM_API_KEY is not configured")

    if not audio_bytes:
        raise ValueError("Audio bytes are empty")

    headers = {
        "Authorization": f"Token {api_key}",
        "Content-Type": content_type,
    }

    params = {
        "model": "nova-3",
        "language": "ur",
        "smart_format": "true"
    }

    async with httpx.AsyncClient(timeout=60) as client:

        response = await client.post(
            DEEPGRAM_URL,
            headers=headers,
            params=params,
            content=audio_bytes,
        )

    # Give us the actual Deepgram error instead of hiding it.
    if response.status_code >= 400:
        raise RuntimeError(
            f"Deepgram HTTP {response.status_code}: "
            f"{response.text}"
        )

    data = response.json()

    # DEBUG: print Deepgram response in Docker logs
    print("DEEPGRAM RESPONSE:", data)

    try:
        transcript = (
            data["results"]
            ["channels"][0]
            ["alternatives"][0]
            ["transcript"]
        )
    except (KeyError, IndexError, TypeError) as exc:

        raise RuntimeError(
            f"Could not extract Deepgram transcript: {data}"
        ) from exc

    transcript = transcript.strip()

    print("DEEPGRAM TRANSCRIPT:", repr(transcript))

    return transcript


async def text_to_speech(text: str) -> bytes:
    """
    Convert agent reply to MP3 using Fish Audio.
    """

    api_key = os.getenv("FISH_API_KEY")

    if not api_key:
        raise RuntimeError("FISH_API_KEY is not configured")

    if not text or not text.strip():
        raise ValueError("Cannot synthesize empty text")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "model": "s2.1-pro-free",
    }

    payload = {
        "text": text.strip(),
        "format": "mp3",
    }

    async with httpx.AsyncClient(timeout=60) as client:

        response = await client.post(
            FISH_API_URL,
            headers=headers,
            json=payload,
        )

    if response.status_code >= 400:
        raise RuntimeError(
            f"Fish Audio HTTP {response.status_code}: "
            f"{response.text}"
        )

    return response.content