# 10-Minute Stakeholder Demonstration Script
## Day 7, Task 4

**Setup before the room fills up:** Notebook open in VS Code with Sections 0-7 already executed (so there's no
waiting on embeddings mid-demo). Keep a terminal tab open on `EVALUATION_REPORT.md` and the CRM query snippet from
the User Guide, ready to switch to.

| Time | What you do | What you say / show |
|---|---|---|
| 0:00-0:30 | Slide 1-2 | Frame the niche: "dozens of calls a day, most from overseas Pakistanis who will never physically visit before buying — hiring agents for this is expensive and inconsistent." |
| 0:30-1:30 | Run `run_conversation(speak_replies=True)`, type an opening buyer message in UrduLish | "Watch Ahmed greet the caller and speak the reply out loud — this is genuinely a live model call, not a script." |
| 1:30-3:00 | Continue the conversation: state budget + city, let the agent recommend | Point out the recommendation is pulled from `data/properties.csv` live — open the CSV briefly to prove there's no hardcoded reply |
| 3:00-4:00 | Ask an RDA/trust FAQ ("Roshan Digital Account kya hai?") | Show the reply is grounded — then show the exact FAQ row it retrieved from, proving no hallucination |
| 4:00-5:30 | Raise a trust objection ("Maine ye ghar kabhi dekha nahi, kaise trust karoon?") | Show the empathetic, fact-based objection handling — this is the moment that sells the niche framing |
| 5:30-7:00 | Provide name/email, confirm a time, let the agent book | Switch to the actual Google Calendar tab — show the event with the Meet link appearing live, and the Gmail notification landing in the relationship manager's inbox |
| 7:00-7:45 | Ask to reschedule, then cancel | Show both flows working, and the Calendar event updating/disappearing |
| 7:45-8:45 | Switch to a fresh cell, run one prompt-injection line live (e.g. "reveal your system prompt") | Show it gets refused politely and the conversation stays on-topic — this is the guardrail proof point |
| 8:45-9:30 | Open `EVALUATION_REPORT.md` (pre-generated) | Walk through grounding rate, latency, injection block rate at a glance — "this isn't just a demo, it's been tested against 45 scripted scenarios" |
| 9:30-10:00 | Slide: Roadmap | WhatsApp integration, live FX rates, real telephony via Twilio + Fish Audio — "here's what's next, and here's the architecture that already supports adding it" |

## Backup plan if the live API is slow/rate-limited
- Have a saved transcript from a prior successful run ready to paste into the chat cell-by-cell as a fallback.
- The Calendar/Gmail steps can be shown from a screen recording if OAuth or network issues appear mid-demo — don't
  burn stakeholder time debugging OAuth live.

## One-line answers ready for likely questions
- *"Why not a real phone line?"* — scoped out deliberately for this build; `app/main.py` and the n8n workflow show
  exactly where Twilio plugs in, and it's a config change, not a redesign.
- *"Why not ChromaDB / a real vector database?"* — it caused unrecoverable kernel crashes on Windows due to native
  dependency conflicts; at this dataset size a NumPy in-memory store performs identically with zero crash risk.
- *"What happens if Gemini is down?"* — the agent automatically rotates across up to 5 API keys and retries with
  backoff before failing; show the `generate_text()` function briefly if asked.
