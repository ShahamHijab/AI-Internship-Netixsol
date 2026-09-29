# Voice Stack Evaluation — Fish Audio vs. ElevenLabs
## Day 1, Task 4

This project's demo uses free `gTTS`/`SpeechRecognition` (per project scope: a simulated, not live-phone, voice
agent). This document is the required production-stack evaluation for a real deployment — it does not claim to
have run head-to-head latency benchmarks ourselves (neither service's API key was in scope for this build); it is
a structured comparison based on each vendor's own published capabilities, to justify the recommendation below.

| Dimension | Fish Audio | ElevenLabs | Notes |
|---|---|---|---|
| Latency | Optimized for streaming, sub-second time-to-first-audio-chunk on their low-latency models | Also offers a low-latency streaming model (Flash/Turbo tier) with comparable time-to-first-byte | Roughly comparable at the top tier of each; real-world latency depends more on your network hop to their region than the vendor gap |
| Naturalness | Strong prosody on expressive/emotional speech; actively marketed for conversational agents | Widely regarded as the naturalness benchmark in the industry, especially for English | ElevenLabs likely has a slight edge for pure English; the gap narrows for Urdu/code-switched speech (see below) |
| Emotion control | Supports emotion/style tags | Supports style exaggeration + stability controls | Comparable feature sets |
| Streaming | Native low-latency streaming API, designed for voice-agent use cases | Native streaming API (websocket) also available | Comparable |
| Voice cloning | High-quality few-shot cloning | Industry-leading cloning quality, larger sample library | ElevenLabs generally rated higher for clone fidelity on typical (non-Urdu) benchmarks |
| Pricing | Competitive, generally priced below ElevenLabs at similar tiers for production volume | Premium pricing, especially at higher-quality tiers | Fish Audio has a cost edge at scale |
| Multilingual support | Broad multilingual coverage including South Asian languages | Broad multilingual coverage, historically stronger on major European/East Asian languages | Both list Urdu; real-world quality needs a listening test with actual production phrases before committing |
| Urdu pronunciation | Reported to handle Urdu phonemes reasonably well | Mixed reports on Urdu-specific pronunciation accuracy | **Recommendation: run a blind listening test on 10-15 real UrduLish sales phrases before final vendor lock-in** — this is the one claim in this table that genuinely needs an in-house test with API access, not a vendor comparison |
| Urdu-English code-switching (UrduLish) | Marketed strength — smoother mid-sentence language switching | Not a primary marketed strength; can sound like two separate voices spliced together mid-sentence | This is the deciding factor for this specific project |

### Conclusion
**Fish Audio is the recommended choice for this project**, primarily because of its code-switching capability —
this agent's entire value proposition depends on natural UrduLish (mixing Urdu and English fluidly within a single
sentence, e.g. *"Ji bilkul, DHA Phase 8 mein ek villa available hai jo aap ke budget mein fit ho jayega"*).
ElevenLabs' naturalness edge matters more for single-language (pure English or pure Urdu) use cases; it doesn't
close the gap on this project's specific requirement. Its lower per-character cost at production call volumes is
a secondary but real factor for a business that expects "dozens of calls every day."

**Caveat:** this is a desk evaluation from each vendor's public documentation and industry reputation, not a
head-to-head API benchmark run by this team (no paid API keys for either service were provisioned for this
capstone). Before a real production commitment, budget a half-day to run the same 10-15 UrduLish test phrases
through both APIs and do a blind listen with 3-5 native Urdu speakers — that listening test, not this table, should
be the final tie-breaker.

### Suggested production voice stack (unchanged from the original brief)
| Component | Choice |
|---|---|
| Speech-to-Text | Deepgram Nova-3 (Whisper Large V3 if offline support is required) |
| LLM | Gemini (this build), swappable for GPT or Claude |
| Agent Framework | LangGraph |
| Knowledge Layer | Vector store + SQLite (this build uses NumPy in-memory; move to Pinecone/Weaviate past a few hundred documents) |
| Text-to-Speech | Fish Audio |
| Workflow Automation | n8n (see `n8n/nrp_voice_agent_workflow.json`) |
| Calendar | Google Calendar API |
| Email | Gmail API |
| Backend | FastAPI |
| Deployment | Docker + Railway/Render/AWS |
