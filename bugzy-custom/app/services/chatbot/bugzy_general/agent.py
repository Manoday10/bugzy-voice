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
from app.services.chatbot.bugzy_general.state import State

# Local imports - Session
from app.services.crm.sessions import SESSIONS, load_user_session, save_session_to_file

# Local imports - Router
from app.services.chatbot.bugzy_general.router import router, resume_router

# Local imports - All node functions
from app.services.chatbot.bugzy_general.nodes import (
    # User verification nodes
    verify_user_node,
    collect_age,
    collect_height,
    collect_weight,
    calculate_bmi_node,
    transition_to_snap,
    snap_image_analysis,
    transition_to_gut_coach,
    
    # Meal plan nodes
    collect_health_conditions,
    collect_medications,
    collect_meal_timing_breakfast,
    collect_meal_timing_lunch,
    collect_meal_timing_dinner,
    collect_current_breakfast,
    collect_current_lunch,
    collect_current_dinner,
    collect_diet_preference,
    collect_cuisine_preference,
    collect_allergies,
    collect_water_intake,
    collect_beverages,
    collect_lifestyle,
    collect_activity_level,
    collect_sleep_stress,
    collect_supplements,
    collect_gut_health,
    collect_meal_goals,
    generate_all_remaining_meal_days,
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
    transition_to_exercise,
    
    # Exercise plan nodes
    collect_fitness_level,
    collect_activity_types,
    collect_exercise_frequency,
    collect_exercise_intensity,
    collect_session_duration,
    collect_sedentary_time,
    collect_exercise_goals,
    generate_all_remaining_exercise_days,
    generate_day1_plan,
    generate_day2_plan,
    generate_day3_plan,
    generate_day4_plan,
    generate_day5_plan,
    generate_day6_plan,
    generate_day7_plan,
    handle_day1_review_choice,
    collect_day1_changes,
    regenerate_day1_plan,
    handle_day1_revised_review,
    
    # QnA nodes
    health_qna_node,
    product_qna_node,
    post_plan_qna_node,
    resume_from_qna_node,
    
    # Plan edit nodes
    handle_meal_day_selection_for_edit,
    collect_meal_day_edit_changes,
    handle_exercise_day_selection_for_edit,
    collect_exercise_day_edit_changes,
)

# Utility imports are no longer needed in the refactored agent.py
# Session management is handled in the nodes and api.py

workflow = StateGraph(State)

# Add shared nodes
workflow.add_node("verify_user", verify_user_node)
workflow.add_node("collect_age", collect_age)
workflow.add_node("collect_height", collect_height)
workflow.add_node("collect_weight", collect_weight)
workflow.add_node("calculate_bmi", calculate_bmi_node)

# Add health Q&A node
workflow.add_node("health_qna", health_qna_node)
workflow.add_node("product_qna", product_qna_node)

# Add meal planner nodes
workflow.add_node("collect_health_conditions", collect_health_conditions)
workflow.add_node("collect_medications", collect_medications)
workflow.add_node("collect_meal_timing_breakfast", collect_meal_timing_breakfast)
workflow.add_node("collect_meal_timing_lunch", collect_meal_timing_lunch)
workflow.add_node("collect_meal_timing_dinner", collect_meal_timing_dinner)
workflow.add_node("collect_current_breakfast", collect_current_breakfast)
workflow.add_node("collect_current_lunch", collect_current_lunch)
workflow.add_node("collect_current_dinner", collect_current_dinner)
workflow.add_node("collect_diet_preference", collect_diet_preference)
workflow.add_node("collect_cuisine_preference", collect_cuisine_preference)
workflow.add_node("collect_allergies", collect_allergies)
workflow.add_node("collect_water_intake", collect_water_intake)
workflow.add_node("collect_beverages", collect_beverages)
workflow.add_node("collect_lifestyle", collect_lifestyle)
workflow.add_node("collect_activity_level", collect_activity_level)
workflow.add_node("collect_sleep_stress", collect_sleep_stress)
workflow.add_node("collect_supplements", collect_supplements)
workflow.add_node("collect_gut_health", collect_gut_health)
workflow.add_node("collect_meal_goals", collect_meal_goals)
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
workflow.add_node("transition_to_exercise", transition_to_exercise)
workflow.add_node("transition_to_snap", transition_to_snap)

# Add exercise planner nodes
workflow.add_node("collect_fitness_level", collect_fitness_level)
workflow.add_node("collect_activity_types", collect_activity_types)
workflow.add_node("collect_exercise_frequency", collect_exercise_frequency)
workflow.add_node("collect_exercise_intensity", collect_exercise_intensity)
workflow.add_node("collect_session_duration", collect_session_duration)
workflow.add_node("collect_sedentary_time", collect_sedentary_time)
workflow.add_node("collect_exercise_goals", collect_exercise_goals)
# workflow.add_node("generate_exercise_plan", generate_exercise_plan)

# Add day-by-day exercise plan nodes
workflow.add_node("generate_day1_plan", generate_day1_plan)
workflow.add_node("handle_day1_review_choice", handle_day1_review_choice)
workflow.add_node("collect_day1_changes", collect_day1_changes)
workflow.add_node("regenerate_day1_plan", regenerate_day1_plan)
workflow.add_node("handle_day1_revised_review", handle_day1_revised_review)
workflow.add_node("generate_all_remaining_exercise_days", generate_all_remaining_exercise_days)
workflow.add_node("generate_day2_plan", generate_day2_plan)
workflow.add_node("generate_day3_plan", generate_day3_plan)
workflow.add_node("generate_day4_plan", generate_day4_plan)
workflow.add_node("generate_day5_plan", generate_day5_plan)
workflow.add_node("generate_day6_plan", generate_day6_plan)
workflow.add_node("generate_day7_plan", generate_day7_plan)

workflow.add_node("snap_image_analysis", snap_image_analysis)
workflow.add_node("transition_to_gut_coach", transition_to_gut_coach)

# Add completion node
workflow.add_node("post_plan_qna", post_plan_qna_node)

# Add plan edit nodes
workflow.add_node("handle_meal_day_selection_for_edit", handle_meal_day_selection_for_edit)
workflow.add_node("collect_meal_day_edit_changes", collect_meal_day_edit_changes)
workflow.add_node("handle_exercise_day_selection_for_edit", handle_exercise_day_selection_for_edit)
workflow.add_node("collect_exercise_day_edit_changes", collect_exercise_day_edit_changes)

# Set conditional entry point with router
workflow.set_conditional_entry_point(
    router,
    {
        "verify_user": "verify_user",
        "collect_age": "collect_age",
        "collect_height": "collect_height",
        "collect_weight": "collect_weight",
        "calculate_bmi": "calculate_bmi",
        "health_qna": "health_qna",
        "product_qna": "product_qna",
        "post_plan_qna": "post_plan_qna",
        "collect_health_conditions": "collect_health_conditions",
        "collect_medications": "collect_medications",
        "collect_meal_timing_breakfast": "collect_meal_timing_breakfast",
        "collect_meal_timing_lunch": "collect_meal_timing_lunch",
        "collect_meal_timing_dinner": "collect_meal_timing_dinner",
        "collect_current_breakfast": "collect_current_breakfast",
        "collect_current_lunch": "collect_current_lunch",
        "collect_current_dinner": "collect_current_dinner",
        "collect_diet_preference": "collect_diet_preference",
        "collect_cuisine_preference": "collect_cuisine_preference",
        "collect_allergies": "collect_allergies",
        "collect_water_intake": "collect_water_intake",
        "collect_beverages": "collect_beverages",
        "collect_lifestyle": "collect_lifestyle",
        "collect_activity_level": "collect_activity_level",
        "collect_sleep_stress": "collect_sleep_stress",
        "collect_supplements": "collect_supplements",
        "collect_gut_health": "collect_gut_health",
        "collect_meal_goals": "collect_meal_goals",
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
        "transition_to_exercise": "transition_to_exercise",
        "collect_fitness_level": "collect_fitness_level",
        "collect_activity_types": "collect_activity_types",
        "collect_exercise_frequency": "collect_exercise_frequency",
        "collect_exercise_intensity": "collect_exercise_intensity",
        "collect_session_duration": "collect_session_duration",
        "collect_sedentary_time": "collect_sedentary_time",
        "collect_exercise_goals": "collect_exercise_goals",
        # "generate_exercise_plan": "generate_exercise_plan",
        "generate_day1_plan": "generate_day1_plan",
        "handle_day1_review_choice": "handle_day1_review_choice",
        "collect_day1_changes": "collect_day1_changes",
        "regenerate_day1_plan": "regenerate_day1_plan",
        "handle_day1_revised_review": "handle_day1_revised_review",
        "generate_all_remaining_exercise_days": "generate_all_remaining_exercise_days",
        "generate_day2_plan": "generate_day2_plan",
        "generate_day3_plan": "generate_day3_plan",
        "generate_day4_plan": "generate_day4_plan",
        "generate_day5_plan": "generate_day5_plan",
        "generate_day6_plan": "generate_day6_plan",
        "generate_day7_plan": "generate_day7_plan",
        "snap_image_analysis": "snap_image_analysis",
        "transition_to_gut_coach": "transition_to_gut_coach",
        "transition_to_snap": "transition_to_snap",
        
        # Plan edit nodes
        "handle_meal_day_selection_for_edit": "handle_meal_day_selection_for_edit",
        "collect_meal_day_edit_changes": "collect_meal_day_edit_changes",
        "handle_exercise_day_selection_for_edit": "handle_exercise_day_selection_for_edit",
        "collect_exercise_day_edit_changes": "collect_exercise_day_edit_changes",
    },
)

# Add edges - all nodes end after one turn (conversation pauses)
workflow.add_edge("verify_user", "collect_age")
workflow.add_edge("collect_age", END)
workflow.add_edge("collect_height", END)
workflow.add_edge("collect_weight", END)
workflow.add_edge("calculate_bmi", "collect_health_conditions")

# Health Q&A edge - goes to resume node
workflow.add_node("resume_from_qna", resume_from_qna_node)
workflow.add_edge("health_qna", "resume_from_qna")

# Product Q&A edge - goes to resume node
workflow.add_edge("product_qna", "resume_from_qna")

# Resume from Q&A uses conditional routing
def resume_router(state: State) -> str:
    """Route back to the interrupted node after health Q&A or product Q&A."""
    pending = state.get("pending_node")
    logger.info("RESUME ROUTER - Pending node: %s", pending)
    
    # If both plans are completed, clear pending_node and go to post-plan Q&A
    if state.get("meal_plan_sent") and state.get("exercise_plan_sent"):
        logger.info("RESUME ROUTER - Both plans completed, routing to post_plan_qna")
        return "post_plan_qna"
    
    # If we have a pending node and we're still in plan generation, resume from there
    if pending and not state.get("exercise_plan_sent"):
        # Map last_question values to actual node names if needed
        question_to_node_map = {
            "meal_day1_plan_review": "handle_meal_day1_review_choice",
            "meal_day1_revised_review": "handle_meal_day1_revised_review",
            "day1_plan_review": "handle_day1_review_choice",
            "day1_revised_review": "handle_day1_revised_review",
            "generate_meal_day1_plan": "generate_meal_plan",
            "generate_day1_plan": "generate_day1_plan",
        }
        # If pending is a last_question value, map it to the actual node
        mapped_pending = question_to_node_map.get(pending, pending)
        # Return to the SAME node that was interrupted, not the next one
        # This ensures the user gets asked the question they didn't answer yet
        logger.info("RESUME ROUTER - Returning to: %s (original pending: %s)", mapped_pending, pending)
        return mapped_pending
    
    # If we don't have a pending node, go to collect_age as a fallback
    if not pending:
        logger.info("RESUME ROUTER - No pending node, defaulting to collect_age")
        return "collect_age"
        
    return "post_plan_qna"

workflow.add_conditional_edges(
    "resume_from_qna",
    resume_router,
    {
        "collect_age": "collect_age",  # Added collect_age for resumption
        "collect_height": "collect_height",
        "collect_weight": "collect_weight",
        "calculate_bmi": "calculate_bmi",
        "collect_health_conditions": "collect_health_conditions",
        "collect_medications": "collect_medications",
        "collect_meal_timing_breakfast": "collect_meal_timing_breakfast",
        "collect_meal_timing_lunch": "collect_meal_timing_lunch",
        "collect_meal_timing_dinner": "collect_meal_timing_dinner",
        "collect_current_breakfast": "collect_current_breakfast",
        "collect_current_lunch": "collect_current_lunch",
        "collect_current_dinner": "collect_current_dinner",
        "collect_diet_preference": "collect_diet_preference",
        "collect_cuisine_preference": "collect_cuisine_preference",
        "collect_allergies": "collect_allergies",
        "collect_water_intake": "collect_water_intake",
        "collect_beverages": "collect_beverages",
        "collect_lifestyle": "collect_lifestyle",
        "collect_activity_level": "collect_activity_level",
        "collect_sleep_stress": "collect_sleep_stress",
        "collect_supplements": "collect_supplements",
        "collect_gut_health": "collect_gut_health",
        "collect_meal_goals": "collect_meal_goals",
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
        "collect_fitness_level": "collect_fitness_level",
        "collect_activity_types": "collect_activity_types",
        "collect_exercise_frequency": "collect_exercise_frequency",
        "collect_exercise_intensity": "collect_exercise_intensity",
        "collect_session_duration": "collect_session_duration",
        "collect_sedentary_time": "collect_sedentary_time",
        "collect_exercise_goals": "collect_exercise_goals",
        # "generate_exercise_plan": "generate_exercise_plan",
        "generate_day1_plan": "generate_day1_plan",
        "handle_day1_review_choice": "handle_day1_review_choice",
        "collect_day1_changes": "collect_day1_changes",
        "regenerate_day1_plan": "regenerate_day1_plan",
        "handle_day1_revised_review": "handle_day1_revised_review",
        "generate_all_remaining_exercise_days": "generate_all_remaining_exercise_days",
        "generate_day2_plan": "generate_day2_plan",
        "generate_day3_plan": "generate_day3_plan",
        "generate_day4_plan": "generate_day4_plan",
        "generate_day5_plan": "generate_day5_plan",
        "generate_day6_plan": "generate_day6_plan",
        "generate_day7_plan": "generate_day7_plan",
        "post_plan_qna": "post_plan_qna",
        "transition_to_gut_coach": "transition_to_gut_coach",
        "transition_to_snap": "transition_to_snap",
    }
)

# Meal planner edges 
workflow.add_edge("collect_health_conditions", END)
workflow.add_edge("collect_medications", END)
workflow.add_edge("collect_meal_timing_breakfast", END)
workflow.add_edge("collect_meal_timing_lunch", END)
workflow.add_edge("collect_meal_timing_dinner", END)
workflow.add_edge("collect_current_breakfast", END)
workflow.add_edge("collect_current_lunch", END)
workflow.add_edge("collect_current_dinner", END)
workflow.add_edge("collect_diet_preference", END)
workflow.add_edge("collect_cuisine_preference", END)
workflow.add_edge("collect_allergies", END)
workflow.add_edge("collect_water_intake", END)
workflow.add_edge("collect_beverages", END)
workflow.add_edge("collect_lifestyle", END)
workflow.add_edge("collect_activity_level", END)
workflow.add_edge("collect_sleep_stress", END)
workflow.add_edge("collect_supplements", END)
workflow.add_edge("collect_gut_health", END)
workflow.add_edge("collect_meal_goals", END)
workflow.add_edge("generate_meal_plan", END)  # Pause for user choice on Day 1 meal plan
workflow.add_edge("handle_meal_day1_review_choice", END)  # Pause after handling choice
workflow.add_edge("collect_meal_day1_changes", END)  # Pause to collect changes
workflow.add_edge("regenerate_meal_day1_plan", END)  # Pause after regenerating
workflow.add_edge("handle_meal_day1_revised_review", END)  # Pause after revised review
workflow.add_edge("generate_all_remaining_meal_days", "transition_to_exercise")  # After generating all days, transition to exercise
# workflow.add_edge("generate_meal_day2_plan", END)
# workflow.add_edge("generate_meal_day3_plan", END)
# workflow.add_edge("generate_meal_day4_plan", END)
# workflow.add_edge("generate_meal_day5_plan", END)
# workflow.add_edge("generate_meal_day6_plan", END)
# workflow.add_edge("generate_meal_day7_plan", "transition_to_exercise")  # After Day 7, transition to exercise
workflow.add_edge("transition_to_exercise", "collect_fitness_level")

# Exercise planner edges
workflow.add_edge("collect_fitness_level", END)
workflow.add_edge("collect_activity_types", END)
workflow.add_edge("collect_exercise_frequency", END)
workflow.add_edge("collect_exercise_intensity", END)
workflow.add_edge("collect_session_duration", END)
workflow.add_edge("collect_sedentary_time", END)
workflow.add_edge("collect_exercise_goals", END)

# Exercise plan generation - sequential day-by-day with Day 1 review option
# workflow.add_edge("generate_exercise_plan", "generate_day1_plan")
workflow.add_edge("generate_day1_plan", END)
workflow.add_edge("handle_day1_review_choice", END)
workflow.add_edge("collect_day1_changes", END)
workflow.add_edge("regenerate_day1_plan", END)
workflow.add_edge("handle_day1_revised_review", END)
workflow.add_edge("generate_all_remaining_exercise_days", "transition_to_snap")  # After generating all days, transition to snap
# workflow.add_edge("generate_day2_plan", END)
# workflow.add_edge("generate_day3_plan", END)
# workflow.add_edge("generate_day4_plan", END)
# workflow.add_edge("generate_day5_plan", END)
# workflow.add_edge("generate_day6_plan", END)
# workflow.add_edge("generate_day7_plan", "transition_to_snap")

workflow.add_edge("transition_to_snap", END)
workflow.add_edge("snap_image_analysis", "transition_to_gut_coach")
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
                SESSIONS[user_id]["user_msg"] = message
                
                # Send welcome back message
                user_name = saved_session.get("user_name", "there")
                last_step = saved_session.get("last_question", "unknown")
                
                # Create a friendly resume message
                resume_messages = {
                    "age": "asking for your age",
                    "height": "asking for your height",
                    "weight": "asking for your weight",
                    "health_conditions": "asking about health conditions",
                    "medications": "asking about medications",
                    "meal_timing_breakfast": "asking about breakfast timing",
                    "meal_timing_lunch": "asking about lunch timing",
                    "meal_timing_dinner": "asking about dinner timing",
                    "current_breakfast": "asking about your breakfast habits",
                    "current_lunch": "asking about your lunch habits",
                    "current_dinner": "asking about your dinner habits",
                    "diet_preference": "asking about diet preferences",
                    "cuisine_preference": "asking about cuisine preferences",
                    "allergies": "asking about allergies",
                    "water_intake": "asking about water intake",
                    "beverages": "asking about beverages",
                    "lifestyle": "asking about lifestyle",
                    "activity_level": "asking about activity level",
                    "sleep_stress": "asking about sleep and stress",
                    "supplements": "asking about supplements",
                    "gut_health": "asking about gut health",
                    "meal_goals": "asking about meal goals",
                    "fitness_level": "asking about fitness level",
                    "activity_types": "asking about activity types",
                    "exercise_frequency": "asking about exercise frequency",
                    "exercise_intensity": "asking about exercise intensity",
                    "session_duration": "asking about session duration",
                    "sedentary_time": "asking about sedentary time",
                    "exercise_goals": "asking about exercise goals",
                    "handle_meal_day1_review_choice": "handling day 1 meal plan review choice",
                    "handle_meal_day1_revised_review": "handling day 1 meal plan revised review",
                    "handle_day1_review_choice": "handling day 1 exercise plan review choice",
                    "handle_day1_revised_review": "handling day 1 exercise plan revised review",
                    "generate_meal_day1_plan": "generating day 1 meal plan",
                    "generate_day1_plan": "generating day 1 exercise plan",
                    "generate_all_remaining_meal_days": "generating all remaining meal days",
                    "generate_all_remaining_exercise_days": "generating all remaining exercise days",
                    "transition_to_snap": "transitioning to snap",
                    "transition_to_gut_coach": "transitioning to gut coach",
                    "post_plan_qna": "post plan qna",
                }
                
                step_description = resume_messages.get(last_step, "your wellness plan")
                
                send_whatsapp_message(
                    user_id,
                    f"Welcome back, {user_name}! 👋 I see we were in the middle of {step_description}. Let's continue from where we left off!"
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
            "exercise_plan_sent": result.get("exercise_plan_sent", False),
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