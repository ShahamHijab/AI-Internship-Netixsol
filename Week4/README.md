# NRP Line — AI Voice Agent for Overseas Pakistani Real Estate Investment

Capstone build for the "Production-Grade AI Voice Agent for Real Estate" brief, scoped to a specific niche:
**Non-Resident Pakistanis (NRPs)** investing remotely, via video walkthroughs instead of physical visits.

## Folder contents
```
NRP_Voice_Agent_Capstone.ipynb   <- main notebook, run this in VS Code / Jupyter
data/properties.csv              <- structured property knowledge base (NRP-focused fields)
data/faqs.csv                    <- FAQ knowledge base for RAG (RDA, POA, trust, repatriation, etc.)
requirements.txt
.env.example                     <- copy to .env and fill in your Gemini key(s)
app/main.py                      <- FastAPI starter for real deployment (Day 7)
Dockerfile
docs/ARCHITECTURE_AND_FLOWS.md       <- architecture diagram + 8 conversation flowcharts (Day 1)
docs/VOICE_STACK_EVALUATION.md       <- Fish Audio vs. ElevenLabs comparison (Day 1)
docs/MONITORING_MAINTENANCE_PLAN.md  <- thresholds, backups, security review cadence (Day 7)
docs/USER_ADMIN_TROUBLESHOOTING_GUIDE.md <- day-to-day operation + common fixes (Day 7)
docs/API_DOCUMENTATION.md            <- FastAPI endpoint contract (Day 7)
docs/DEMO_SCRIPT.md                  <- 10-minute stakeholder demo script (Day 7)
docs/EXECUTIVE_REPORT.docx           <- objectives, architecture, evaluation, limitations, roadmap (Day 7)
docs/NRP_Capstone_Demo_Deck.pptx     <- stakeholder demo slide deck (Day 7)
n8n/nrp_voice_agent_workflow.json    <- importable Call->Intent->Calendar->Email->CRM automation (Day 4)
n8n/README.md                        <- how to import + what backend endpoints it expects
```

## Why the kernel used to crash (and what changed)
The original version used **ChromaDB** as the vector store. ChromaDB pulls in `onnxruntime`/`hnswlib` native
binaries, and on a lot of Windows/VS Code Python setups those collide with the OpenMP runtime that numpy/pandas
already loaded — this **hard-crashes the whole kernel process with no Python traceback**, which is exactly the
"keeps crashing no matter what I change" symptom (the crash happens below Python, so no `try/except` in the
notebook can catch it).

This version removes ChromaDB entirely and replaces it with a ~15-line **pure NumPy cosine-similarity search**
(Section 2.3 of the notebook). At this dataset's size (8 properties, 10 FAQs) it's just as accurate and has **zero
native dependencies**, so it cannot crash the kernel that way. It also switches from the deprecated
`google-generativeai` package to the current **`google-genai`** SDK throughout (chat, intent detection, generation,
profile extraction, embeddings all go through `client.models.*` now).

**Also install packages in a terminal, not inside the notebook.** Running `%pip install` inside a kernel that has
already imported numpy/pandas can silently swap in a binary-incompatible wheel and crash the kernel on the very
next import. Cell 0 now only *checks* that packages are importable — it doesn't install anything.

## Setup (VS Code)
1. Open this folder in VS Code, create a **clean** virtual environment: `python -m venv .venv`
2. Activate it, then in that terminal (kernel not yet started): `pip install -r requirements.txt`
3. `cp .env.example .env` then edit `.env` and add your Gemini API key
   (get one free at https://aistudio.google.com/app/apikey).
4. Open `NRP_Voice_Agent_Capstone.ipynb`, select `.venv` as the kernel, run cells top to bottom.
5. **Optional — Calendar/Gmail:** In Google Cloud Console, create a project, enable "Google Calendar API" and
   "Gmail API", create an OAuth Client ID of type **Desktop app**, download it as `credentials.json` into this
   folder. Run the OAuth cell in Section 4.1 (uncomment the 3 lines) once — it opens a browser to authorize, then
   caches `token.json` so you won't need to re-auth.

## If it STILL crashes after this
Open a plain terminal (not Jupyter) in your activated `.venv` and run:
```
python -c "import pandas, numpy, google.genai; print('ok')"
```
- If **that terminal command itself crashes** (not just an error message, but the terminal closes/dies), the
  problem is your Python environment, not this notebook's code — most often a corrupted venv, a Windows-Store
  Python install, or a 32-bit/64-bit mismatch. Fix: delete `.venv`, reinstall Python from python.org, recreate the
  venv, reinstall requirements.
- If it prints `ok` cleanly but the *notebook* still crashes, it's almost always the Jupyter/ipykernel package
  itself being out of date: `pip install --upgrade ipykernel jupyter` in the same venv, then fully restart VS Code.

## What actually runs out of the box
- Sections 0–3 (persona, RAG, SQL, recommendation engine) run with **only** a Gemini key.
- Section 8 (`run_conversation()`) runs a full simulated voice call: you type, Ahmed replies in UrduLish text
  **and** speaks it via gTTS.
- Section 6 (evaluation: grounding, chunk-size comparison, 45-case test battery, prompt-injection, latency) runs
  standalone against the graph, and `write_evaluation_report()` writes a filled-in `EVALUATION_REPORT.md` you can
  paste straight into `docs/EXECUTIVE_REPORT.docx`'s Section 4 table.
- Sections 4.1–4.3 (Calendar/Gmail) need `credentials.json` — everything else works without it, the booking node
  will just report `MISSING_FIELDS`/be ready to call the tool once you wire the OAuth cell in.
- `n8n/nrp_voice_agent_workflow.json` is importable into any n8n instance, but expects two backend endpoints
  (`/turn` returning an `appointment_request`, and `/crm/log`) that `app/main.py` currently stubs — see
  `n8n/README.md` and `docs/API_DOCUMENTATION.md` for the exact contract.

## Known limitations (be upfront about these in your report)
- No real phone line: this is a simulated voice agent (typed input, spoken output), per project scope decision.
  `app/main.py` + Dockerfile sketch the path to a real Twilio-backed deployment.
- gTTS renders Urdu script but doesn't truly code-switch UrduLish the way Fish Audio/ElevenLabs would — swap in
  either once you have API keys, the `speak()` function is the only place that needs to change (full comparison
  in `docs/VOICE_STACK_EVALUATION.md`).
- The NumPy vector store is in-memory and rebuilt each run (cheap at this dataset size); if you scale to thousands
  of documents, move to a hosted vector DB instead of re-introducing a local native one.
- `app/main.py`'s `/turn` and `/crm/log` endpoints are stubs with docstrings showing how to wire them — refactor
  the notebook's Sections 1–6 into an `agent/` package before deploying, rather than importing a notebook in
  production. The n8n workflow depends on this refactor being done.
- `docs/EXECUTIVE_REPORT.docx`'s evaluation table has placeholder dashes — run Section 6 end-to-end with a live
  API key and copy the numbers from the generated `EVALUATION_REPORT.md` before presenting it.
- LLM-judge scores (naturalness/persuasiveness in the evaluation battery) are an automated proxy, not real human
  raters — spot-check with an actual person before citing them externally.
