"""
Bugzy Voice Agent — LiveKit Worker Entry Point (livekit-agents v1.4.5).

Architecture in v1.4.5:
  - Agent subclass  →  handles turn-by-turn conversation
  - AgentSession    →  manages STT / LLM / TTS pipeline
  - WorkerOptions + cli.run_app  → registers with LiveKit Cloud

Entry point: `python3 app/services/voice/livekit_agent.py start`
"""

import asyncio
import logging
import os
import sys
from typing import Optional

import aiohttp
from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentSession,
    AutoSubscribe,
    JobContext,
    JobExecutorType,
    WorkerOptions,
    cli,
)
from livekit.plugins import deepgram, google, silero

from app.services.voice.audio_config import (
    DEEPGRAM_STT_CONFIG,
    GOOGLE_TTS_CONFIG,
    NODE_BACKEND_PORT,
    SILERO_VAD_CONFIG,
)
from app.services.voice.llm_wrapper import GraphLLM, is_context_mismatch, is_echo

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# ─── Pre-load VAD ─────────────────────────────────────────────────────────────

_PRELOADED_VAD: Optional[silero.VAD] = None


def _get_vad() -> silero.VAD:
    global _PRELOADED_VAD
    if _PRELOADED_VAD is None:
        logger.info("Loading Silero VAD…")
        _PRELOADED_VAD = silero.VAD.load(
            min_speech_duration=SILERO_VAD_CONFIG["min_speech_duration"],
            min_silence_duration=SILERO_VAD_CONFIG["min_silence_duration"],
        )
    return _PRELOADED_VAD


# ─── LangGraph product helpers ────────────────────────────────────────────────

def _detect_product(phone_number: Optional[str]):
    """Return (product_enum, crm_user, crm_order) from CRM lookup."""
    from app.config.product_registry import BugzyProduct

    product_type = BugzyProduct.FREE_FORM
    user_details = None
    order_details = None

    if not phone_number:
        return product_type, user_details, order_details

    try:
        from app.services.crm.sessions import fetch_user_details, fetch_order_details, extract_order_details
        user_details = fetch_user_details(phone_number)
        if "error" not in user_details and "message" not in user_details:
            order_details = fetch_order_details(phone_number)
            if "error" not in order_details:
                info = extract_order_details(order_details)
                order_name = info.get("latest_order_name")
                if order_name:
                    from app.config.product_registry import detect_product_from_order
                    product_type = detect_product_from_order(order_name)
    except Exception as exc:
        logger.warning("CRM lookup failed (%s): %s — defaulting to FREE_FORM", phone_number, exc)

    return product_type, user_details, order_details


def _load_graph(product_type):
    """Return the compiled LangGraph for the given product."""
    from app.config.product_registry import BugzyProduct
    if product_type == BugzyProduct.AMS:
        from app.services.chatbot.bugzy_ams.agent import graph
        return graph
    elif product_type == BugzyProduct.GUT_CLEANSE:
        from app.services.chatbot.bugzy_gut_cleanse.agent import graph
        return graph
    else:
        from app.services.chatbot.bugzy_free_form.agent import graph
        return graph


def _normalize_phone_for_session(phone: str) -> list[str]:
    """Return phone variants to try for session lookup (chat may use different format)."""
    if not phone or not phone.strip():
        return []
    digits = "".join(c for c in phone if c.isdigit())
    if not digits:
        return [phone]
    variants = [phone, digits]
    if digits.startswith("91") and len(digits) == 12:
        variants.append(digits[2:])  # Without country code
    elif len(digits) == 10 and digits.isdigit():
        variants.append("91" + digits)  # With India code
    return variants


def _gut_append_voice_age_seed_if_absent(state: dict, intro: str, question: str) -> None:
    """Avoid stacking duplicate 18+ pre-seeds when reconnecting or reloading session."""
    from app.services.chatbot.bugzy_gut_cleanse.voice_message_utils import (
        gut_should_append_age_seed,
    )

    full = f"{intro}{question}".strip()
    msgs = state.get("messages") or []
    if not gut_should_append_age_seed(msgs, question):
        logger.info("Gut voice: skip duplicate age pre-seed (already in messages)")
        return
    state.setdefault("messages", []).append({"role": "assistant", "content": full})


def _build_initial_state(product_type, phone_number: Optional[str], user_details, order_details) -> dict:
    import re
    from app.services.crm.sessions import load_user_session
    from app.config.product_registry import BugzyProduct

    existing = None
    if phone_number:
        for variant in _normalize_phone_for_session(phone_number):
            existing = load_user_session(variant)
            if existing:
                if variant != phone_number:
                    logger.info("Session loaded with phone variant %s (original %s)", variant, phone_number)
                break

    if existing:
        logger.info("Resuming session for %s — last_question=%s voice_context=%s", phone_number, existing.get("last_question"), existing.get("voice_agent_context"))
        state = existing
        lq = state.get("last_question")
        if state.get("voice_agent_context") == "meal_planning" and lq not in ("voice_agent_promotion_meal", "voice_agent_promotion_exercise", "ask_meal_plan_preference") and not lq:
            state["last_question"] = "voice_agent_promotion_meal"
            logger.info("Set last_question=voice_agent_promotion_meal for voice meal journey (was %s)", lq)
        # Flexible journey: ensure agent speaks the right content when joining
        product = state.get("product", "ams")
        if lq in ("voice_agent_promotion_meal", "voice_agent_promotion_exercise"):
            # User tapped call from promotion screen — speak first question immediately
            if state.get("voice_agent_context") == "meal_planning":
                if product == "ams":
                    from app.services.chatbot.bugzy_ams.voice_questions import VOICE_QUESTIONS
                    intro = "Perfect! Before we design your meal plan, let me learn a bit about you. "
                    q = VOICE_QUESTIONS.get("age", "What's your age?")
                    state.setdefault("messages", []).append({"role": "assistant", "content": intro + q})
                    state["pending_node"] = "collect_age"
                elif product == "gut_cleanse":
                    from app.services.chatbot.bugzy_gut_cleanse.voice_questions import VOICE_QUESTIONS
                    intro = "Perfect! Before we design your meal plan, let me learn a bit about you. "
                    q = VOICE_QUESTIONS.get("age_eligibility", "Are you 18 years or older?")
                    _gut_append_voice_age_seed_if_absent(state, intro, q)
                    state["pending_node"] = "collect_age_eligibility"
            else:
                from app.services.chatbot.resume_questions import get_question_for_resume
                q = get_question_for_resume(product, "fitness_level")
                if q:
                    state.setdefault("messages", []).append({"role": "assistant", "content": q})
        elif lq and lq not in ("ask_meal_plan_preference",):
            from app.services.chatbot.resume_questions import get_question_for_resume

            def _resume_question() -> str | None:
                """Speak the NEXT question when current field is already collected."""
                if product == "ams":
                    from app.services.chatbot.bugzy_ams.voice_questions import VOICE_QUESTIONS
                    if lq == "age" and (state.get("age") or "").strip() and re.search(r"\d", str(state.get("age", ""))):
                        return VOICE_QUESTIONS.get("height")
                    if lq == "height" and (state.get("height") or "").strip() and re.search(r"\d", str(state.get("height", ""))):
                        return VOICE_QUESTIONS.get("weight")
                    if lq == "weight" and (state.get("weight") or "").strip() and re.search(r"\d", str(state.get("weight", ""))):
                        return VOICE_QUESTIONS.get("diet_preference")
                return get_question_for_resume(product, lq)

            q = _resume_question()
            if q:
                state.setdefault("messages", []).append({"role": "assistant", "content": q})
    else:
        logger.info("New session for %s", phone_number)
        product_map = {BugzyProduct.AMS: "ams", BugzyProduct.GUT_CLEANSE: "gut_cleanse"}
        product = product_map.get(product_type, "free_form")
        state = {
            "user_id": phone_number or "unknown",
            "phone_number": phone_number,
            "conversation_history": [],
            "journey_history": [],
            "full_chat_history": [],
            "messages": [],
            "current_agent": "meal" if product in ("ams", "gut_cleanse") else None,
            "product": product,
        }
        # Voice call for meal plan: append first question so agent speaks immediately
        # (avoids slow graph.ainvoke which causes LiveKit process init timeout)
        if product == "ams":
            state["voice_agent_context"] = "meal_planning"
            state["last_question"] = "voice_agent_promotion_meal"
            state["wants_meal_plan"] = True
            state["pending_node"] = "collect_age"
            from app.services.chatbot.bugzy_ams.voice_questions import VOICE_QUESTIONS
            intro = "Perfect! Before we design your meal plan, let me learn a bit about you. "
            q = VOICE_QUESTIONS.get("age", "What's your age?")
            state["messages"] = [{"role": "assistant", "content": intro + q}]
        elif product == "gut_cleanse":
            state["voice_agent_context"] = "meal_planning"
            state["last_question"] = "voice_agent_promotion_meal"
            state["wants_meal_plan"] = True
            state["pending_node"] = "collect_age_eligibility"
            from app.services.chatbot.bugzy_gut_cleanse.voice_questions import VOICE_QUESTIONS
            intro = "Perfect! Before we design your meal plan, let me learn a bit about you. "
            q = VOICE_QUESTIONS.get("age_eligibility", "Are you 18 years or older?")
            state["messages"] = [{"role": "assistant", "content": intro + q}]
        else:
            state["messages"] = [{"role": "assistant", "content": "Hello! I'm Bugzy, your personal health coach. How can I help you today?"}]

    state["interaction_mode"] = "voice"
    state["voice_call_active"] = True

    if user_details:
        state["_crm_user_details"] = user_details
    if order_details:
        state["_crm_order_details"] = order_details

    return state


# ─── Bugzy Agent (v1.4.5 style) ────────────────────────────────────────────────


class BugzyAgent(Agent):
    """
    Bugzy voice agent: each conversation turn calls the LangGraph graph.

    Lifecycle:
      1. __init__: lightweight — no blocking I/O (subprocess IPC would time out)
      2. initialize(): called from entrypoint after participant joins — CRM + graph.invoke
      3. on_user_turn_completed: each STT result → graph.ainvoke → TTS
    """

    def __init__(self, phone_number: Optional[str]) -> None:
        super().__init__(
            instructions=(
                "You are Bugzy, a friendly health coach helping users with meal plans and fitness. "
                "Listen carefully and respond naturally."
            ),
        )
        self.phone_number = phone_number
        self.should_terminate = False
        self._recent_responses: list[str] = []
        self._last_turn_user_msg: str = ""
        self._last_turn_response: str = ""
        # Heavy attributes set later by initialize()
        self.product_type = None
        self.graph = None
        self.state = {}

    async def initialize(self) -> None:
        """Lightweight init: CRM + state only. No graph run — avoids LiveKit process init timeout."""
        loop = asyncio.get_event_loop()
        product_type, user_details, order_details = await loop.run_in_executor(
            None, _detect_product, self.phone_number
        )
        self.product_type = product_type
        self.graph = _load_graph(product_type)
        self.state = _build_initial_state(product_type, self.phone_number, user_details, order_details)

        # Ensure we have something to speak (fallback if messages empty)
        if not any(
            isinstance(m, dict) and m.get("role") == "assistant" and (m.get("content") or "").strip()
            for m in self.state.get("messages", [])
        ):
            self.state.setdefault("messages", []).append({
                "role": "assistant",
                "content": "Hello! I'm Bugzy, your personal health coach. How can I help you today?",
            })
        mc = len(self.state.get("messages") or [])
        logger.info(
            "Voice init done — user=%s last_question=%s messages=%d",
            self.phone_number,
            self.state.get("last_question"),
            mc,
        )

    # ─── Helpers ──────────────────────────────────────────────────────────────

    def _get_last_assistant_text(self) -> str:
        """Last assistant line for TTS — supports dict messages and LangChain AI messages."""
        from app.services.chatbot.bugzy_gut_cleanse.voice_message_utils import gut_last_assistant_content

        t = gut_last_assistant_content(list(self.state.get("messages", [])))
        if t:
            return t
        return "Hello! I'm Bugzy, your personal health coach. How can I help you today?"

    def _store_response(self, text: str) -> None:
        self._recent_responses.append(text.strip())
        if len(self._recent_responses) > 3:
            self._recent_responses.pop(0)

    async def _save_state(self) -> None:
        try:
            from app.services.crm.sessions import save_session_to_file
            uid = self.state.get("user_id") or self.phone_number
            if uid:
                save_session_to_file(uid, self.state)
        except Exception as exc:
            logger.error("Failed to save session: %s", exc)

    async def process_user_input(self, user_text: str) -> str:
        """Used by GraphLLM when framework invokes LLM path; invokes graph and returns response text."""
        self.state["user_input"] = user_text
        self.state["user_msg"] = user_text
        result = await self.graph.ainvoke(self.state)
        self.state["user_input"] = ""
        self.state["user_msg"] = ""
        if isinstance(result, dict):
            self.state.update(result)
        out = self._get_last_assistant_text()
        # Keep cache in sync so on_user_turn_completed can skip duplicate graph+say.
        self._last_turn_user_msg = user_text.strip()
        self._last_turn_response = out.strip() if out else ""
        if self._last_turn_response:
            self._store_response(self._last_turn_response)
        return out

    # ─── v1.4.5 Agent lifecycle callbacks ─────────────────────────────────────

    async def on_enter(self) -> None:
        """Called when the agent joins the room. Speak the initial greeting here."""
        logger.info("Agent joined the room.")
        greeting = self._get_last_assistant_text()
        self._store_response(greeting)
        logger.info("Speaking greeting (user=%s, len=%d): %s", self.phone_number, len(greeting), greeting[:160])
        try:
            await self.session.say(greeting, allow_interruptions=True)
        except Exception as e:
            logger.error("Failed to speak initial greeting: %s", e)

    async def on_user_turn_completed(self, turn_ctx, new_message) -> None:
        """
        Called after each user speech turn. We override the default LLM
        and call the LangGraph graph directly.
        """
        user_text = new_message.text_content if hasattr(new_message, "text_content") else str(new_message)
        user_text = user_text.strip()

        if not user_text:
            return

        # GraphLLM may already have run ainvoke+TTS for this utterance — avoid second graph + duplicate speak.
        if user_text == self._last_turn_user_msg and self._last_turn_response:
            logger.info("on_user_turn: skip duplicate (already processed via GraphLLM): %s…", user_text[:60])
            return

        # Echo / mismatch detection
        if is_echo(user_text, self._recent_responses):
            logger.info("Echo suppressed: '%s'", user_text[:60])
            return
        if is_context_mismatch(user_text, self._recent_responses):
            logger.info("Context mismatch suppressed: '%s'", user_text[:60])
            return

        logger.info("User: '%s'", user_text[:100])

        try:
            # Drive the LangGraph
            self.state["user_input"] = user_text
            self.state["user_msg"] = user_text
            result = await self.graph.ainvoke(self.state)
            self.state["user_input"] = ""
            self.state["user_msg"] = ""
            # Merge result so we don't lose keys (graph may return partial state)
            if isinstance(result, dict):
                self.state.update(result)

            response_text = self._get_last_assistant_text()

            # END_CALL signal
            if "<<END_CALL>>" in response_text:
                logger.info("<<END_CALL>> detected")
                self.should_terminate = True
                response_text = response_text.replace("<<END_CALL>>", "").strip()

            if not response_text:
                response_text = "I'm sorry, I didn't catch that. Could you repeat?"

            self._store_response(response_text)
            logger.info("Agent: '%s'…", response_text[:80])

            # Cache so GraphLLM skip avoids double processing (on_user_turn + LLM both run)
            self._last_turn_user_msg = user_text
            self._last_turn_response = response_text

            await self.session.say(response_text, allow_interruptions=True)
            asyncio.create_task(self._save_state())

            # Trigger termination after speaking if needed
            if self.should_terminate:
                asyncio.create_task(self._end_call_after_delay(10))

        except Exception as exc:
            logger.error("Error processing turn: %s", exc, exc_info=True)
            await self.session.say("I'm having trouble with that. Could you try again?")

    async def _end_call_after_delay(self, delay: float) -> None:
        await asyncio.sleep(delay)
        await _send_plan_to_node(self.state, self.phone_number)
        await _terminate_call_on_node(self.phone_number)


# ─── Plan delivery helpers ─────────────────────────────────────────────────────

async def _send_plan_to_node(state: dict, phone_number: Optional[str]) -> None:
    if not phone_number:
        return
    from app.services.whatsapp.client import _send_whatsapp_buttons

    base_url = f"http://localhost:{NODE_BACKEND_PORT}"
    review_prompt = "Would you like to make changes, or shall we continue to your full 7-day plan? 🌟"

    async with aiohttp.ClientSession() as http:
        if state.get("fresh_meal_plan"):
            payload: dict = {"phone_number": phone_number}
            days = state.get("meal_plan_days")
            plan = state.get("meal_plan")
            if days:
                payload["meal_plan_days"] = days
            elif plan:
                payload["meal_plan"] = plan
            if len(payload) > 1:
                try:
                    async with http.post(f"{base_url}/send-meal-plan", json=payload, timeout=aiohttp.ClientTimeout(total=15)) as r:
                        if r.status == 200:
                            logger.info("Meal plan sent successfully")
                            state["fresh_meal_plan"] = False
                            _send_whatsapp_buttons(
                                phone_number,
                                review_prompt,
                                [
                                    {"type": "reply", "reply": {"id": "make_changes_meal_day1", "title": "✏️ Make Changes"}},
                                    {"type": "reply", "reply": {"id": "continue_7day_meal", "title": "✅ 7-Day Plan"}},
                                ],
                            )
                except Exception as exc:
                    logger.error("Failed to send meal plan: %s", exc)

        if state.get("fresh_exercise_plan") and state.get("exercise_plan"):
            try:
                payload = {"phone_number": phone_number, "meal_plan": state["exercise_plan"]}
                async with http.post(f"{base_url}/send-meal-plan", json=payload, timeout=aiohttp.ClientTimeout(total=15)) as r:
                    if r.status == 200:
                        state["fresh_exercise_plan"] = False
                        _send_whatsapp_buttons(
                            phone_number,
                            review_prompt,
                            [
                                {"type": "reply", "reply": {"id": "make_changes_exercise_day1", "title": "✏️ Make Changes"}},
                                {"type": "reply", "reply": {"id": "continue_7day_exercise", "title": "✅ 7-Day Plan"}},
                            ],
                        )
            except Exception as exc:
                logger.error("Failed to send exercise plan: %s", exc)


async def _terminate_call_on_node(phone_number: Optional[str]) -> None:
    if not phone_number:
        return
    try:
        async with aiohttp.ClientSession() as http:
            async with http.post(
                f"http://localhost:{NODE_BACKEND_PORT}/terminate-call",
                json={"phone_number": phone_number},
                timeout=aiohttp.ClientTimeout(total=5),
            ) as r:
                logger.info("terminate-call → %d", r.status)
    except Exception as exc:
        logger.error("terminate-call failed: %s", exc)


# ─── LiveKit entrypoint ───────────────────────────────────────────────────────

async def entrypoint(ctx: JobContext) -> None:
    """Called by LiveKit Worker for each incoming call."""
    logger.info("New job — room: %s", ctx.room.name if ctx.room else "None")
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    try:
        participant = await asyncio.wait_for(ctx.wait_for_participant(), timeout=30.0)
    except asyncio.TimeoutError:
        logger.error("Timeout waiting for participant — aborting")
        return

    phone_number = participant.identity or None
    logger.info("Caller: %s", phone_number)

    bugzy_agent = BugzyAgent(phone_number=phone_number)

    # Heavy init: CRM lookup + first graph invoke (async, after event loop is running)
    logger.info("Running agent initialize (CRM + graph)...")
    await bugzy_agent.initialize()
    logger.info("Agent initialization complete")

    # Build STT / TTS
    stt = deepgram.STT(
        model=DEEPGRAM_STT_CONFIG["model"],
        language=DEEPGRAM_STT_CONFIG["language"],
        smart_format=DEEPGRAM_STT_CONFIG.get("smart_format", True),
        punctuate=DEEPGRAM_STT_CONFIG.get("punctuate", True),
        interim_results=DEEPGRAM_STT_CONFIG.get("interim_results", True),
        endpointing_ms=DEEPGRAM_STT_CONFIG.get("endpointing", 300),
    )
    tts = google.TTS(
        language=GOOGLE_TTS_CONFIG["language"],
        voice_name=GOOGLE_TTS_CONFIG["voice_name"],
    )

    session = AgentSession(
        stt=stt,
        tts=tts,
        vad=_get_vad(),
        llm=GraphLLM(bugzy_agent),
    )

    async def _on_call_end(_reason=None) -> None:
        bugzy_agent.state["voice_call_active"] = False
        bugzy_agent.state["interaction_mode"] = "chat"
        await bugzy_agent._save_state()
        await _send_plan_to_node(bugzy_agent.state, phone_number)

    ctx.add_shutdown_callback(_on_call_end)

    # In livekit-agents 1.4.5, AgentSession.start() expects `agent` as the first arg
    # Greeting is spoken in BugzyAgent.on_enter() when the agent becomes active
    await session.start(bugzy_agent, room=ctx.room)
    logger.info("AgentSession started — listening for speech…")


# ─── Main / CLI ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Setup WhatsApp sender for the voice agent process
    from app.api.v1.api import _send_whatsapp_via_meta_sync, _send_whatsapp_via_meta_async
    from app.services.whatsapp.client import set_whatsapp_sender, set_whatsapp_sender_async
    set_whatsapp_sender(_send_whatsapp_via_meta_sync)
    set_whatsapp_sender_async(_send_whatsapp_via_meta_async)

    missing = [k for k in ("LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET") if not os.getenv(k)]
    if missing:
        logger.error("Missing env vars: %s", ", ".join(missing))
        sys.exit(1)

    # THREAD executor avoids process-pool init timeout (~10s) from heavy
    # LangGraph/CRM/MongoDB imports in child processes; jobs run in main process.
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            job_executor_type=JobExecutorType.THREAD,
        )
    )
