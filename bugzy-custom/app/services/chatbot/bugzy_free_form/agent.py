"""
Bugzy Free Form Agent - Minimal graph (4 nodes).

Flow: verify_user → post_plan_qna; SNAP: transition_to_snap → snap_image_analysis → post_plan_qna.
No meal planner, no exercise planner.
"""

import logging
from langgraph.graph import StateGraph, END

from app.services.chatbot.bugzy_free_form.state import State
from app.services.crm.sessions import SESSIONS, load_user_session, save_session_to_file
from app.services.chatbot.bugzy_free_form.router import router
from app.services.chatbot.bugzy_free_form.nodes import (
    verify_user_node,
    transition_to_snap,
    snap_image_analysis,
    post_plan_qna_node,
)

logger = logging.getLogger(__name__)

workflow = StateGraph(State)

workflow.add_node("verify_user", verify_user_node)
workflow.add_node("post_plan_qna", post_plan_qna_node)
workflow.add_node("transition_to_snap", transition_to_snap)
workflow.add_node("snap_image_analysis", snap_image_analysis)

workflow.set_conditional_entry_point(
    router,
    {
        "verify_user": "verify_user",
        "post_plan_qna": "post_plan_qna",
        "transition_to_snap": "transition_to_snap",
        "snap_image_analysis": "snap_image_analysis",
    },
)

# After verify_user we stop; next message will route to post_plan_qna
workflow.add_edge("verify_user", END)
workflow.add_edge("post_plan_qna", END)
workflow.add_edge("transition_to_snap", END)
workflow.add_edge("snap_image_analysis", "post_plan_qna")

graph = workflow.compile()


def process_message(user_id: str, message: str) -> dict:
    """Process a user message through the free_form graph."""
    try:
        if user_id not in SESSIONS:
            saved = load_user_session(user_id)
            if saved:
                logger.info("Resuming session for %s", user_id)
                SESSIONS[user_id] = saved
            else:
                SESSIONS[user_id] = {
                    "user_id": user_id,
                    "user_msg": message,
                    "conversation_history": [],
                    "journey_history": [],
                    "full_chat_history": [],
                    "current_agent": None,
                }
        SESSIONS[user_id]["user_msg"] = message

        if SESSIONS[user_id].get("conversation_history") is None:
            SESSIONS[user_id]["conversation_history"] = []
        SESSIONS[user_id]["conversation_history"].append({"role": "user", "content": message})

        if SESSIONS[user_id].get("full_chat_history") is None:
            SESSIONS[user_id]["full_chat_history"] = []
        from datetime import datetime
        SESSIONS[user_id]["full_chat_history"].append({
            "role": "user",
            "content": message,
            "timestamp": datetime.now().isoformat(),
        })

        result = graph.invoke(SESSIONS[user_id])
        SESSIONS[user_id].update(result)
        save_session_to_file(user_id, SESSIONS[user_id])

        return {
            "status": "success",
            "user_id": user_id,
            "current_agent": result.get("current_agent"),
            "last_question": result.get("last_question"),
        }
    except Exception as e:
        logger.error("Error processing message: %s", e)
        from app.services.whatsapp.client import send_whatsapp_message
        send_whatsapp_message(
            user_id,
            "I'm sorry, I encountered an error. Please try again.",
        )
        return {"status": "error", "error": str(e)}


def reset_session(user_id: str):
    """Reset user session."""
    from app.services.crm.sessions import delete_user_session
    if user_id in SESSIONS:
        del SESSIONS[user_id]
    delete_user_session(user_id)
    return {"status": "success", "message": "Session reset"}


def get_session_state(user_id: str) -> dict:
    """Get current session state."""
    return SESSIONS.get(user_id, {})
