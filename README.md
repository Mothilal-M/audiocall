# Audiocall — Twilio + Google ADK Voice Agent

A real-time voice agent that lets you call any phone number and have a natural AI conversation powered by **Twilio Media Streams** and **Google ADK** (Gemini Live API).

```
Phone caller ──► Twilio ──► WebSocket (μ-law 8 kHz) ──► Your Server
                                                             │   ▲
                                              audio convert  ▼   │
                                           Google ADK / Gemini Live API
                                           (PCM-16 16 kHz in, 24 kHz out)
```

---

## How it works

1. You call `POST /call` with a phone number.  
2. Twilio dials the number; when the call connects Twilio hits `POST /voice` and receives TwiML instructing it to open a **bidirectional WebSocket** media stream.  
3. Your server receives the callerʼs audio (μ-law / 8 kHz), converts it to PCM-16 / 16 kHz, and streams it to **Google ADK** via `LiveRequestQueue`.  
4. The **Gemini Live API** agent produces spoken audio responses (PCM-16 / 24 kHz).  
5. The server converts that audio back to μ-law / 8 kHz and sends it to Twilio, which plays it on the call.

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Python ≥ 3.13 | `audioop` was removed in 3.13; we use `audioop-lts` as replacement |
| [Twilio account](https://www.twilio.com/) | Free trial works; you need an account SID, auth token, and a phone number |
| [Google AI Studio API key](https://aistudio.google.com/apikey) *or* Google Cloud project | For Gemini Live API or Vertex AI Live API respectively |
| Public HTTPS URL | Twilio needs to reach your server; use **ngrok** for local dev |

---

## Setup

### 1. Install dependencies

```bash
pip install -e .
```

### 2. Configure environment variables

```bash
cp .env.example .env
# Edit .env and fill in all values
```

Key variables:

| Variable | Description |
|---|---|
| `GOOGLE_API_KEY` | Google AI Studio API key (Gemini Live API) |
| `TWILIO_ACCOUNT_SID` | Twilio Account SID (starts with `AC`) |
| `TWILIO_AUTH_TOKEN` | Twilio Auth Token |
| `TWILIO_PHONE_NUMBER` | Your Twilio phone number in E.164 format |
| `SERVER_HOST` | Public hostname Twilio can reach (no `https://` prefix) |
| `USE_TLS` | `true` for production/ngrok HTTPS; `false` for plain HTTP |
| `AGENT_MODEL` | Gemini model ID (see `.env.example` for options) |

### 3. Expose your server with ngrok (local development)

```bash
ngrok http 8000
```

Copy the hostname (e.g. `abc123.ngrok-free.app`) and set `SERVER_HOST=abc123.ngrok-free.app` in your `.env`.

### 4. Configure Twilio webhook (inbound calls only)

If you also want to receive *inbound* calls, go to the Twilio Console → Phone Numbers → your number → Voice Configuration and set the **A CALL COMES IN** webhook to:

```
https://your-server-host/voice   (HTTP POST)
```

---

## Running the server

```bash
python -m audiocall.main
```

or

```bash
uvicorn audiocall.main:app --host 0.0.0.0 --port 8000
```

---

## Making a call

```bash
curl -X POST https://lovely-brooms-win.loca.lt/call \
  -H "Content-Type: application/json" \
  -d '{"to": "+8801732033963"}'
```

Response:
```json
{
  "call_sid": "CAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "status": "queued"
}
```

The callee will receive your Twilio number's call. Once they answer, they are connected live to the AI agent.

---

## Project structure

```
audiocall/
├── __init__.py      # Package init
├── agent.py         # Google ADK agent definition (model, instruction)
└── main.py          # FastAPI app:
                     #   POST /call    – initiate outbound call
                     #   POST /voice   – Twilio TwiML webhook
                     #   WS   /stream  – bidirectional audio bridge
.env.example         # Environment variable template
pyproject.toml       # Project metadata and dependencies
```

---

## Audio format conversion

| Direction | Format In | Conversion | Format Out |
|---|---|---|---|
| Twilio → ADK | μ-law 8 kHz | `ulaw2lin` + `ratecv` 8k→16k | PCM-16 16 kHz |
| ADK → Twilio | PCM-16 24 kHz | `ratecv` 24k→8k + `lin2ulaw` | μ-law 8 kHz |

Conversion is done with [`audioop-lts`](https://pypi.org/project/audioop-lts/) — a maintained port of the Python 3.11 `audioop` stdlib module for Python 3.13+.

---

## Configuration options

### Switching to Vertex AI Live API (production)

Edit `.env`:

```bash
GOOGLE_GENAI_USE_VERTEXAI=TRUE
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
AGENT_MODEL=gemini-live-2.5-flash-native-audio
```

No code changes required.

### Choosing a voice

Edit `audiocall/agent.py` — add a `Gemini` instance with `speech_config`:

```python
from google.adk.models.google_llm import Gemini
from google.genai import types

llm = Gemini(
    model="gemini-2.5-flash-native-audio-preview-12-2025",
    speech_config=types.SpeechConfig(
        voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Kore")
        )
    ),
)

root_agent = Agent(name="phone_assistant", model=llm, instruction="...")
```

Available voices: Puck, Charon, Kore, Fenrir, Aoede, Leda, Orus, Zephyr (and more on native audio models).

---

## Security notes

- In production, validate Twilio webhook signatures using the `X-Twilio-Signature` header with `twilio.request_validator.RequestValidator`.  
- Restrict `/call` to authenticated internal callers only — it can trigger billable Twilio calls.  
- Store secrets in environment variables or a secret manager, never in source code.
