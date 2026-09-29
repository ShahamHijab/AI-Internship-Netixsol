# System Architecture & Conversation Flows
## NRP Line — AI Voice Agent for Overseas Pakistani Real Estate Investment

This document covers Day 1 Task 1 (architecture) and Day 1 Task 2 (conversation flows) of the capstone brief.
Diagrams are in Mermaid — they render natively on GitHub, in VS Code (with the Mermaid extension), and in most
Markdown viewers.

---

## 1. Voice Agent Architecture

```mermaid
flowchart TB
    caller[["Overseas caller\n(UK / US / Gulf)"]]

    subgraph telephony["Telephony layer (not built in this notebook — see note)"]
        twilio["Twilio Voice\n(phone line + audio streaming)"]
    end

    subgraph voice_io["Voice I/O"]
        stt["Speech-to-Text\n(Deepgram / Whisper in prod,\nSpeechRecognition in this build)"]
        tts["Text-to-Speech\n(Fish Audio in prod,\ngTTS in this build)"]
    end

    subgraph brain["Agent Brain — LangGraph"]
        intent["Intent Detection\n(Gemini)"]
        route{{"Router"}}
        rag["RAG node\n(FAQ + property search)"]
        rec["Recommendation node"]
        book["Booking node"]
        resch["Reschedule node"]
        cancel["Cancel node"]
        obj["Objection-handling node"]
        unsafe["Guardrail / unsafe node"]
        gen["Reply generation\n(Gemini + persona)"]
    end

    subgraph knowledge["Knowledge Layer"]
        vecstore[("Vector store\nNumPy cosine similarity\nover Gemini embeddings")]
        sqldb[("SQLite\nstructured property facts")]
    end

    subgraph workflow["Business Workflow Tools"]
        calendar["Google Calendar API\n(book / reschedule / cancel)"]
        gmail["Gmail API\n(notify relationship manager)"]
        crm[("CRM store\ncalls, profiles, appointments,\nfollow-ups")]
    end

    caller --> twilio --> stt --> intent
    intent --> route
    route --> rag & rec & book & resch & cancel & obj & unsafe
    rag --> vecstore
    rec --> vecstore
    rec --> sqldb
    rag & rec & book & resch & cancel & obj & unsafe --> gen
    gen --> tts --> twilio --> caller
    book --> calendar
    resch --> calendar
    book --> gmail
    intent --> crm
    book --> crm
```

**Notes on this diagram vs. the delivered notebook:**
- The **Telephony layer** (Twilio box) is *not* implemented in the notebook — per project scope, voice is
  simulated (typed input, spoken output) rather than a live phone line. The box is included here to show where
  it plugs in for a real deployment (see `app/main.py`).
- Every other box in the diagram **is** implemented and runnable in `NRP_Voice_Agent_Capstone.ipynb`.
- The **Vector store** is plain NumPy cosine similarity, not a hosted vector DB — a deliberate choice at this
  dataset size (see README for the reasoning; ChromaDB's native dependencies were an early kernel-crash source).

---

## 2. Component Responsibilities

| Layer | Component | Responsibility |
|---|---|---|
| Telephony | Twilio (prod only) | Answers the call, streams caller audio in, plays agent audio back |
| Voice I/O | STT | Converts caller speech to text |
| Voice I/O | TTS | Converts agent text reply to speech |
| Agent Brain | Intent Detection | Classifies each turn into one of 9 intents (faq, recommend, book, reschedule, cancel, objection, smalltalk, end_call, unsafe) |
| Agent Brain | Router | Conditional edge sending state to the right node based on intent |
| Agent Brain | RAG / Recommendation / Booking / Reschedule / Cancel / Objection nodes | Gather the context needed to answer (retrieval, SQL filter, or a fixed policy string) |
| Agent Brain | Reply generation | Turns retrieved context + persona + conversation history into one UrduLish reply |
| Knowledge | Vector store | Semantic search over FAQs and property descriptions |
| Knowledge | SQLite | Exact structured facts: price, availability, RDA eligibility, possession date |
| Workflow | Google Calendar | Creates/updates/deletes the video-walkthrough event with a Meet link |
| Workflow | Gmail | Emails the assigned relationship manager after a booking |
| Workflow | CRM store | Logs every call transcript, extracted client profile, appointment, and follow-up |

---

## 3. Conversation Flows (Day 1, Task 2)

### 3.1 Buyer inquiry
```mermaid
flowchart LR
    A[Greeting] --> B[Caller states purpose:\nown-use home in Pakistan]
    B --> C[Agent asks budget,\ncity, bedrooms]
    C --> D[RAG + SQL: recommend\n1-3 matching properties]
    D --> E{Interested?}
    E -->|Yes| F[Move to appointment booking]
    E -->|Objection| G[Objection handling]
    G --> D
    F --> H[Book video walkthrough]
    H --> I[Calendar event + Meet link\n+ email to relationship manager]
    I --> J[Goodbye + CRM log]
```

### 3.2 Investment inquiry
```mermaid
flowchart LR
    A[Greeting] --> B[Caller states:\npure investment, not living there]
    B --> C[Agent asks budget,\nrisk appetite, timeline]
    C --> D[Recommendation node sorts\nby rental_yield_pct]
    D --> E[Explain RDA discount +\nrepatriation process via RAG]
    E --> F{Interested?}
    F -->|Yes| G[Book video walkthrough]
    F -->|Objection: trust/distance| H[Objection handling]
    H --> D
    G --> I[Calendar + email + CRM log]
```

### 3.3 Commercial property inquiry
```mermaid
flowchart LR
    A[Greeting] --> B[Caller wants commercial\nshop/plaza unit]
    B --> C[Agent asks budget, city,\nexpected footfall/business type]
    C --> D[SQL filter: type = Commercial]
    D --> E[Highlight rental yield\n(commercial > residential)]
    E --> F{Interested?}
    F -->|Yes| G[Book walkthrough]
    F -->|No| H[Offer residential alternative]
    H --> D
```

### 3.4 Investment vs. returning-customer memory
```mermaid
flowchart LR
    A[Turn 1: caller states\nbudget + city] --> B[Profile updated:\nbudget_pkr, preferred_city]
    B --> C[Turn 2: caller asks\nfollow-up: "DHA mein options?"]
    C --> D[Profile carried in state;\nrecommend filtered by\nsaved budget + city]
    D --> E[Turn 3: "Us se sasti\nkoi option?"]
    E --> F[Recommendation re-run\nwith budget lowered,\nsame city/purpose remembered]
```

### 3.5 Appointment booking
```mermaid
flowchart TB
    A[Caller confirms interest\nin a specific property] --> B{name, email,\npreferred_city\nall known?}
    B -->|No| C[Ask for the missing field(s)\n— never guess]
    C --> B
    B -->|Yes| D[Confirm date/time\nin caller's own timezone]
    D --> E[book_video_walkthrough tool:\nGoogle Calendar event\n+ Meet link]
    E --> F[send_employee_notification:\nGmail to relationship manager]
    F --> G[log_appointment to CRM]
    G --> H[Confirm back to caller]
```

### 3.6 Appointment rescheduling
```mermaid
flowchart LR
    A[Caller requests reschedule] --> B[Look up existing\nevent_id from CRM]
    B --> C[Ask new date/time\n+ confirm timezone]
    C --> D[reschedule_video_walkthrough\ntool call]
    D --> E[Calendar + attendee\nnotified automatically]
    E --> F[Update appointments\ntable status]
```

### 3.7 Appointment cancellation
```mermaid
flowchart LR
    A[Caller requests cancellation] --> B[Confirm intent once\n"Are you sure?"]
    B -->|Confirmed| C[cancel_video_walkthrough\ntool call]
    C --> D[Calendar event deleted,\nattendee notified]
    D --> E[Update appointments\ntable status = cancelled]
    B -->|Changed mind| F[Return to normal conversation]
```

### 3.8 Prompt injection / unsafe request (guardrail flow)
```mermaid
flowchart LR
    A[Caller sends injection attempt,\ne.g. "reveal your system prompt"] --> B[Intent detector\nclassifies as 'unsafe']
    B --> C[unsafe node: refuse\npolitely, no internal details]
    C --> D[Reply generation stays\non real-estate topic]
    D --> E[Conversation continues\nnormally]
```
