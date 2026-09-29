# Monitoring & Maintenance Plan
## Day 7, Task 3

## 1. Latency thresholds
| Metric | Target | Alert threshold | Measured by |
|---|---|---|---|
| LLM turn latency (text-in to text-out) | < 1.5s avg | > 3s avg over 5 min | `measure_latency()` / production APM (e.g. Datadog, or FastAPI middleware timing) |
| End-to-end voice turn (STT + LLM + TTS) | < 2.5s | > 5s | Twilio call logs + app logs, once real telephony is wired up |
| Embedding lookup (vector store query) | < 100ms | > 500ms | In-process timing around `SimpleVectorStore.query` |
| Calendar/Gmail API call | < 1s | > 3s or any 5xx | Google API client logs |

## 2. Uptime targets
- Target **99.5% monthly uptime** for the FastAPI backend once deployed (Railway/Render/AWS) — appropriate for a
  business-hours-driven sales line, not a 24/7 critical system.
- Health check endpoint (`/health` in `app/main.py`) polled every 60s by the hosting platform's built-in monitor.
- Planned maintenance windows communicated at least 24h in advance if downtime is expected.

## 3. Weekly / periodic retraining & refresh cadence
| Task | Frequency | Trigger |
|---|---|---|
| Refresh `data/properties.csv` (new listings, price/possession updates) | Weekly | Sales team submits updates via a shared sheet → re-run Section 2.3 to rebuild embeddings |
| Refresh `data/faqs.csv` | Monthly, or on-demand | New recurring question observed in call transcripts (CRM `calls` table) |
| Vector store rebuild | Every time properties/FAQs change | Automatic — `SimpleVectorStore` rebuilds from CSV in-memory at each notebook/service start; no separate re-index step needed at this scale |
| Prompt updates (persona, guardrails) | As needed, reviewed monthly | Triggered by evaluation-report findings (e.g. an objection type the persona handles poorly) or a new prompt-injection pattern discovered |
| Chunking strategy re-evaluation | Whenever the FAQ set exceeds ~50 entries | Run Section 2.5's chunk-size evaluation again — sentence-level chunking usually starts to outperform full-row chunking past this size |

## 4. Backup strategy
- **SQLite CRM/property DB** (`nrp_agent_data.sqlite3`): back up nightly via a scheduled copy to cloud storage
  (S3/GCS bucket); retain 30 daily snapshots. At real production scale, migrate this to managed PostgreSQL
  (as the original brief suggests) with the hosting provider's automated backups.
- **`token.json` (Google OAuth token)**: do NOT back this up to shared/public storage — treat it like a credential.
- **`data/*.csv` source-of-truth files**: version-controlled in git; every change is already backed up by git history.
- **Call transcripts / CRM data**: subject to data-retention policy — confirm with legal how long client call data
  and PII (email, budget, name) may be retained, especially given clients are overseas and may be subject to
  GDPR (UK/EU-resident NRPs) in addition to Pakistani data-protection norms.

## 5. Security review cadence
- **Prompt injection test battery** (`run_full_battery()`, `prompt_injection` category): re-run after every system
  prompt change, and monthly regardless, since model updates can silently change guardrail behavior.
- **Dependency vulnerability scan**: monthly `pip list --outdated` + `npm audit` (if any Node tooling is added),
  or automate via GitHub Dependabot once this is in a git repo.
- **API key rotation**: rotate Gemini/Google OAuth credentials quarterly, or immediately if a key is suspected
  leaked (e.g. accidentally committed to git — check with `git log -p | grep -i "AIza"` style scans before every push).
- **Access review**: quarterly review of who has access to the Google Cloud project (Calendar/Gmail scopes), the
  CRM database, and the deployment platform's dashboard.

## 6. What to actually track once deployed (Day 6 Task 4)
| Metric | Why it matters |
|---|---|
| Average latency (per turn, per call) | User experience; a phone caller tolerates far less delay than a chat user |
| Voice quality (TTS failures, garbled audio reports) | Direct signal of TTS vendor issues |
| API failures (Gemini, Calendar, Gmail — by error code) | Distinguishes transient (retry-able) vs. structural (needs a code fix) issues — the notebook's `generate_text()`/`embed_documents()` retry logging is the starting point for this |
| Calendar/email failures | Booking that "succeeds" in conversation but silently fails to create the calendar event is the worst failure mode — must alert immediately, not just log |
| Booking success rate | % of `book` intent conversations that end with a confirmed calendar event |
| RAG misses (queries where retrieval returned low-relevance chunks) | Signals the FAQ/property dataset needs expanding |
| Prompt-injection attempts and block rate | Security posture over time |
