"""
LLM Wrapper — bridges livekit-agents v1.x LLM interface to the LangGraph agent.

In livekit-agents v1.x, the Agent class handles conversation turns via its
`on_message` callback. This file provides a standalone `LangGraphLLM` class
that can be used as the `llm` parameter to pass to the agent's TTS pipeline,
or used directly via `AgentSession`.

For v1.4.5, we use the simpler pattern: the Agent subclass directly calls
the LangGraph process_user_input in its _do_reply implementation.
This module provides the echo detection utilities shared by the agent.
"""

import logging
import re
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


def is_echo(user_text: str, recent_responses: list[str]) -> bool:
    """Return True if user_text closely mirrors a recent agent response (echo detected)."""
    lower = user_text.lower().strip()
    if not lower or len(lower) < 3:
        return False

    for resp in recent_responses:
        resp_lower = resp.lower().strip()
        if not resp_lower:
            continue
        # Direct equality
        if lower == resp_lower:
            logger.warning("Echo detected (exact match): '%s'", user_text[:60])
            return True
        # Substring
        if len(lower) > 5 and (lower in resp_lower or resp_lower in lower):
            logger.warning("Echo detected (substring): '%s'", user_text[:60])
            return True
        # High similarity
        similarity = SequenceMatcher(None, lower, resp_lower).ratio()
        if similarity > 0.8:
            logger.warning("Echo detected (similarity %.2f): '%s'", similarity, user_text[:60])
            return True

    # Regex patterns for paraphrased echoes
    echo_patterns = [
        r"you said (.+)",
        r"you'?re saying (.+)",
        r"you mentioned (.+)",
    ]
    for pattern in echo_patterns:
        match = re.search(pattern, lower)
        if match:
            echoed = match.group(1).strip()
            for resp in recent_responses:
                resp_lower = resp.lower().strip()
                if echoed in resp_lower or resp_lower in echoed:
                    logger.warning("Echo detected (pattern): '%s'", user_text[:60])
                    return True
    return False


def is_context_mismatch(user_text: str, recent_responses: list[str]) -> bool:
    """Return True when the user's reply cannot possibly match the pending question."""
    if not recent_responses:
        return False

    lower = user_text.lower().strip()
    last_resp_lower = recent_responses[-1].lower()

    # Only suppress CLEARLY unrelated inputs for the age question.
    # IMPORTANT: "yes", "no", "yeah", "sure" ARE valid answers to "Are you 18 or older?"
    # so we must NOT classify them as mismatches.
    age_kws = ["age", " old", "years"]
    # Only suppress inputs that are clearly about a different topic (meal plan, food, exercise)
    # and do NOT contain any digit (which could be an actual age number)
    non_age = ["meal", "plan", "diet", "food", "exercise", "workout"]
    if any(kw in last_resp_lower for kw in age_kws):
        if any(na in lower for na in non_age) and not any(str(d) in lower for d in range(10)):
            logger.warning("Context mismatch (age question): '%s'", user_text[:60])
            return True
    return False

from livekit.agents import llm
from livekit.agents.types import DEFAULT_API_CONNECT_OPTIONS, NOT_GIVEN, NotGivenOr
import uuid

class GraphLLM(llm.LLM):
    """
    LLM wrapper that delegates to BugzyAgent's graph.
    This allows the AgentSession to use our LangGraph agent as its 'intelligence'.
    """
    def __init__(self, agent):
        super().__init__()
        self.agent = agent
        self._label = "custom-graph-agent"

    def chat(
        self,
        *,
        chat_ctx: llm.ChatContext,
        tools: list | None = None,
        conn_options=None,
        parallel_tool_calls: NotGivenOr[bool] = NOT_GIVEN,
        tool_choice: NotGivenOr = NOT_GIVEN,
        extra_kwargs: NotGivenOr[dict] = NOT_GIVEN,
    ) -> "GraphLLMStream":
        """Match livekit-agents LLM.chat() signature — accept tools, tool_choice, etc."""
        if conn_options is None:
            conn_options = DEFAULT_API_CONNECT_OPTIONS
        msgs = chat_ctx.messages() if callable(getattr(chat_ctx, "messages", None)) else getattr(chat_ctx, "messages", [])
        logger.info("GraphLLM.chat() called with %d messages", len(msgs))
        return GraphLLMStream(self, self.agent, chat_ctx, tools or [], conn_options)


class GraphLLMStream(llm.LLMStream):
    def __init__(self, llm_opts: llm.LLM, agent, chat_ctx: llm.ChatContext, tools: list, conn_options):
        super().__init__(
            llm=llm_opts,
            chat_ctx=chat_ctx,
            tools=tools,
            conn_options=conn_options,
        )
        self.agent = agent
        self.recent_agent_responses: list[str] = []
        self.max_recent_responses = 3
        _msgs = chat_ctx.messages() if callable(getattr(chat_ctx, "messages", None)) else getattr(chat_ctx, "messages", [])
        logger.info("GraphLLMStream initialized with %d messages", len(_msgs))

    async def _run(self) -> None:
        logger.info("🟢 GraphLLMStream._run() STARTED")
        try:
            chat_ctx = self._chat_ctx
            msgs = chat_ctx.messages() if callable(getattr(chat_ctx, "messages", None)) else getattr(chat_ctx, "messages", [])
            if not msgs:
                return

            last_msg = msgs[-1]
            if last_msg.role != "user":
                return

            user_text = getattr(last_msg, "text_content", None) or str(getattr(last_msg, "content", ""))
            if isinstance(user_text, list):
                user_text = " ".join([str(c) for c in user_text])
            if not isinstance(user_text, str):
                user_text = str(user_text)
            
            user_text = user_text.strip()
            if not user_text:
                return
            
            # Use echo cancellation from this module
            if is_echo(user_text, self.recent_agent_responses):
                return
            if is_context_mismatch(user_text, self.recent_agent_responses):
                return

            # Skip if on_user_turn_completed already processed this message (avoids double response + double speak)
            if (
                getattr(self.agent, "_last_turn_user_msg", "") == user_text
                and getattr(self.agent, "_last_turn_response", "")
            ):
                logger.info("GraphLLM: skipping (already spoken in on_user_turn) — no chunk")
                return
            else:
                logger.info(f"🎤 Processing user input via Graph: '{user_text}'")
                response_text = await self.agent.process_user_input(user_text)
            
            logger.info(f"💬 Graph response: '{response_text}'")
            
            if "<<END_CALL>>" in response_text:
                logger.info("🛑 <<END_CALL>> signal detected in response!")
                self.agent.should_terminate = True
                response_text = response_text.replace("<<END_CALL>>", "").strip()

            if not response_text or not response_text.strip():
                response_text = "I'm sorry, I didn't catch that. Could you repeat?"
            
            response_text_clean = response_text.strip()
            if response_text_clean:
                self.recent_agent_responses.append(response_text_clean)
                if len(self.recent_agent_responses) > self.max_recent_responses:
                    self.recent_agent_responses.pop(0)

            chunk = llm.ChatChunk(
                id=str(uuid.uuid4()),
                delta=llm.ChoiceDelta(content=response_text, role="assistant"),
            )
            self._event_ch.send_nowait(chunk)

        except Exception as e:
            logger.error("Error in GraphLLMStream: %s", e, exc_info=True)
            chunk = llm.ChatChunk(
                id=str(uuid.uuid4()),
                delta=llm.ChoiceDelta(
                    content="I'm sorry, I encountered an error processing that.",
                    role="assistant",
                ),
            )
            self._event_ch.send_nowait(chunk)
