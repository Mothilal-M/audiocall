"""
Twilio + Google ADK Voice Agent server.

Architecture
============
Phone caller → Twilio → WebSocket (μ-law / 8 kHz) → this server
                                                          ↓  ↑  (audio conversion)
                                              Google ADK (PCM-16 / 16 kHz in,
                                                           PCM-16 / 24 kHz out)

Audio conversion pipeline
--------------------------
Inbound  (Twilio → ADK) :  μ-law 8 kHz  →  PCM-16 16 kHz
Outbound (ADK → Twilio) :  PCM-16 24 kHz →  μ-law 8 kHz

Endpoints
---------
POST /call   – Initiate an outbound call via Twilio REST API
POST /voice  – Twilio voice webhook; returns TwiML <Connect><Stream>
WS   /stream – Bidirectional Twilio Media Stream ↔ ADK bridge
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import uuid
from math import gcd
from urllib.parse import quote

# audioop-lts is a drop-in replacement for the stdlib `audioop` module that was
# removed in Python 3.13.  Install it with: pip install audioop-lts
import audioop  # type: ignore[import-not-found]
import numpy as np
from scipy import signal

from dotenv import load_dotenv

# ── env must be loaded BEFORE google-adk imports so that os.getenv() calls
# inside the SDK (and in agent.py) see the correct values at import time.
load_dotenv()

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect  # noqa: E402
from fastapi.responses import Response  # noqa: E402
from twilio.rest import Client as TwilioClient  # noqa: E402

from google.adk.agents.live_request_queue import LiveRequestQueue  # noqa: E402
from google.adk.agents.run_config import RunConfig, StreamingMode  # noqa: E402
from google.adk.runners import Runner  # noqa: E402
from google.adk.sessions import InMemorySessionService  # noqa: E402
from google.genai import types  # noqa: E402

from audiocall.agent import build_agent  # noqa: E402

# ---------------------------------------------------------------------------
# Audio processing utilities
# ---------------------------------------------------------------------------


class StreamingResampler:
    """
    Stateful sample-rate converter for streaming PCM-16 audio.

    Carrying the FIR filter delay-line state (``zi``) across calls makes
    chunked processing bit-identical to filtering the whole stream at once,
    so chunk boundaries introduce no discontinuities — unlike calling
    ``scipy.signal.resample_poly`` per chunk, whose per-call filter edge
    effects produce audible clicks/warble at every boundary.

    One instance handles one direction of one stream; create a fresh pair
    per connection.
    """

    def __init__(self, in_rate: int, out_rate: int) -> None:
        g = gcd(in_rate, out_rate)
        self.up = out_rate // g
        self.down = in_rate // g
        fs_up = in_rate * self.up

        # Telephony-band lowpass: pass 3400 Hz, stop 4000 Hz, 60 dB attenuation.
        # ~97 taps at fs=16k / ~145 at fs=24k → ~3 ms group delay either way.
        numtaps, beta = signal.kaiserord(60.0, (4000 - 3400) / (fs_up / 2))
        numtaps |= 1
        taps = signal.firwin(numtaps, 3700.0, window=("kaiser", beta), fs=fs_up)
        # Zero-stuffing by `up` scales the passband down by `up`; compensate so
        # overall gain stays exactly 1 (firwin gives unity DC gain).
        self.taps = taps.astype(np.float64) * self.up
        assert abs(self.taps.sum() - self.up) < 1e-6

        self._zi_zero = np.zeros(numtaps - 1)
        self.reset()

    def reset(self) -> None:
        """Drop all carried state (use when the output stream is discarded)."""
        self.zi = self._zi_zero.copy()
        self.phase = 0
        self._carry = b""

    def process(self, chunk: bytes) -> bytes:
        """Convert a chunk of int16 PCM bytes; may return b"" for tiny inputs."""
        data = self._carry + chunk
        self._carry = b""
        if len(data) & 1:
            # int16 frames can split across WS messages; carry the odd byte.
            self._carry = data[-1:]
            data = data[:-1]
        if not data:
            return b""

        x = np.frombuffer(data, dtype=np.int16).astype(np.float64)

        if self.up > 1:
            xu = np.zeros(len(x) * self.up)
            xu[:: self.up] = x
        else:
            xu = x

        y, self.zi = signal.lfilter(self.taps, 1.0, xu, zi=self.zi)

        out = y[self.phase :: self.down]
        self.phase = (self.phase - len(xu)) % self.down

        return np.clip(np.rint(out), -32768, 32767).astype(np.int16).tobytes()


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Suppress the noisy "1000 None" WebSocket Normal Closure log that ADK emits
# at the end of every call — it's not an application error, just the stream
# closing cleanly, but ADK logs it at ERROR level.
logging.getLogger("google_adk.google.adk.flows.llm_flows.base_llm_flow").setLevel(
    logging.CRITICAL
)

# Also suppress normal WebSocket closure errors from google.genai
logging.getLogger("google.genai.live").setLevel(logging.CRITICAL)

# ---------------------------------------------------------------------------
# Configuration from environment variables
# ---------------------------------------------------------------------------
TWILIO_ACCOUNT_SID: str = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN: str = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER: str = os.environ.get("TWILIO_PHONE_NUMBER", "")

# SERVER_HOST should be your public hostname (e.g. abc123.ngrok.io).
# Twilio needs to reach this address for both the HTTP webhook and
# the WebSocket media stream.
# Strip any accidental scheme prefix (e.g. "https://host" → "host")
_raw_host = os.environ.get("SERVER_HOST", "localhost:8000")
SERVER_HOST: str = (
    _raw_host.removeprefix("https://").removeprefix("http://").rstrip("/")
)
USE_TLS: bool = os.environ.get("USE_TLS", "true").lower() == "true"

# How long the caller must be silent (ms) before Gemini treats the utterance
# as finished and starts replying.  Lower = snappier responses, but too low
# cuts callers off when they pause mid-sentence.  Tune via env, no rebuild.
VAD_SILENCE_MS: int = int(os.environ.get("VAD_SILENCE_MS", "200"))

WS_SCHEME = "wss" if USE_TLS else "ws"
HTTP_SCHEME = "https" if USE_TLS else "http"

# ---------------------------------------------------------------------------
# Phase 1: Application-level objects (created once at startup)
# ---------------------------------------------------------------------------
APP_NAME = "audiocall"

app = FastAPI(title="Twilio + Google ADK Voice Agent")

session_service = InMemorySessionService()

twilio_client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# POST /call  – initiate an outbound call
# ---------------------------------------------------------------------------
@app.post("/call")
async def make_call(request: Request) -> dict:
    """
    Initiate an outbound Twilio call that connects the callee to the AI agent.

    Request body (JSON):
        {
            "to": "+15551234567"   // E.164 format
            "role": "site_manager" // optional, for logging/analytics
        }

    Returns:
        {
            "call_sid": "CA...",
            "status": "queued"
        }
    """
    data = await request.json()
    to_number: str = data.get("to", "").strip()
    role: str = data.get("role", "Manager").strip()

    if not to_number:
        return {
            "error": "Missing required field 'to' with the destination phone number"
        }

    call = twilio_client.calls.create(
        to=to_number,
        from_=TWILIO_PHONE_NUMBER,
        url=f"{HTTP_SCHEME}://{SERVER_HOST}/voice?role={role}",
    )

    logger.info("Outbound call initiated: SID=%s  to=%s", call.sid, to_number)
    return {"call_sid": call.sid, "status": call.status}


# ---------------------------------------------------------------------------
# POST /voice  – Twilio voice webhook (returns TwiML)
# ---------------------------------------------------------------------------
@app.post("/voice")
async def voice_webhook(request: Request) -> Response:
    """
    Called by Twilio when the call is answered.
    Returns TwiML that instructs Twilio to open a bidirectional media stream
    to our /stream WebSocket endpoint.
    """
    role = request.query_params.get("role", "Manager")

    # Forward the role to the WebSocket so the bridge (and agent) can use it.
    # Twilio media-stream URLs support query params, which the /stream handler
    # reads off websocket.query_params on connect.
    stream_url = f"{WS_SCHEME}://{SERVER_HOST}/stream?role={quote(role)}"

    twiml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        "<Connect>"
        f'<Stream url="{stream_url}"/>'
        "</Connect>"
        "</Response>"
    )
    logger.info("Twilio voice webhook hit for role=%s; directing stream to %s", role, stream_url)
    return Response(content=twiml, media_type="application/xml")


# ---------------------------------------------------------------------------
# WS /stream  – Twilio bidirectional Media Stream ↔ Google ADK bridge
# ---------------------------------------------------------------------------
@app.websocket("/stream")
async def stream_websocket(websocket: WebSocket) -> None:
    """
    Bridge between a Twilio bidirectional Media Stream and the ADK agent.

    Twilio sends audio as μ-law encoded at 8 000 Hz.
    Google ADK (Gemini Live API) expects 16-bit PCM at 16 000 Hz.
    Google ADK returns 16-bit PCM at 24 000 Hz.
    We must convert back to μ-law 8 000 Hz before sending to Twilio.
    """
    await websocket.accept()

    # Role forwarded from /voice via the Stream URL query param. Drives the
    # role-aware agent instruction (manager vs. worker greeting & framing).
    role = websocket.query_params.get("role", "Manager")
    logger.info("Twilio WebSocket connection accepted (role=%s)", role)

    # Build a fresh, role-aware agent + runner for this call.
    runner = Runner(
        app_name=APP_NAME,
        agent=build_agent(role),
        session_service=session_service,
    )

    # ── Phase 2: Session Initialization ─────────────────────────────────────────
    user_id = "caller"
    session_id = str(uuid.uuid4())

    await session_service.create_session(
        app_name=APP_NAME,
        user_id=user_id,
        session_id=session_id,
    )
    logger.info("ADK session created: %s", session_id)

    run_config = RunConfig(
        streaming_mode=StreamingMode.BIDI,
        response_modalities=["AUDIO"],
        # Enable transcription so we can log what was said
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        # Tighten VAD: respond faster after the caller stops speaking.
        # END_SENSITIVITY_HIGH + a short silence window cuts the "wait" after
        # each utterance from the default ~800 ms down to VAD_SILENCE_MS.
        # START_SENSITIVITY_HIGH makes Gemini notice the caller's voice sooner
        # (faster turn starts and barge-in).  If callers get cut off while
        # pausing mid-sentence, raise VAD_SILENCE_MS (e.g. 300-400).
        realtime_input_config=types.RealtimeInputConfig(
            automatic_activity_detection=types.AutomaticActivityDetection(
                start_of_speech_sensitivity=(
                    types.StartSensitivity.START_SENSITIVITY_HIGH
                ),
                end_of_speech_sensitivity=types.EndSensitivity.END_SENSITIVITY_HIGH,
                silence_duration_ms=VAD_SILENCE_MS,
            )
        ),
    )

    live_request_queue = LiveRequestQueue()

    # Per-connection mutable state (accessed via closures below)
    stream_sid: str | None = None

    # Stateful resamplers — one per direction so filter state is continuous
    # across chunks (no boundary clicks) for the lifetime of the stream.
    inbound_resampler = StreamingResampler(8000, 16000)
    outbound_resampler = StreamingResampler(24000, 8000)

    # ── Phase 3: Concurrent bidirectional streaming ──────────────────────────────

    async def upstream_task() -> None:
        """
        Receive audio from Twilio WebSocket and forward to the ADK agent.

        Message flow:
          Twilio WS msg (μ-law / 8 kHz, base64)
            → base64 decode
            → audioop.ulaw2lin  (μ-law → 16-bit PCM)
            → StreamingResampler (8 kHz → 16 kHz, stateful, no boundary clicks)
            → LiveRequestQueue.send_realtime
        """
        nonlocal stream_sid

        try:
            while True:
                raw = await websocket.receive_text()
                msg: dict = json.loads(raw)
                event_type: str = msg.get("event", "")

                if event_type == "connected":
                    logger.info(
                        "Twilio Media Stream connected (protocol=%s)",
                        msg.get("protocol"),
                    )

                elif event_type == "start":
                    stream_sid = msg.get("streamSid")
                    start_meta = msg.get("start", {})
                    logger.info(
                        "Media Stream started: streamSid=%s  callSid=%s",
                        stream_sid,
                        start_meta.get("callSid", "unknown"),
                    )

                elif event_type == "media":
                    # 1. Decode base64 → raw μ-law bytes
                    payload_b64: str = msg["media"]["payload"]
                    ulaw_data: bytes = base64.b64decode(payload_b64)

                    # 2. μ-law → 16-bit PCM @ 8 000 Hz
                    pcm_8k: bytes = audioop.ulaw2lin(ulaw_data, 2)

                    # 3. Resample 8 000 Hz → 16 000 Hz (required by ADK) and
                    #    forward each 20 ms chunk immediately — the stateful
                    #    resampler keeps audio continuous across chunks, so no
                    #    accumulation (and no added latency) is needed.
                    pcm_16k = inbound_resampler.process(pcm_8k)

                    if pcm_16k:
                        blob = types.Blob(
                            mime_type="audio/pcm;rate=16000", data=pcm_16k
                        )
                        live_request_queue.send_realtime(blob)

                elif event_type == "dtmf":
                    digit = msg.get("dtmf", {}).get("digit", "?")
                    logger.info("DTMF digit: %s", digit)

                elif event_type == "stop":
                    logger.info("Media Stream stopped by Twilio")
                    break

        except WebSocketDisconnect:
            logger.info("Twilio WebSocket disconnected (upstream)")
        except Exception:
            logger.exception("Unexpected error in upstream_task")
        finally:
            # Signal the ADK runner to stop
            live_request_queue.close()

    async def downstream_task() -> None:
        """
        Receive ADK agent events and forward audio back to Twilio.

        Message flow:
          runner.run_live() → Event (inline_data PCM-16 / 24 kHz)
            → StreamingResampler (24 kHz → 8 kHz, stateful, no boundary clicks)
            → audioop.lin2ulaw (16-bit PCM → μ-law)
            → base64 encode
            → Twilio WS media message

        Barge-in / interruption:
          When the ADK detects that the user started speaking while the agent
          was responding, it fires event.interrupted=True.  At that point we
          must tell Twilio to discard any audio already queued for playback
          (via the Twilio 'clear' message).
        """
        try:
            async for event in runner.run_live(
                user_id=user_id,
                session_id=session_id,
                live_request_queue=live_request_queue,
                run_config=run_config,
            ):
                # ── Log transcriptions for observability ──────────────────────
                if event.input_transcription and event.input_transcription.text:
                    logger.info(
                        "[USER]  %s%s",
                        event.input_transcription.text,
                        "" if event.input_transcription.finished else " ...",
                    )
                if event.output_transcription and event.output_transcription.text:
                    logger.info(
                        "[AGENT] %s%s",
                        event.output_transcription.text,
                        "" if event.output_transcription.finished else " ...",
                    )

                # ── Barge-in: user interrupted the agent mid-response ─────────
                # The ADK / Gemini VAD detected the caller started speaking.
                # Tell Twilio to throw away all buffered audio immediately.
                if event.interrupted:
                    logger.info("Agent interrupted by user – sending Twilio clear")
                    # Twilio discards its queued playback on 'clear', so the
                    # resampler's filter tail is stale — drop it too.
                    outbound_resampler.reset()
                    if stream_sid:
                        await websocket.send_json(
                            {"event": "clear", "streamSid": stream_sid}
                        )
                    continue  # No audio to forward for this event

                if event.turn_complete:
                    logger.info("Agent turn complete")
                    # turn_complete events carry no audio; nothing to forward.
                    continue

                # ── Forward audio parts to Twilio ─────────────────────────────
                if not (event.content and event.content.parts):
                    continue

                for part in event.content.parts:
                    if not (
                        part.inline_data
                        and part.inline_data.mime_type
                        and part.inline_data.mime_type.startswith("audio/pcm")
                        and part.inline_data.data
                    ):
                        continue

                    pcm_24k: bytes = part.inline_data.data

                    # 1. Resample 24 000 Hz → 8 000 Hz (required by Twilio),
                    #    stateful so consecutive chunks join seamlessly
                    pcm_8k = outbound_resampler.process(pcm_24k)
                    if not pcm_8k:
                        continue

                    # 2. 16-bit PCM → μ-law
                    ulaw_data: bytes = audioop.lin2ulaw(pcm_8k, 2)

                    # 3. Base64-encode and send to Twilio. Per Twilio's spec the
                    #    outbound media payload may be any size, so we forward
                    #    each resampled burst directly (no re-framing needed).
                    if stream_sid:
                        await websocket.send_json(
                            {
                                "event": "media",
                                "streamSid": stream_sid,
                                "media": {
                                    "payload": base64.b64encode(ulaw_data).decode()
                                },
                            }
                        )

        except WebSocketDisconnect:
            logger.info("Twilio WebSocket disconnected (downstream)")
        except Exception as e:
            # Don't log normal WebSocket closures (code 1000) as errors
            # This happens when the call ends normally
            error_msg = str(e)
            if "1000" in error_msg and "None" in error_msg:
                logger.info("ADK WebSocket closed normally (call ended)")
            else:
                logger.exception("Unexpected error in downstream_task")

    # ── Run both directions concurrently ──────────────────────────────────────────
    try:
        await asyncio.gather(
            upstream_task(),
            downstream_task(),
            return_exceptions=True,
        )
    finally:
        # Phase 4: Guarantee cleanup regardless of which task finished first
        live_request_queue.close()
        logger.info("Session %s terminated", session_id)


# ---------------------------------------------------------------------------
# Entry point  (python -m audiocall.main)
# ---------------------------------------------------------------------------
def main() -> None:
    import uvicorn

    uvicorn.run(
        "audiocall.main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
        reload=bool(os.environ.get("DEV_RELOAD", "")),
        log_level="info",
    )


if __name__ == "__main__":
    main()
