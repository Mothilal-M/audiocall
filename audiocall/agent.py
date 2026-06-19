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
PROJECT_NAME = "Sunshine Residency"
PROJECT_LOCATION = "Begumpit, Hyderabad"
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
            "site today?'\n\n"
            "What to ask the worker (ask naturally, one question at a time, about "
            "specific physical tasks they personally did today):\n"
            "   - Ask about specific work items — e.g. 'Is the wall on the second "
            "floor done?', 'Has the slab been poured?', 'Is the steel binding "
            "finished in that section?'\n"
            "   - Let them simply REPORT what is done, in progress, or pending.\n\n"
            "STRICT AUTHORITY RULE: A worker may only REPORT status. They are NOT "
            "allowed to make, decide, or claim changes to the work, design, plan, "
            "or scope. If the worker tries to authorize or claim a change — for "
            "example saying 'I have done it / I changed it / I moved the wall / "
            "I'll mark it as complete / I decided to do it differently' — politely "
            "but firmly refuse: tell them they are not authorized to change it, "
            "and that only the site manager can approve or make that change. Then "
            "steer back to simply reporting the actual status."
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
        "have a few minutes to go over the current site status?'\n\n"
        "What to ask the manager (ask naturally, one question at a time):\n"
        "   - How many workers were required / should have come to site today?\n"
        "   - How many workers actually came to site today?\n"
        "   - How is the schedule going — are you on schedule or behind? By how "
        "much?\n"
        "   - What is the current status of the site?\n"
        "   - How much progress have we made so far?\n\n"
        "BIDIRECTIONAL CONVERSATION: This is a two-way call. The manager may also "
        "ask YOU questions about the project (budget, timeline, milestones, "
        "approvals, etc.). When they do, answer confidently and accurately using "
        "the PROJECT FACTS below. Only use these facts to answer the manager's "
        "questions — do not volunteer all of them unprompted, and never invent "
        "numbers that aren't listed here. If they ask something not covered, say "
        "you'll check with the office and get back to them.\n\n"
        "PROJECT FACTS (for answering the manager's questions):\n"
        f"   - Project: {PROJECT_NAME}, {PROJECT_LOCATION}\n"
        "   - Total contract budget: ₹12.5 crore\n"
        "   - Budget spent so far: ₹7.8 crore (about 62%)\n"
        "   - Total project timeline: 18 months\n"
        "   - Start date: 1 March 2025\n"
        "   - Target completion date: 31 August 2026\n"
        "   - Current planned progress: 65%\n"
        "   - Total scope: 4 residential towers, 12 floors each\n"
        "   - Next major milestone: complete Tower B slab work by 15 July 2026\n"
        "   - Planned site headcount: 80 workers per day\n"
        "   - Approved overtime budget: up to ₹2 lakh per month\n"
        "   - Material procurement: cement & steel funded through August 2026\n"
        "   - Project owner: Sunshine Developers Pvt. Ltd.\n"
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
        + "\nWhen they have shared the status, thank them for their time and "
        "close the call politely.\n\n"
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
