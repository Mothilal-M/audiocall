"""Google ADK agent definition for the Twilio voice agent."""

import contextlib
import os
from typing import AsyncIterator

from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from google.adk.models.llm_request import LlmRequest
from google.genai import types

# Use environment variable with a sensible default.
# - Gemini Live API (public):  gemini-2.5-flash-native-audio-preview-12-2025
# - Vertex AI Live API:        gemini-live-2.5-flash-native-audio
_MODEL = os.getenv("AGENT_MODEL", "gemini-2.5-flash-native-audio-preview-12-2025")


class GeminiNoThinking(Gemini):
    """Gemini subclass that disables dynamic thinking before each Live connection.

    The native-audio preview model has Dynamic Thinking enabled by default,
    which adds ~2-3 seconds of pre-response latency.  Setting thinking_budget=0
    disables it without requiring any additional SDK support in RunConfig.
    """

    @contextlib.asynccontextmanager
    async def connect(self, llm_request: LlmRequest) -> AsyncIterator:  # type: ignore[override]
        llm_request.live_connect_config.thinking_config = types.ThinkingConfig(
            thinking_budget=0
        )
        async with super().connect(llm_request) as conn:
            yield conn


# Configure a clear, professional voice for phone calls.
# Native audio models support the full TTS voice library; "Puck" is a crisp,
# articulate voice well suited for phone conversations.
_llm = GeminiNoThinking(
    model=_MODEL,
    speech_config=types.SpeechConfig(
        voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                voice_name=os.getenv("AGENT_VOICE", "Puck")
            )
        )
    ),
)

root_agent = Agent(
    name="phone_assistant",
    model=_llm,
    description="A helpful voice assistant that answers phone calls via Twilio.",
    instruction=(
        "You are a professional and helpful voice assistant answering phone calls. "
        "Rules you must always follow:\n"
        "- Keep every response SHORT and to the point — 1 to 3 sentences maximum. "
        "People are on the phone and do not want to listen to long monologues.\n"
        "- Speak naturally, as if in a real phone conversation.\n"
        "- If the caller interrupts you or changes topic, immediately address "
        "their new question. Never finish an old answer after being interrupted.\n"
        "- When the call connects, greet the caller warmly in one sentence and "
        "ask how you can help.\n"
        "- If you do not know the answer, say so honestly and offer an alternative."
    ),
)
