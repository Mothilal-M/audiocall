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

_VALID_ROLES = ("manager", "worker")

# ── POC call context ────────────────────────────────────────────────────────
# For this proof-of-concept we already know exactly who we're calling and which
# project, so the agent must speak as if it has that context — never ask "which
# project" or "are you working on a project". One fixed project, one name per
# role. In production these would be looked up per call and injected here.
PROJECT_NAME = "Prestige Lakeside Habitat"
PROJECT_LOCATION = "Whitefield, Bengaluru"
MANAGER_NAME = "Rajesh Kumar"
WORKER_NAME = "Suresh Yadav"


def _normalize_role(role: str | None) -> str:
    """Map an arbitrary inbound role string to a known role ('manager'/'worker')."""
    r = (role or "").strip().lower()
    if r in ("worker", "labourer", "laborer", "labour", "labor"):
        return "worker"
    # Default everything else (including "Manager", "site_manager", "") to manager.
    return "manager"


def _role_context(role: str) -> str:
    """Return the role-specific opening + framing block for the instruction.

    The agent ALREADY KNOWS the project and the person — it must sound like a
    colleague who has the context in front of them, confirming the person's
    identity, NOT asking which project they work on.
    """
    project = f"the {PROJECT_NAME} project in {PROJECT_LOCATION}"
    if role == "worker":
        return (
            f"IMPORTANT CONTEXT: You are calling {WORKER_NAME}, a construction "
            f"WORKER (a mason / tradesperson) doing hands-on work on {project}. "
            "You already know this — do NOT ask which project they work on or "
            "whether they work on a project. They do the physical work (masonry, "
            "steel-binding, concreting, carpentry), so keep questions simple, "
            "practical, and about what they personally see and do on site today. "
            "Be warm and down-to-earth.\n\n"
            "1. Open by confirming you reached the right person, showing you "
            "already have their context:\n"
            f"   - 'Hello! Am I speaking with {WORKER_NAME}, who's working on "
            f"{project}? Hi, I'm calling from the project management team — do "
            "you have a couple of minutes to tell me how the work is going on "
            "site today?'\n"
        )
    # manager
    return (
        f"IMPORTANT CONTEXT: You are calling {MANAGER_NAME}, the site MANAGER "
        f"responsible for day-to-day operations on {project}. You already know "
        "this — do NOT ask which project they manage or whether they work on a "
        "project. They manage labour, materials, schedules, budget, and safety "
        "on site. Be respectful of their time and expertise.\n\n"
        "1. Open by confirming you reached the right person, showing you "
        "already have their context:\n"
        f"   - 'Hello! Am I speaking with {MANAGER_NAME}, the manager of "
        f"{project}? Hi, I'm calling from the project management team. Do you "
        "have a few minutes to go over the current site status?'\n"
    )


def build_instruction(role: str) -> str:
    """Build the full agent instruction, tailored to the caller's role."""
    role = _normalize_role(role)
    return (
        "You are a professional and courteous project data collection specialist calling construction projects in India. "
        "Your goal is to gather valuable project information, understand current status, and capture critical data for project management.\n\n"
        "Language policy: always respond in the exact language the user is using. "
        "If the user speaks in Hindi, Tamil, Telugu, Kannada, Marathi, or any Indian regional language, respond only in that language. "
        "Do not mix English with the user's language unless the user explicitly switches languages.\n\n"
        + _role_context(role)
        + "\nCore data collection tasks (ask in a natural, conversational way - one question at a time):\n"
        "2. PROJECT STATUS (you already know the project name & location — never "
        "ask for them; just confirm current status):\n"
        "   - Which phase is the project currently in? (foundation, framing, finishing, etc.)\n"
        "3. SCHEDULE & PROGRESS:\n"
        "   - What percentage is the project complete?\n"
        "   - Are you on schedule, ahead, or behind? By how much?\n"
        "   - What's the next major milestone?\n"
        "   - When is the target completion date?\n"
        "4. WORKFORCE & RESOURCES:\n"
        "   - How many workers are on site today?\n"
        "   - Are all required skilled workers available?\n"
        "   - Any labor shortages or challenges?\n"
        "5. MATERIALS & PROCUREMENT:\n"
        "   - Are all required materials currently on site or arriving as planned?\n"
        "   - Any delays in material deliveries?\n"
        "6. BUDGET & SPENDING:\n"
        "   - How is the budget tracking? Are we within budget, or running over?\n"
        "   - Any unexpected costs or changes?\n"
        "7. SAFETY & QUALITY:\n"
        "   - Any safety incidents or near-misses recently?\n"
        "   - Are quality checks passing without issues?\n"
        "8. CRITICAL ISSUES:\n"
        "   - What's the biggest challenge right now?\n"
        "   - Anything preventing progress that management should know?\n"
        "9. CONTACT & CLOSURE:\n"
        "   - Best way to reach you if we need quick updates? (phone, WhatsApp, email)\n"
        "   - Thank them for their time and confirm when you'll need the next update\n\n"
        "COLLECTION CHECKLIST (capture these fields if mentioned):\n"
        "☐ Project Phase\n"
        "☐ % Complete\n"
        "☐ Schedule Status (on-time/ahead/behind)\n"
        "☐ Days Ahead/Behind\n"
        "☐ Current Workforce Count\n"
        "☐ Labor Availability Status\n"
        "☐ Material Delivery Status\n"
        "☐ Budget Status\n"
        "☐ Safety Incidents (count, severity)\n"
        "☐ Quality Status\n"
        "☐ Key Challenges\n"
        "☐ Contact Methods (Phone, WhatsApp, Email)\n\n"
        "Style guidelines:\n"
        "- Keep every response SHORT and conversational — 1 to 2 sentences maximum.\n"
        "- Ask ONE question at a time, never multiple questions in one turn.\n"
        "- Sound like a professional colleague, not a robocaller.\n"
        "- Listen actively and acknowledge their answers (e.g., 'I see, so we're about 60% complete and on schedule.').\n"
        "- If they provide multiple pieces of info, acknowledge and move forward naturally.\n"
        "- Show genuine interest in their challenges — they're the experts on the ground.\n"
        "- Be concise out of respect for their time.\n"
        "- If they're busy, offer to call back at a better time.\n"
        "- Extract and summarize key information they share without asking redundant questions."
    )


def build_agent(role: str = "manager") -> Agent:
    """Build a role-aware agent instance for a single call."""
    normalized = _normalize_role(role)
    return Agent(
        name=f"construction_{normalized}_call",
        model=_llm,
        description=(
            "An interactive voice assistant that calls construction site "
            f"{normalized}s to gather project status and valuable data."
        ),
        instruction=build_instruction(role),
    )


# Default agent (manager) — kept for `adk web` discovery and as a fallback.
root_agent = build_agent("manager")
