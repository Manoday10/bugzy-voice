"""
Bugzy Chatbot Agent - Main Module

This module contains the LangGraph workflow definition and public API functions.
All node functions and routing logic have been extracted to separate modules.
"""

# Standard library imports
import logging
from datetime import datetime

# Third-party imports
from langgraph.graph import StateGraph, END

logger = logging.getLogger(__name__)

# Local imports - State
from app.services.chatbot.bugzy_gut_cleanse.state import State

# Local imports - Session
from app.services.crm.sessions import SESSIONS, load_user_session, save_session_to_file

# Local imports - Router
from app.services.chatbot.bugzy_gut_cleanse.router import router, resume_router

# Local imports - All node functions
from app.services.chatbot.bugzy_gut_cleanse.nodes import (
    # User verification nodes - New profiling flow
    verify_user_node,
    collect_age_eligibility,
    collect_age_warning_confirmation,
    collect_gender,
    collect_pregnancy_check,
    collect_pregnancy_warning_confirmation,
    transition_to_snap,
    snap_image_analysis,

    transition_to_gut_coach,

    # Extended Profiling Nodes
    collect_health_safety_screening,
    collect_detox_experience,
    

    generate_meal_plan,  # This is the Day 1 meal plan function
    generate_meal_day2_plan,
    generate_meal_day3_plan,
    generate_meal_day4_plan,
    generate_meal_day5_plan,
    generate_meal_day6_plan,
    generate_meal_day7_plan,
    handle_meal_day1_review_choice,
    collect_meal_day1_changes,
    regenerate_meal_day1_plan,
    handle_meal_day1_revised_review,
    generate_all_remaining_meal_days,
    
    ask_meal_plan_preference,
    voice_agent_promotion_meal,
    ask_existing_meal_plan_choice,
    load_existing_meal_plan_for_edit,
    
    # New 11-Question Meal Plan Flow Nodes
    collect_dietary_preference,
    collect_cuisine_preference,
    collect_food_allergies_intolerances,
    collect_daily_eating_pattern,
    collect_foods_avoid,
    collect_supplements,
    collect_digestive_issues,
    collect_hydration,
    collect_other_beverages,
    collect_gut_sensitivity,
    
    # QnA nodes
    health_qna_node,
    product_qna_node,
    post_plan_qna_node,
    resume_from_qna_node,
    
    # Plan edit nodes
    handle_meal_day_selection_for_edit,
    collect_meal_day_edit_changes,
)

# Utility imports are no longer needed in the refactored agent.py
# Session management is handled in the nodes and api.py

workflow = StateGraph(State)

# Add shared nodes - New profiling flow
workflow.add_node("verify_user", verify_user_node)
workflow.add_node("collect_age_eligibility", collect_age_eligibility)
workflow.add_node("collect_age_warning_confirmation", collect_age_warning_confirmation)
workflow.add_node("collect_gender", collect_gender)
workflow.add_node("collect_pregnancy_check", collect_pregnancy_check)
workflow.add_node("collect_pregnancy_warning_confirmation", collect_pregnancy_warning_confirmation)

# Add extended profiling nodes
workflow.add_node("collect_health_safety_screening", collect_health_safety_screening)
workflow.add_node("collect_detox_experience", collect_detox_experience)

# Add health Q&A node
workflow.add_node("health_qna", health_qna_node)
workflow.add_node("product_qna", product_qna_node)



# New 11-Question Meal Plan Flow Nodes
workflow.add_node("collect_dietary_preference", collect_dietary_preference)
workflow.add_node("collect_cuisine_preference", collect_cuisine_preference)
workflow.add_node("collect_food_allergies_intolerances", collect_food_allergies_intolerances)
workflow.add_node("collect_daily_eating_pattern", collect_daily_eating_pattern)
workflow.add_node("collect_foods_avoid", collect_foods_avoid)
workflow.add_node("collect_supplements", collect_supplements)
workflow.add_node("collect_digestive_issues", collect_digestive_issues)
workflow.add_node("collect_hydration", collect_hydration)
workflow.add_node("collect_other_beverages", collect_other_beverages)
workflow.add_node("collect_gut_sensitivity", collect_gut_sensitivity)
workflow.add_node("ask_meal_plan_preference", ask_meal_plan_preference)
workflow.add_node("voice_agent_promotion_meal", voice_agent_promotion_meal)
workflow.add_node("ask_existing_meal_plan_choice", ask_existing_meal_plan_choice)
workflow.add_node("load_existing_meal_plan_for_edit", load_existing_meal_plan_for_edit)

workflow.add_node("generate_meal_plan", generate_meal_plan)
workflow.add_node("handle_meal_day1_review_choice", handle_meal_day1_review_choice)
workflow.add_node("collect_meal_day1_changes", collect_meal_day1_changes)
workflow.add_node("regenerate_meal_day1_plan", regenerate_meal_day1_plan)
workflow.add_node("handle_meal_day1_revised_review", handle_meal_day1_revised_review)
workflow.add_node("generate_all_remaining_meal_days", generate_all_remaining_meal_days)
workflow.add_node("generate_meal_day2_plan", generate_meal_day2_plan)
workflow.add_node("generate_meal_day3_plan", generate_meal_day3_plan)
workflow.add_node("generate_meal_day4_plan", generate_meal_day4_plan)
workflow.add_node("generate_meal_day5_plan", generate_meal_day5_plan)
workflow.add_node("generate_meal_day6_plan", generate_meal_day6_plan)
workflow.add_node("generate_meal_day7_plan", generate_meal_day7_plan)
workflow.add_node("transition_to_snap", transition_to_snap)

workflow.add_node("snap_image_analysis", snap_image_analysis)
workflow.add_node("transition_to_gut_coach", transition_to_gut_coach)

# Add completion node
workflow.add_node("post_plan_qna", post_plan_qna_node)

# Add plan edit nodes
workflow.add_node("handle_meal_day_selection_for_edit", handle_meal_day_selection_for_edit)
workflow.add_node("collect_meal_day_edit_changes", collect_meal_day_edit_changes)

# Set conditional entry point with router
workflow.set_conditional_entry_point(
    router,
    {
        "verify_user": "verify_user",
        # New profiling flow
        "collect_age_eligibility": "collect_age_eligibility",
        "collect_age_warning_confirmation": "collect_age_warning_confirmation",
        "collect_gender": "collect_gender",
        "collect_pregnancy_check": "collect_pregnancy_check",
        "collect_pregnancy_warning_confirmation": "collect_pregnancy_warning_confirmation",
        # Extended profiling
        "collect_health_safety_screening": "collect_health_safety_screening",
        "collect_detox_experience": "collect_detox_experience",
        "health_qna": "health_qna",
        "product_qna": "product_qna",
        "post_plan_qna": "post_plan_qna",

        
        # New 11-Question Meal Plan Flow
        "collect_dietary_preference": "collect_dietary_preference",
        "collect_cuisine_preference": "collect_cuisine_preference",
        "collect_food_allergies_intolerances": "collect_food_allergies_intolerances",
        "collect_daily_eating_pattern": "collect_daily_eating_pattern",
        "collect_foods_avoid": "collect_foods_avoid",
        "collect_supplements": "collect_supplements",
        "collect_digestive_issues": "collect_digestive_issues",
        "collect_hydration": "collect_hydration",
        "collect_other_beverages": "collect_other_beverages",
        "collect_gut_sensitivity": "collect_gut_sensitivity",
        "ask_meal_plan_preference": "ask_meal_plan_preference",
        "voice_agent_promotion_meal": "voice_agent_promotion_meal",
        "ask_existing_meal_plan_choice": "ask_existing_meal_plan_choice",
        "load_existing_meal_plan_for_edit": "load_existing_meal_plan_for_edit",

        "generate_meal_plan": "generate_meal_plan",
        "handle_meal_day1_review_choice": "handle_meal_day1_review_choice",
        "collect_meal_day1_changes": "collect_meal_day1_changes",
        "regenerate_meal_day1_plan": "regenerate_meal_day1_plan",
        "handle_meal_day1_revised_review": "handle_meal_day1_revised_review",
        "generate_all_remaining_meal_days": "generate_all_remaining_meal_days",
        "generate_meal_day2_plan": "generate_meal_day2_plan",
        "generate_meal_day3_plan": "generate_meal_day3_plan",
        "generate_meal_day4_plan": "generate_meal_day4_plan",
        "generate_meal_day5_plan": "generate_meal_day5_plan",
        "generate_meal_day6_plan": "generate_meal_day6_plan",
        "generate_meal_day7_plan": "generate_meal_day7_plan",
        "snap_image_analysis": "snap_image_analysis",
        "transition_to_gut_coach": "transition_to_gut_coach",
        "transition_to_snap": "transition_to_snap",
        
        # Plan edit nodes
        "handle_meal_day_selection_for_edit": "handle_meal_day_selection_for_edit",
        "collect_meal_day_edit_changes": "collect_meal_day_edit_changes",
    },
)

# Add edges - all nodes end after one turn (conversation pauses)
# CHANGED: verify_user → ask_meal_plan_preference
workflow.add_edge("verify_user", "ask_meal_plan_preference")
# New profiling flow edges
workflow.add_edge("collect_age_eligibility", END)
workflow.add_edge("collect_age_warning_confirmation", END)
workflow.add_edge("collect_gender", END)
workflow.add_edge("collect_pregnancy_check", END)
workflow.add_edge("collect_pregnancy_warning_confirmation", END)
workflow.add_edge("collect_health_safety_screening", END)
workflow.add_edge("collect_detox_experience", END)


# Health Q&A edge - goes to resume node
workflow.add_node("resume_from_qna", resume_from_qna_node)
workflow.add_edge("health_qna", "resume_from_qna")

# Product Q&A edge - goes to resume node
workflow.add_edge("product_qna", "resume_from_qna")

# Resume from Q&A uses conditional routing


workflow.add_conditional_edges(
    "resume_from_qna",
    resume_router,
    {
        # New profiling flow for resumption
        "collect_age_eligibility": "collect_age_eligibility",
        "collect_age_warning_confirmation": "collect_age_warning_confirmation",
        "collect_gender": "collect_gender",
        "collect_pregnancy_check": "collect_pregnancy_check",
        "collect_pregnancy_warning_confirmation": "collect_pregnancy_warning_confirmation",
        "collect_health_safety_screening": "collect_health_safety_screening",
        "collect_detox_experience": "collect_detox_experience",

        
        # New 11-Question Meal Plan Flow
        "collect_dietary_preference": "collect_dietary_preference",
        "collect_cuisine_preference": "collect_cuisine_preference",
        "collect_food_allergies_intolerances": "collect_food_allergies_intolerances",
        "collect_daily_eating_pattern": "collect_daily_eating_pattern",
        "collect_foods_avoid": "collect_foods_avoid",
        "collect_supplements": "collect_supplements",
        "collect_digestive_issues": "collect_digestive_issues",
        "collect_hydration": "collect_hydration",
        "collect_other_beverages": "collect_other_beverages",
        "collect_gut_sensitivity": "collect_gut_sensitivity",
        "ask_meal_plan_preference": "ask_meal_plan_preference",
        "voice_agent_promotion_meal": "voice_agent_promotion_meal",
        "ask_existing_meal_plan_choice": "ask_existing_meal_plan_choice",
        "load_existing_meal_plan_for_edit": "load_existing_meal_plan_for_edit",

        "generate_meal_plan": "generate_meal_plan",
        "handle_meal_day1_review_choice": "handle_meal_day1_review_choice",
        "collect_meal_day1_changes": "collect_meal_day1_changes",
        "regenerate_meal_day1_plan": "regenerate_meal_day1_plan",
        "handle_meal_day1_revised_review": "handle_meal_day1_revised_review",
        "generate_all_remaining_meal_days": "generate_all_remaining_meal_days",
        "generate_meal_day2_plan": "generate_meal_day2_plan",
        "generate_meal_day3_plan": "generate_meal_day3_plan",
        "generate_meal_day4_plan": "generate_meal_day4_plan",
        "generate_meal_day5_plan": "generate_meal_day5_plan",
        "generate_meal_day6_plan": "generate_meal_day6_plan",
        "generate_meal_day7_plan": "generate_meal_day7_plan",
        "post_plan_qna": "post_plan_qna",
        "transition_to_gut_coach": "transition_to_gut_coach",
        "transition_to_snap": "transition_to_snap",
    }
)

# Meal planner edges 

workflow.add_edge("ask_meal_plan_preference", END) # Wait for preference choice
workflow.add_edge("voice_agent_promotion_meal", END)
workflow.add_edge("ask_existing_meal_plan_choice", END)
workflow.add_edge("load_existing_meal_plan_for_edit", END)
workflow.add_edge("collect_dietary_preference", END)
workflow.add_edge("collect_cuisine_preference", END)
workflow.add_edge("collect_food_allergies_intolerances", END)
workflow.add_edge("collect_daily_eating_pattern", END)
workflow.add_edge("collect_foods_avoid", END)
workflow.add_edge("collect_supplements", END)
workflow.add_edge("collect_digestive_issues", END)
workflow.add_edge("collect_hydration", END)
workflow.add_edge("collect_other_beverages", END)
workflow.add_edge("collect_gut_sensitivity", END)

workflow.add_edge("generate_meal_plan", END)  # Pause for user choice on Day 1 meal plan
workflow.add_edge("handle_meal_day1_review_choice", END)  # Pause after handling choice
workflow.add_edge("collect_meal_day1_changes", END)  # Pause to collect changes
workflow.add_edge("regenerate_meal_day1_plan", END)  # Pause after regenerating
workflow.add_edge("handle_meal_day1_revised_review", END)  # Pause after revised review

# Conditional routing after meal plan completion
def route_after_meal_plan_completion(state: State) -> str:
    """
    Route after meal plan completion based on journey_restart_mode / recreation.
    If user recreated the meal plan from post_plan_qna, END at post_plan_qna — do NOT go to SNAP.
    Otherwise, proceed to SNAP transition.
    """
    is_recreation = (
        state.get("journey_restart_mode") or
        state.get("existing_meal_plan_choice_origin") == "post_plan_qna"
    )
    if is_recreation:
        logger.info("🔄 ROUTE: Meal plan complete (recreation) → END (staying in post_plan_qna)")
        # Don't clear the flag here - it needs to persist for proper state management
        return "__end__"
    logger.info("➡️ ROUTE: Meal plan complete, normal flow → transition_to_snap")
    return "transition_to_snap"

workflow.add_conditional_edges(
    "generate_all_remaining_meal_days",
    route_after_meal_plan_completion,
    {
        "__end__": END,
        "transition_to_snap": "transition_to_snap",
    }
)

workflow.add_edge("transition_to_snap", END)

# Route after SNAP analysis
def route_after_snap(state: State) -> str:
    """
    Route after SNAP analysis.
    If we skipped SNAP (text input), go directly to post_plan_qna.
    If we did analysis (or fallback), go to transition_to_gut_coach.
    """
    if state.get("last_question") == "post_plan_qna":
        return "post_plan_qna"
    return "transition_to_gut_coach"

workflow.add_conditional_edges(
    "snap_image_analysis",
    route_after_snap,
    {
        "post_plan_qna": "post_plan_qna",
        "transition_to_gut_coach": "transition_to_gut_coach"
    }
)

workflow.add_edge("transition_to_gut_coach", "post_plan_qna")

# Post-plan Q&A edge - stays in post-plan Q&A state
workflow.add_edge("post_plan_qna", END)

# workflow.add_edge("post_plan", END)

graph = workflow.compile()

# --- Public API for external integration ---
def process_message(user_id: str, message: str) -> dict:
    """
    Process a user message and return the response.
    This is the main entry point for external systems (like api.py).
    
    Args:
        user_id: User's phone number or unique identifier
        message: The message text from the user
    
    Returns:
        dict with status and any relevant data
    """
    try:
        # Get or create session state
        if user_id not in SESSIONS:
            # Try to load from persistent storage first
            saved_session = load_user_session(user_id)
            
            if saved_session:
                # Resume from saved session
                logger.info("🔄 Resuming session for %s from %s", user_id, saved_session.get('last_question', 'unknown'))
                SESSIONS[user_id] = saved_session
                SESSIONS[user_id]["interaction_mode"] = "chat"
                SESSIONS[user_id]["user_msg"] = message

                user_name = saved_session.get("user_name", "there")
                last_step = saved_session.get("last_question", "unknown")

                from app.services.chatbot.resume_questions import get_question_for_resume
                actual_question = get_question_for_resume("gut_cleanse", last_step)

                # Create a friendly resume message
                resume_messages = {
                    "age": "asking for your age",
                    "height": "asking for your height",
                    "weight": "asking for your weight",

                    "dietary_preference": "asking about dietary preference",
                    "cuisine_preference": "asking about cuisine preference",
                    "food_allergies_intolerances": "asking about food allergies or intolerances",
                    "daily_eating_pattern": "asking about daily eating pattern",
                    "foods_avoid": "asking about foods you avoid",
                    "supplements": "asking about supplements",
                    "digestive_issues": "asking about digestive issues",
                    "hydration": "asking about hydration",
                    "other_beverages": "asking about other beverages",
                    "gut_sensitivity": "asking about gut sensitivity",
                    "handle_meal_day1_review_choice": "handling day 1 meal plan review choice",
                    "handle_meal_day1_revised_review": "handling day 1 meal plan revised review",
                    "generate_meal_day1_plan": "generating day 1 meal plan",
                    "generate_all_remaining_meal_days": "generating all remaining meal days",
                    "transition_to_snap": "transitioning to snap",
                    "transition_to_gut_coach": "transitioning to gut coach",
                }
                
                step_description = resume_messages.get(last_step, "your wellness plan")
                if actual_question:
                    send_whatsapp_message(
                        user_id,
                        f"Welcome back, {user_name}! 👋 {actual_question}"
                    )
                else:
                    send_whatsapp_message(
                        user_id,
                        f"Welcome back, {user_name}! 👋 Ready to continue your gut reset? We were at {step_description}. Let's pick it up!"
                    )
            else:
                # Create new session
                logger.info("🆕 Creating new session for %s", user_id)
                SESSIONS[user_id] = {
                    "user_id": user_id,
                    "user_msg": message,
                    "conversation_history": [],
                    "journey_history": [],
                    "full_chat_history": [],
                    "current_agent": None,
                }
        else:
            SESSIONS[user_id]["user_msg"] = message
        
        # Add to conversation history
        if SESSIONS[user_id].get("conversation_history") is None:
            SESSIONS[user_id]["conversation_history"] = []
        SESSIONS[user_id]["conversation_history"].append({
            "role": "user",
            "content": message
        })
        
        # Add to full chat history
        if SESSIONS[user_id].get("full_chat_history") is None:
            SESSIONS[user_id]["full_chat_history"] = []
        SESSIONS[user_id]["full_chat_history"].append({
            "role": "user",
            "content": message,
            "timestamp": datetime.now().isoformat()
        })
        
        # Run the graph
        result = graph.invoke(SESSIONS[user_id])
        
        # Update session with result
        SESSIONS[user_id].update(result)
        
        # Save session to file after each step
        save_session_to_file(user_id, SESSIONS[user_id])
        
        return {
            "status": "success",
            "user_id": user_id,
            "current_agent": result.get("current_agent"),
            "last_question": result.get("last_question"),
            "meal_plan_sent": result.get("meal_plan_sent", False),
        }
    
    except Exception as e:
        logger.error("Error processing message: %s", e)
        send_whatsapp_message(
            user_id,
            "I'm sorry, I encountered an error. Please try again or type 'restart' to begin fresh."
        )
        return {
            "status": "error",
            "error": str(e)
        }

def reset_session(user_id: str):
    """Reset a user's session from both memory and persistent storage."""
    # Delete from memory
    if user_id in SESSIONS:
        del SESSIONS[user_id]
    
    # Delete from persistent storage
    delete_user_session(user_id)
    
    return {"status": "success", "message": "Session reset from memory and storage"}

def get_session_state(user_id: str) -> dict:
    """Get the current state of a user's session."""
    return SESSIONS.get(user_id, {})