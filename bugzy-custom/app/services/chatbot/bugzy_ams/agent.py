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
from app.services.chatbot.bugzy_ams.state import State

# Local imports - Session
from app.services.crm.sessions import SESSIONS, load_user_session, save_session_to_file

# Local imports - Router
from app.services.chatbot.bugzy_ams.router import (
    router,
    resume_router,
    route_after_bmi_calculation,
    route_after_collect_weight,
)

# Local imports - All node functions
from app.services.chatbot.bugzy_ams.nodes import (
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
    ask_existing_meal_plan_choice,
    load_existing_meal_plan_for_edit,
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
    
    # AMS Specific Nodes
    collect_diet_preference,
    collect_cuisine_preference,
    collect_current_dishes,
    collect_allergies,
    collect_water_intake,
    collect_beverages,
    collect_supplements,
    collect_gut_health,
    collect_meal_goals,
    collect_fitness_level,
    collect_activity_types,
    collect_exercise_frequency,
    collect_exercise_intensity,
    collect_session_duration,
    collect_sedentary_time,
    collect_exercise_goals,
    
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

    
    # Permission nodes
    ask_meal_plan_preference,
    voice_agent_promotion_meal,
    ask_exercise_plan_preference,
    voice_agent_promotion_exercise,
    ask_existing_exercise_plan_choice,
    load_existing_exercise_plan_for_edit,
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
workflow.add_node("ask_meal_plan_preference", ask_meal_plan_preference)
workflow.add_node("voice_agent_promotion_meal", voice_agent_promotion_meal)
workflow.add_node("ask_existing_meal_plan_choice", ask_existing_meal_plan_choice)
workflow.add_node("load_existing_meal_plan_for_edit", load_existing_meal_plan_for_edit)
workflow.add_node("collect_health_conditions", collect_health_conditions)
workflow.add_node("collect_medications", collect_medications)

# AMS Specific Meal Nodes
workflow.add_node("collect_diet_preference", collect_diet_preference)
workflow.add_node("collect_cuisine_preference", collect_cuisine_preference)
workflow.add_node("collect_current_dishes", collect_current_dishes)
workflow.add_node("collect_allergies", collect_allergies)
workflow.add_node("collect_water_intake", collect_water_intake)
workflow.add_node("collect_beverages", collect_beverages)
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
workflow.add_node("ask_exercise_plan_preference", ask_exercise_plan_preference)
workflow.add_node("voice_agent_promotion_exercise", voice_agent_promotion_exercise)
workflow.add_node("ask_existing_exercise_plan_choice", ask_existing_exercise_plan_choice)
workflow.add_node("load_existing_exercise_plan_for_edit", load_existing_exercise_plan_for_edit)
# AMS Specific Exercise Nodes
# FITT Assessment Nodes
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
        "ask_meal_plan_preference": "ask_meal_plan_preference",
        "voice_agent_promotion_meal": "voice_agent_promotion_meal",
        "ask_existing_meal_plan_choice": "ask_existing_meal_plan_choice",
        "load_existing_meal_plan_for_edit": "load_existing_meal_plan_for_edit",
        "ask_existing_exercise_plan_choice": "ask_existing_exercise_plan_choice",
        "load_existing_exercise_plan_for_edit": "load_existing_exercise_plan_for_edit",
        
        # AMS Specific
        "collect_diet_preference": "collect_diet_preference",
        "collect_cuisine_preference": "collect_cuisine_preference",
        "collect_current_dishes": "collect_current_dishes",
        "collect_allergies": "collect_allergies",
        "collect_water_intake": "collect_water_intake",
        "collect_beverages": "collect_beverages",
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
        "ask_exercise_plan_preference": "ask_exercise_plan_preference",
        "voice_agent_promotion_exercise": "voice_agent_promotion_exercise",
        
        # AMS Specific
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
# CHANGED: verify_user → ask_meal_plan_preference (was collect_age)
workflow.add_edge("verify_user", "ask_meal_plan_preference")
workflow.add_edge("collect_age", END)
workflow.add_edge("collect_height", END)
workflow.add_conditional_edges(
    "collect_weight",
    route_after_collect_weight,
    {"calculate_bmi": "calculate_bmi", "__end__": END},
)
# CHANGED: After BMI calculation, use conditional routing based on context
# workflow.add_edge("calculate_bmi", "transition_to_snap")  # OLD: Static edge

# NEW: Conditional edge for calculate_bmi based on profiling context
workflow.add_conditional_edges(
    "calculate_bmi",
    route_after_bmi_calculation,
    {
        "collect_health_conditions": "collect_health_conditions",  # If collected in meal flow
        "transition_to_exercise": "transition_to_exercise",  # AMS: If collected in exercise flow
        "transition_to_snap": "transition_to_snap",  # End-of-journey fallback
    }
)

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
        "collect_age": "collect_age",  # Added collect_age for resumption
        "collect_height": "collect_height",
        "collect_weight": "collect_weight",
        "calculate_bmi": "calculate_bmi",
        "collect_health_conditions": "collect_health_conditions",
        "collect_medications": "collect_medications",
        
        # AMS Specific
        "collect_diet_preference": "collect_diet_preference",
        "collect_cuisine_preference": "collect_cuisine_preference",
        "collect_current_dishes": "collect_current_dishes",
        "collect_allergies": "collect_allergies",
        "collect_water_intake": "collect_water_intake",
        "collect_beverages": "collect_beverages",
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
        "ask_meal_plan_preference": "ask_meal_plan_preference",
        "voice_agent_promotion_meal": "voice_agent_promotion_meal",
        "ask_exercise_plan_preference": "ask_exercise_plan_preference",
        "voice_agent_promotion_exercise": "voice_agent_promotion_exercise",
        "transition_to_gut_coach": "transition_to_gut_coach",
        "transition_to_snap": "transition_to_snap",
    }
)

# Meal planner edges 
# Meal planner edges 
workflow.add_edge("collect_health_conditions", END)
workflow.add_edge("collect_medications", END) # Note: Router will handle next step
workflow.add_edge("ask_meal_plan_preference", END)
workflow.add_edge("voice_agent_promotion_meal", END)
workflow.add_edge("ask_existing_meal_plan_choice", END)
workflow.add_edge("load_existing_meal_plan_for_edit", END)
workflow.add_edge("collect_diet_preference", END)
workflow.add_edge("collect_cuisine_preference", END)
workflow.add_edge("collect_current_dishes", END)
workflow.add_edge("collect_allergies", END)
workflow.add_edge("collect_water_intake", END)
workflow.add_edge("collect_beverages", END)
workflow.add_edge("collect_supplements", END)
workflow.add_edge("collect_gut_health", END)
workflow.add_edge("collect_meal_goals", END)

workflow.add_edge("generate_meal_plan", END)  # Pause for user choice on Day 1 meal plan
workflow.add_edge("handle_meal_day1_review_choice", END)  # Pause after handling choice
workflow.add_edge("collect_meal_day1_changes", END)  # Pause to collect changes
workflow.add_edge("regenerate_meal_day1_plan", END)  # Pause after regenerating
workflow.add_edge("handle_meal_day1_revised_review", END)  # Pause after revised review

# Conditional routing after meal plan completion
def route_after_meal_plan_completion(state: State) -> str:
    """
    Route after meal plan completion based on journey_restart_mode / recreation.
    If user recreated the meal plan from post_plan_qna, END at post_plan_qna — do NOT go to exercise/SNAP.
    Otherwise, proceed to exercise plan preference.
    """
    logger.info("🔍 ROUTING AFTER MEAL PLAN: Checking recreation flags")
    logger.info("  - journey_restart_mode: %s", state.get("journey_restart_mode"))
    logger.info("  - existing_meal_plan_choice_origin: %s", state.get("existing_meal_plan_choice_origin"))
    
    is_recreation = (
        state.get("journey_restart_mode") or
        state.get("existing_meal_plan_choice_origin") == "post_plan_qna"
    )
    
    logger.info("  - is_recreation: %s", is_recreation)
    
    if is_recreation:
        logger.info("🔄 ROUTE: Meal plan complete (recreation) → END (staying in post_plan_qna)")
        # Don't clear the flag here - it needs to persist for proper state management
        return "__end__"
    logger.info("➡️ ROUTE: Meal plan complete, normal flow → ask_exercise_plan_preference")
    return "ask_exercise_plan_preference"

workflow.add_conditional_edges(
    "generate_all_remaining_meal_days",
    route_after_meal_plan_completion,
    {
        "__end__": END,
        "ask_exercise_plan_preference": "ask_exercise_plan_preference",
    }
)
# workflow.add_edge("generate_meal_day2_plan", END)
# workflow.add_edge("generate_meal_day3_plan", END)
# workflow.add_edge("generate_meal_day4_plan", END)
# workflow.add_edge("generate_meal_day5_plan", END)
# workflow.add_edge("generate_meal_day6_plan", END)
# workflow.add_edge("generate_meal_day7_plan", "transition_to_exercise")  # After Day 7, transition to exercise
workflow.add_edge("transition_to_exercise", "collect_fitness_level") # This will send message, set agent to exercise, then pause.

# AND ask_exercise_plan_preference should go to END.

workflow.add_edge("ask_exercise_plan_preference", END)
workflow.add_edge("voice_agent_promotion_exercise", END)
workflow.add_edge("ask_existing_exercise_plan_choice", END)
workflow.add_edge("load_existing_exercise_plan_for_edit", END)

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

# Conditional routing after exercise plan completion
def route_after_exercise_plan_completion(state: State) -> str:
    """
    Route after exercise plan completion based on journey_restart_mode / recreation.
    If user recreated the exercise plan from post_plan_qna (journey_restart_mode or
    existing_exercise_plan_choice_origin), END at post_plan_qna — do NOT go to SNAP.
    Otherwise, proceed to profiling or SNAP transition.
    """
    is_recreation = (
        state.get("journey_restart_mode") or
        state.get("existing_exercise_plan_choice_origin") == "post_plan_qna"
    )
    if is_recreation:
        logger.info("🔄 ROUTE: Exercise plan complete (recreation) → END (staying in post_plan_qna)")
        # Don't clear the flag here - it needs to persist for proper state management
        return "__end__"
    
    # CRITICAL FIX: Check if profiling was collected DURING THIS JOURNEY
    # Use journey-specific flags instead of checking data existence
    # This prevents issues with data being cleared by ghost data prevention
    profiling_done_in_journey = (
        state.get("profiling_collected_in_exercise") or 
        state.get("profiling_collected_in_meal") or
        state.get("profiling_collected")
    )
    
    if profiling_done_in_journey:
        # Profiling already done in this journey - skip to SNAP
        logger.info("➡️ ROUTE: Exercise plan complete, profiling done in journey (exercise=%s, meal=%s, flag=%s) → transition_to_snap",
                   state.get("profiling_collected_in_exercise"), 
                   state.get("profiling_collected_in_meal"),
                   state.get("profiling_collected"))
        return "transition_to_snap"
    
    # Profiling not done - collect now (fallback, shouldn't happen with new flow)
    logger.info("➡️ ROUTE: Exercise plan complete, no profiling in journey → collect_age")
    return "collect_age"

workflow.add_conditional_edges(
    "generate_all_remaining_exercise_days",
    route_after_exercise_plan_completion,
    {
        "__end__": END,
        "transition_to_snap": "transition_to_snap",
        "collect_age": "collect_age",  # CHANGED: exercise completion → collect_age (was transition_to_snap)
    }
)
# workflow.add_edge("generate_day2_plan", END)
# workflow.add_edge("generate_day3_plan", END)
# workflow.add_edge("generate_day4_plan", END)
# workflow.add_edge("generate_day5_plan", END)
# workflow.add_edge("generate_day6_plan", END)
# workflow.add_edge("generate_day7_plan", "transition_to_snap")

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

                # Get actual question for flexible chat/voice resume
                from app.services.chatbot.resume_questions import get_question_for_resume
                actual_question = get_question_for_resume("ams", last_step)

                # Create a friendly resume message
                resume_messages = {
                    "age": "asking for your age",
                    "height": "asking for your height",
                    "weight": "asking for your weight",
                    "health_conditions": "asking about health conditions",
                    "medications": "asking about medications",
                    "diet_preference": "asking about your diet preference",
                    "cuisine_preference": "asking about your cuisine preference",
                    "current_dishes": "asking about your current dishes",
                    "allergies": "asking about allergies",
                    "water_intake": "asking about water intake",
                    "beverages": "asking about beverages",
                    "supplements": "asking about supplements",
                    "gut_health": "asking about your gut health",
                    "meal_goals": "asking about your meal goals",
                    "fitness_level": "asking about your fitness level",
                    "activity_types": "asking about your activities",
                    "exercise_frequency": "asking about your exercise frequency",
                    "exercise_intensity": "asking about your exercise intensity",
                    "session_duration": "asking about your session duration",
                    "sedentary_time": "asking about your daily activity",
                    "exercise_goals": "asking about your exercise goals",
                    "handle_meal_day1_review_choice": "handling day 1 meal plan review choice",
                    "handle_meal_day1_revised_review": "handling day 1 meal plan revised review",
                    "handle_day1_review_choice": "handling day 1 exercise plan review choice",
                    "handle_day1_revised_review": "handling day 1 exercise plan revised review",
                    "generate_meal_day1_plan": "generating day 1 meal plan",
                    "generate_day1_plan": "generating day 1 exercise plan",
                    "generate_all_remaining_meal_days": "generating all remaining meal days",
                    "generate_all_remaining_exercise_days": "generating all remaining exercise days",
                    "transition_to_snap": "transitioning to snap",
                    "post_plan_qna": "post plan qna",
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
                        f"Welcome back, {user_name}! 👋 Ready to boost your metabolism again? We were at {step_description}. Let's continue!"
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