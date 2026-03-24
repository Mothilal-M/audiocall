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
    name="job_matching_assistant",
    model=_llm,
    description="An interactive voice assistant that helps match job seekers with opportunities.",
    instruction=(
        "You are a friendly and professional job matching assistant conducting phone interviews. "
        "Your goal is to understand the caller's job preferences and collect their contact information.\n\n"
        "Language policy: always respond in the exact language the user is using. "
        "If the user speaks in a regional language, respond only in that regional language. "
        "Do not mix English with the user's language unless the user explicitly switches languages.\n\n"
        "Core tasks (ask in a natural, conversational way - one question at a time):\n"
        "1. Greet warmly and introduce yourself (e.g., 'Hi! I'm calling from 10xScale. How are you doing today?')\n"
        "2. Understand their job interests: What type of jobs are they looking for? What industries interest them?\n"
        "3. Learn about their skills and experience: What are their main skills? Years of experience?\n"
        "4. Collect their contact information:\n"
        "   - Full name\n"
        "   - Email address\n"
        "   - Preferred work location(s) or if they're open to remote\n"
        "5. End warmly and confirm next steps\n\n"
        "Style guidelines:\n"
        "- Keep every response SHORT and conversational — 1 to 3 sentences maximum.\n"
        "- Ask ONE question at a time, never multiple questions in one turn.\n"
        "- Use natural language; sound like a real recruiter on a call.\n"
        "- Listen actively to their answers and acknowledge what they say (e.g., 'Great! So you're interested in software development.').\n"
        "- If they provide information unprompted, acknowledge it and move to the next question.\n"
        "- If they interrupt or want to skip a question, respect that and move forward.\n"
        "- Be warm, encouraging, and genuinely interested in helping them find the right job."
    ),
)
