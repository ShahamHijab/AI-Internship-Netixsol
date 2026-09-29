# User Guide, Admin Guide & Troubleshooting Guide
## Day 7, Task 2

---

## Part 1 — User Guide (for the sales team / relationship managers)

### What this system does
Ahmed (the AI agent) has a simulated phone conversation with an overseas Pakistani client, answers their property
questions using verified company data, recommends matching properties, and — when the client is ready — books a
video walkthrough call directly on your Google Calendar and emails you (the relationship manager) the details.

### How to run a live demo conversation
1. Open `NRP_Voice_Agent_Capstone.ipynb` in VS Code, run all cells top to bottom (Sections 0–7).
2. In Section 8, run: `run_conversation(speak_replies=True)`
3. Type as the client would speak. Ahmed replies in text and out loud.
4. Type `exit` to end the call — the transcript and extracted client profile are automatically saved to the CRM.

### What happens after a booking
- A Google Calendar event is created on the connected Google account, with a Google Meet link, at the time and
  timezone the client confirmed.
- An email is sent (via Gmail) to the relationship manager's address with the client's name, email, property of
  interest, meeting time, and any notes.
- The call is logged in the CRM (`nrp_agent_data.sqlite3`, tables `calls`, `client_profiles`, `appointments`).

### Checking CRM data
```python
import sqlite3, pandas as pd
conn = sqlite3.connect("nrp_agent_data.sqlite3")
pd.read_sql("SELECT * FROM client_profiles", conn)
pd.read_sql("SELECT * FROM appointments", conn)
```

---

## Part 2 — Admin Guide

### Updating the property catalog
Edit `data/properties.csv` directly (Excel, Google Sheets export, or a text editor) — columns must stay in the
same order/names. Re-run Section 2 of the notebook to rebuild the SQLite table and vector store from the updated
file. No other code changes are needed for a normal listing update.

### Updating FAQs
Edit `data/faqs.csv` the same way — add a row for any new recurring question the sales team notices in call
transcripts, then re-run Section 2.

### Changing the LLM model
Edit `CHAT_MODEL_NAME` in Section 0.1. Check https://ai.google.dev/gemini-api/docs/deprecations first if you're
reacting to a "model not found" error — Google retires model IDs every few months.

### Adding more Gemini API keys (for rate-limit headroom)
Add to `.env`: `GEMINI_API_KEYS=key1,key2,key3`. See the caveat in Section 0.1 of the notebook — keys must be on
separate Google Cloud projects to actually multiply your quota, not just separate key strings under one project.

### Re-authorizing Google Calendar/Gmail
Delete `token.json` and re-run the OAuth cell in Section 4.1 — this forces a fresh browser login and consent.

### Editing the persona / system prompt
Edit `SYSTEM_PROMPT` and the `PERSONA_PHRASES` dict in Section 1 of the notebook. After any change, re-run the
`prompt_injection` category of `run_full_battery()` to confirm guardrails still hold.

---

## Part 3 — Troubleshooting Guide

| Symptom | Likely cause | Fix |
|---|---|---|
| `AssertionError: Set GEMINI_API_KEYS...` | `.env` missing or not loaded | Confirm `.env` exists next to the notebook and has `GEMINI_API_KEYS=...` (or `GEMINI_API_KEY=...`), then restart the kernel |
| `ClientError 404 NOT_FOUND` mentioning the model name | Google retired the pinned model ID | Check https://ai.google.dev/gemini-api/docs/deprecations, update `CHAT_MODEL_NAME` in Section 0.1 |
| `ServerError 503 UNAVAILABLE` ("high demand") | Transient Gemini overload | Already auto-retried across the key pool by `generate_text()`; if it still fails after cycling all keys, wait a minute and re-run |
| Kernel dies with no Python traceback at all | Almost always a native-dependency conflict (this project intentionally avoids ChromaDB for this reason) or a corrupted Python environment | Recreate the venv from scratch: `python -m venv .venv`, reinstall `requirements.txt`, restart VS Code. See README's "if it still crashes" section |
| `google.auth.exceptions...` on Calendar/Gmail cells | Expired/missing OAuth token or missing `credentials.json` | Ensure `credentials.json` (OAuth Client ID, Desktop app type) is in the project folder; delete `token.json` and re-run Section 4.1 |
| Booking node returns `MISSING_FIELDS` | Client's name/email/city weren't captured in conversation yet | Expected behavior — the agent is designed to never book without these; ask the missing info in the conversation |
| gTTS audio doesn't play in VS Code | VS Code's Jupyter output audio widget needs `ipywidgets`/`ffmpeg` in some setups | `pip install ipywidgets`; alternatively open the generated `.mp3` file directly from the file explorer |
| Retrieval returns irrelevant FAQ/property chunks | Dataset too small/generic for the query, or a genuinely new question outside current FAQs | Add a row to `data/faqs.csv` covering that question, re-run Section 2 |
| `run_full_battery()` is slow / burns quota fast | The LLM-judge step calls Gemini once per non-injection test case | Pass `sample_judge_categories=[...]` to restrict judging to 1-2 categories for a quick smoke test |

### Where to look for logs
- **Conversation-level**: printed execution trace (`Execution trace: detect_intent -> ... -> generate`) from `run_turn(verbose=True)`.
- **CRM**: `nrp_agent_data.sqlite3` — every call's transcript and profile.
- **Evaluation**: `EVALUATION_REPORT.md`, generated by `write_evaluation_report()`.
