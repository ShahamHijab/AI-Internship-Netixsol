# n8n Workflow — Call → Intent → Property Match → Appointment → Calendar → Email → CRM

`nrp_voice_agent_workflow.json` implements the exact pipeline the brief asks for (Day 4, Task 4), adapted to call
out to this project's FastAPI backend for the AI parts (intent detection + property matching, which the notebook's
LangGraph agent already does in one call) while using n8n's native nodes for the business actions (Calendar,
Gmail) and CRM logging.

## Import
1. In n8n: **Workflows → Import from File** → select `nrp_voice_agent_workflow.json`.
2. Set two environment variables in your n8n instance: `AGENT_BASE_URL` (e.g. `https://your-deployed-agent.com`)
   and `RELATIONSHIP_MANAGER_EMAIL`.
3. Create two credentials in n8n (**Settings → Credentials**): a Google Calendar OAuth2 credential and a Gmail
   OAuth2 credential, then attach them to the "Create/Reschedule/Cancel Calendar Event" and "Notify Relationship
   Manager" nodes (the JSON references placeholder credential IDs — n8n will prompt you to reassign them on import).
4. Activate the workflow. The webhook URL n8n shows you (e.g. `https://your-n8n.app/webhook/nrp-call`) is what your
   telephony/STT layer should POST to.

## Required backend changes
This workflow assumes two things the notebook's FastAPI stub (`app/main.py`) doesn't fully implement yet:
1. **`POST /turn`** should return an `appointment_request` object when `intent == "book"` **and** every required
   field (name, email, city, date/time, timezone) has already been confirmed in the conversation — i.e. exactly
   when the notebook's `node_book` would report `"READY_TO_BOOK"` instead of `"MISSING_FIELDS"`. Shape:
   ```json
   {
     "session_id": "...", "reply": "...", "intent": "book",
     "appointment_request": {
       "property_id": "P006", "client_name": "Ahmed Raza", "client_email": "ahmed@example.com",
       "start_iso": "2026-10-04T18:00:00", "end_iso": "2026-10-04T18:30:00", "timezone": "Europe/London",
       "notes": "First-time NRP investor, budget 30M PKR"
     }
   }
   ```
   For reschedule/cancel intents, include `event_id` (looked up from the CRM `appointments` table by `call_id`)
   plus the new time for reschedule.
2. **`POST /crm/log`** — a small endpoint wrapping the notebook's `log_call()`/`log_appointment()` functions, so
   n8n can record the outcome of every branch (including "other", where no calendar/email action happens but the
   call should still be logged).

Neither change is large — both are thin wrappers around functions the notebook already defines in Sections 4.4 and
5. They're left as an explicit backend task (not pre-built into `app/main.py`) because they depend on how you
refactor the notebook into the `agent/` package per that file's docstring.

## Error handling built into this workflow
- The two HTTP Request nodes and all three Calendar nodes have `retryOnFail: true` with 3 attempts and a backoff
  wait, matching the brief's "handle failures and retries" requirement (Day 4, Task 4).
- "Update CRM" runs after **every** branch (book/reschedule/cancel/other), so a call is logged even if no
  calendar/email action was needed, and even if the AI step returned an intent this workflow doesn't specially
  handle (those fall into "other" and skip straight to CRM logging + responding).
- For production, also set a workflow-level **Error Workflow** (Settings → this workflow → Error Workflow) pointing
  at a small separate workflow that posts a Slack/email alert — left blank here since it depends on an existing
  n8n instance's workflow IDs.
