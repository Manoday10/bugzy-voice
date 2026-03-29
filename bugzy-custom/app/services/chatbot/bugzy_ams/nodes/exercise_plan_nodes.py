"""
Exercise Plan Nodes Module

This module contains all exercise plan related nodes for the Bugzy agent.
These nodes handle exercise plan generation, review, and revision.
"""

import time
import logging
from app.services.chatbot.bugzy_ams.state import State
from app.services.chatbot.bugzy_ams.constants import (
    EDIT_EXISTING_EXERCISE_PLAN,
    CREATE_NEW_EXERCISE_PLAN,
)
from app.services.whatsapp.utils import (
    _set_if_expected,
    llm,
    _store_question_in_history,
    _update_last_answer_in_history,
)
from app.services.whatsapp.client import (
    send_whatsapp_message,
    _send_whatsapp_buttons,
    _send_whatsapp_list,
)
from app.services.whatsapp.messages import remove_markdown
from app.services.crm.sessions import (
    save_exercise_plan,
    extract_exercise_plan_user_context,
    load_exercise_plan,
)

from app.services.prompts.ams.exercise import (
    generate_day_exercise_plan,
    generate_complete_7day_exercise_plan,
)

from app.services.prompts.ams.conversational import get_conversational_response
from app.services.media.video import search_exercise_videos, format_video_references
from app.services.chatbot.bugzy_ams.nodes.user_verification_nodes import _ams_voice_owns_turn

logger = logging.getLogger(__name__)


# --- EXERCISE PLAN COLLECTION NODES ---

def ask_exercise_plan_preference(state: State) -> State:
    """Node: Ask if user wants an exercise plan."""
    # No input to store from previous step usually, but good practice to check
    if state.get("user_msg") and state.get("last_question") != "meal_plan_complete":
        _update_last_answer_in_history(state, state["user_msg"])

    # More empathetic question
    question = "💪 Well done, everything's coming together nicely.\n\nI can also design a custom exercise routine to complement your goals.\n\nShould I add that to your plan?"

    _send_whatsapp_buttons(
        state["user_id"],
        question,
        [
            {"type": "reply", "reply": {"id": "create_exercise_plan", "title": "Create exercise plan"}},
            {"type": "reply", "reply": {"id": "has_exercise_plan", "title": "I already have one"}},
            {"type": "reply", "reply": {"id": "no_exercise_plan", "title": "Maybe later"}},
        ]
    )

    # Store question in history
    _store_question_in_history(state, question, "ask_exercise_plan_preference")
    
    state["last_question"] = "ask_exercise_plan_preference"
    state["pending_node"] = "ask_exercise_plan_preference"
    return state


def voice_agent_promotion_exercise(state: State) -> State:
    """Node: Present choice between chat and voice agent exercise planning."""
    from app.services.whatsapp.client import _send_whatsapp_call_button

    if _ams_voice_owns_turn(state):
        state["voice_agent_promotion_shown"] = True
        state.setdefault("voice_agent_context", "exercise_planning")
        state["last_question"] = "voice_agent_promotion_exercise"
        state["pending_node"] = "handle_voice_agent_choice_exercise"
        if state.get("user_id"):
            from app.services.crm.sessions import save_session_to_file
            save_session_to_file(state["user_id"], state)
        return state

    benefits_message = (
        "Great! You can create your exercise plan in two ways:\n\n"
        "🎙️ *Voice Agent*: Talk naturally with our AI coach over a phone call\n"
        "• More interactive and conversational\n"
        "• Hands-free experience\n"
        "• Real-time clarifications\n\n"
        "💬 *Chat Here*: Continue in WhatsApp\n"
        "• Visual buttons and menus\n"
        "• Go at your own pace\n"
        "• Easy to review your answers\n\n"
        "Which would you prefer?"
    )
    
    # Message 1: The Chat Here choice
    _send_whatsapp_buttons(
        state["user_id"],
        benefits_message,
        [ {"type": "reply", "reply": {"id": "create_here_chat", "title": "Chat here 💬"}} ]
    )
    
    # Message 2: Native WhatsApp call button — tapping this immediately starts a voice call
    _send_whatsapp_call_button(
        state["user_id"],
        "Or tap below to speak with Bugzy right now 🎙️",
        "+919082131232"
    )
    
    state["last_question"] = "voice_agent_promotion_exercise"
    state["pending_node"] = "handle_voice_agent_choice_exercise"
    state["voice_agent_promotion_shown"] = True
    state["voice_agent_context"] = "exercise_planning"

    if state.get("user_id"):
        from app.services.crm.sessions import save_session_to_file
        save_session_to_file(state["user_id"], state)
    
    return state



def ask_existing_exercise_plan_choice(state: State) -> State:
    """Node: Ask whether to edit existing workout plan or create a new one."""
    if state.get("user_msg"):
        _update_last_answer_in_history(state, state["user_msg"])

    question = "It looks like you already have a workout plan.\n\n*✏️ Edit Day* to modify a specific day\n*🆕 New Plan* to start fresh with new questions"

    _send_whatsapp_buttons(
        state["user_id"],
        question,
        [
            {
                "type": "reply",
                "reply": {"id": EDIT_EXISTING_EXERCISE_PLAN, "title": "✏️ Edit Existing Plan"},
            },
            {
                "type": "reply",
                "reply": {"id": CREATE_NEW_EXERCISE_PLAN, "title": "🆕 Create New Plan"},
            },
        ],
    )

    _store_question_in_history(state, question, "existing_exercise_plan_choice")
    state["last_question"] = "existing_exercise_plan_choice"
    state["pending_node"] = "ask_existing_exercise_plan_choice"
    return state


def load_existing_exercise_plan_for_edit(state: State) -> State:
    """Node: Load an existing exercise plan and start the day-by-day edit flow."""
    user_id = state["user_id"]
    exercise_plan_data = state.get("existing_exercise_plan_data") or load_exercise_plan(user_id) or {}

    if not exercise_plan_data:
        send_whatsapp_message(
            user_id,
            "I couldn't find your existing workout plan. Let's start a new one.",
        )
        # Start fresh exercise journey
        state["current_agent"] = "exercise"
        state["last_question"] = "transitioning_to_exercise"
        return state

    for day_num in range(1, 8):
        key = f"day{day_num}_plan"
        if exercise_plan_data.get(key):
            state[key] = exercise_plan_data[key]

    if exercise_plan_data.get("exercise_plan"):
        state["exercise_plan"] = exercise_plan_data["exercise_plan"]

    sections = [
        {
            "title": "📅 Select Day to Edit",
            "rows": [
                {"id": f"edit_exercise_day{i}", "title": f"Day {i}", "description": f"Edit Day {i} workout plan"}
                for i in range(1, 8)
            ],
        }
    ]

    _send_whatsapp_list(
        user_id=user_id,
        body_text="Which day's workout plan would you like to edit?",
        button_text="Select Day 📅",
        sections=sections,
        header_text="Edit Workout Plan",
    )

    state["edit_mode"] = "exercise"
    state["last_question"] = "select_exercise_day_to_edit"
    state["pending_node"] = "handle_exercise_day_selection_for_edit"
    return state


def collect_fitness_level(state: State) -> State:
    """Node: Collect current fitness level - FITT assessment start."""
    # Voice: when transitioning from exercise promo, user_msg IS the fitness answer
    # (_set_if_expected requires last_question match, so we handle this explicitly)
    if state.get("last_question") in ("voice_agent_promotion_exercise", "transitioning_to_exercise") and state.get("user_msg"):
        um = (state.get("user_msg") or "").strip().lower()
        # Map voice responses to canonical form
        if "beginner" in um or "fitness_beginner" in um or "just starting" in um:
            state["fitness_level"] = "Beginner"
        elif "intermediate" in um or "fitness_intermediate" in um or "active" in um:
            state["fitness_level"] = "Intermediate"
        elif "advanced" in um or "fitness_advanced" in um or "regular" in um:
            state["fitness_level"] = "Advanced"
        else:
            state["fitness_level"] = (state.get("user_msg") or "").strip()

    _set_if_expected(state, "exercise_plan_preference", "exercise_plan_preference")
    _set_if_expected(state, "fitness_level", "fitness_level")

    if state.get("user_msg"):
        _update_last_answer_in_history(state, state["user_msg"])

    fitness = (state.get("fitness_level") or "").strip()
    if fitness:
        state["last_question"] = "fitness_level"
        return collect_activity_types(state)

    is_voice = state.get("interaction_mode") == "voice"
    question = "🏃‍♂️ Let's start with where you're at!\n\nHow would you describe your current fitness level?"
    
    if is_voice:
        from app.services.chatbot.bugzy_ams.voice_questions import VOICE_QUESTIONS
        q = VOICE_QUESTIONS.get("fitness_level", question)
        state.setdefault("messages", []).append({"role": "assistant", "content": q})
    else:
        sections = [
            {
                "title": "Fitness Level",
                "rows": [
                    {"id": "fitness_beginner", "title": "🆕 Beginner", "description": "Just starting/sedentary"},
                    {"id": "fitness_intermediate", "title": "🔥 Intermediate", "description": "Active 3-6 months"},
                    {"id": "fitness_advanced", "title": "💪 Advanced", "description": "Regular exerciser 6+ months"},
                ]
            }
        ]
        _send_whatsapp_list(
            state["user_id"],
            question,
            "Your Fitness Level 💪",
            sections,
            header_text="Fitness Level",
        )
    
    _store_question_in_history(state, question, "fitness_level")
    
    state["last_question"] = "fitness_level"
    state["pending_node"] = "collect_fitness_level"
    
    # Safeguard: Ensure wants_exercise_plan is True since we are in the flow
    state["wants_exercise_plan"] = True
    
    return state


def collect_activity_types(state: State) -> State:
    """Node: Collect types of physical activities done recently."""
    _set_if_expected(state, "fitness_level", "fitness_level")
    _set_if_expected(state, "activity_types", "activity_types")

    if state.get("user_msg"):
        _update_last_answer_in_history(state, state["user_msg"])

    activities = (state.get("activity_types") or "").strip()
    if activities:
        state["last_question"] = "activity_types"
        return collect_exercise_frequency(state)

    is_voice = state.get("interaction_mode") == "voice"
    question = "🧩 This is shaping up well — let me personalize it further.\n\n🏃‍♀️ What types of physical activities did you do in the last week? Select all that apply!"
    
    if is_voice:
        from app.services.chatbot.bugzy_ams.voice_questions import VOICE_QUESTIONS
        q = VOICE_QUESTIONS.get("activity_types", question)
        state.setdefault("messages", []).append({"role": "assistant", "content": q})
    else:
        sections = [
            {
                "title": "Cardio Activities",
                "rows": [
                    {"id": "activity_walking", "title": "🚶 Walking", "description": "Casual or brisk walking"},
                    {"id": "activity_running", "title": "🏃 Running/Jogging", "description": "Running or jogging"},
                    {"id": "activity_cycling", "title": "🚴 Cycling", "description": "Bike riding"},
                ]
            },
            {
                "title": "Strength & Flexibility",
                "rows": [
                    {"id": "activity_yoga", "title": "🧘 Yoga/Pilates", "description": "Flexibility & core"},
                    {"id": "activity_gym", "title": "🏋️ Gym/Weights", "description": "Strength training"},
                    {"id": "activity_sports", "title": "⚽ Sports", "description": "Team or individual sports"},
                    {"id": "activity_none", "title": "❌ None", "description": "No physical activity"},
                ]
            }
        ]
        _send_whatsapp_list(
            state["user_id"],
            question,
            "Recent Activities 🎯",
            sections,
            header_text="Activity Types",
        )
    
    _store_question_in_history(state, question, "activity_types")
    
    state["last_question"] = "activity_types"
    state["pending_node"] = "collect_activity_types"
    return state


def collect_exercise_frequency(state: State) -> State:
    """Node: Collect exercise frequency per week."""
    _set_if_expected(state, "activity_types", "activity_types")
    _set_if_expected(state, "exercise_frequency", "exercise_frequency")

    if state.get("user_msg"):
        _update_last_answer_in_history(state, state["user_msg"])

    freq = (state.get("exercise_frequency") or "").strip()
    if freq:
        state["last_question"] = "exercise_frequency"
        return collect_exercise_intensity(state)

    is_voice = state.get("interaction_mode") == "voice"
    question = "🎯 One last detail to tailor this better.\n\n📅 How many days per week do you typically exercise or do physical activities?"
    
    if is_voice:
        from app.services.chatbot.bugzy_ams.voice_questions import VOICE_QUESTIONS
        q = VOICE_QUESTIONS.get("exercise_frequency", question)
        state.setdefault("messages", []).append({"role": "assistant", "content": q})
    else:
        sections = [
            {
                "title": "Days Per Week",
                "rows": [
                    {"id": "freq_0", "title": "🛋️ 0 days", "description": "Not active"},
                    {"id": "freq_1_2", "title": "🚶 1-2 days", "description": "1-2 days per week"},
                    {"id": "freq_3_4", "title": "🏃 3-4 days", "description": "3-4 days per week"},
                    {"id": "freq_5_6", "title": "💪 5-6 days", "description": "5-6 days per week"},
                    {"id": "freq_7", "title": "🔥 7 days", "description": "Daily activity"},
                ]
            }
        ]
        _send_whatsapp_list(
            state["user_id"],
            question,
            "Weekly Activity 📆",
            sections,
            header_text="Exercise Frequency",
        )
    
    _store_question_in_history(state, question, "exercise_frequency")
    
    state["last_question"] = "exercise_frequency"
    state["pending_node"] = "collect_exercise_frequency"
    return state


def collect_exercise_intensity(state: State) -> State:
    """Node: Collect exercise intensity/effort level."""
    _set_if_expected(state, "exercise_frequency", "exercise_frequency")
    _set_if_expected(state, "exercise_intensity", "exercise_intensity")

    if state.get("user_msg"):
        _update_last_answer_in_history(state, state["user_msg"])

    intensity = (state.get("exercise_intensity") or "").strip()
    if intensity:
        state["last_question"] = "exercise_intensity"
        return collect_session_duration(state)

    is_voice = state.get("interaction_mode") == "voice"
    question = "✅ Your plan is ready; we're just refining the details now.\n\n💨 When you exercise, how would you describe your effort level?"
    
    if is_voice:
        from app.services.chatbot.bugzy_ams.voice_questions import VOICE_QUESTIONS
        q = VOICE_QUESTIONS.get("exercise_intensity", question)
        state.setdefault("messages", []).append({"role": "assistant", "content": q})
    else:
        sections = [
            {
                "title": "Intensity Level",
                "rows": [
                    {"id": "intensity_light", "title": "😌 Light", "description": "Can talk easily"},
                    {"id": "intensity_moderate", "title": "💬 Moderate", "description": "Can talk but breathing harder"},
                    {"id": "intensity_vigorous", "title": "😤 Vigorous", "description": "Hard to talk, breathing heavily"},
                ]
            }
        ]
        _send_whatsapp_list(
            state["user_id"],
            question,
            "Effort Level 🔥",
            sections,
            header_text="Exercise Intensity",
        )
    
    _store_question_in_history(state, question, "exercise_intensity")
    
    state["last_question"] = "exercise_intensity"
    state["pending_node"] = "collect_exercise_intensity"
    return state


def collect_session_duration(state: State) -> State:
    """Node: Collect typical exercise session duration."""
    _set_if_expected(state, "exercise_intensity", "exercise_intensity")
    _set_if_expected(state, "session_duration", "session_duration")

    if state.get("user_msg"):
        _update_last_answer_in_history(state, state["user_msg"])

    duration = (state.get("session_duration") or "").strip()
    if duration:
        state["last_question"] = "session_duration"
        return collect_sedentary_time(state)

    is_voice = state.get("interaction_mode") == "voice"
    question = "🌸 You've done the hard part. Just a quick check before we finish.\n\n⏱️ On average, how long are your exercise sessions?"
    
    if is_voice:
        from app.services.chatbot.bugzy_ams.voice_questions import VOICE_QUESTIONS
        q = VOICE_QUESTIONS.get("session_duration", question)
        state.setdefault("messages", []).append({"role": "assistant", "content": q})
    else:
        sections = [
            {
                "title": "Duration",
                "rows": [
                {"id": "duration_15", "title": "⚡ 15 minutes", "description": "Quick sessions"},
                {"id": "duration_30", "title": "🏃 30 minutes", "description": "Half hour"},
                {"id": "duration_45", "title": "💪 45 minutes", "description": "45 minutes"},
                {"id": "duration_60", "title": "🔥 1 hour", "description": "Full hour"},
                {"id": "duration_90", "title": "🏆 90+ minutes", "description": "Extended sessions"},
            ]
            }
        ]
        _send_whatsapp_list(
            state["user_id"],
            question,
            "Session Length ⏰",
            sections,
            header_text="Session Duration",
        )
    
    _store_question_in_history(state, question, "session_duration")
    
    state["last_question"] = "session_duration"
    state["pending_node"] = "collect_session_duration"
    return state


def collect_sedentary_time(state: State) -> State:
    """Node: Collect sedentary time per day."""
    _set_if_expected(state, "session_duration", "session_duration")
    _set_if_expected(state, "sedentary_time", "sedentary_time")

    if state.get("user_msg"):
        _update_last_answer_in_history(state, state["user_msg"])

    sedentary = (state.get("sedentary_time") or "").strip()
    if sedentary:
        state["last_question"] = "sedentary_time"
        return collect_exercise_goals(state)

    is_voice = state.get("interaction_mode") == "voice"
    question = "🔄 Just refining things now.\n\n🪑 Roughly how many hours per day do you spend sitting or lying down (excluding sleep)?"
    
    if is_voice:
        from app.services.chatbot.bugzy_ams.voice_questions import VOICE_QUESTIONS
        q = VOICE_QUESTIONS.get("sedentary_time", question)
        state.setdefault("messages", []).append({"role": "assistant", "content": q})
    else:
        sections = [
            {
                "title": "Daily Sitting Time",
                "rows": [
                    {"id": "sedentary_2_4", "title": "🚶 2-4 hours", "description": "Minimal sitting"},
                    {"id": "sedentary_4_6", "title": "💺 4-6 hours", "description": "Moderate sitting"},
                    {"id": "sedentary_6_8", "title": "🪑 6-8 hours", "description": "Desk job range"},
                    {"id": "sedentary_8_10", "title": "😴 8-10 hours", "description": "High sitting time"},
                    {"id": "sedentary_10_plus", "title": "🛋️ 10+ hours", "description": "Very sedentary"},
                ]
            }
        ]
        _send_whatsapp_list(
            state["user_id"],
            question,
            "Sitting Time 💺",
            sections,
            header_text="Sedentary Time",
        )
    
    _store_question_in_history(state, question, "sedentary_time")
    
    state["last_question"] = "sedentary_time"
    state["pending_node"] = "collect_sedentary_time"
    return state


def collect_exercise_goals(state: State) -> State:
    """Node: Collect exercise goals - final question in exercise assessment."""
    _set_if_expected(state, "sedentary_time", "sedentary_time")
    _set_if_expected(state, "exercise_goals", "exercise_goals")

    if state.get("user_msg"):
        _update_last_answer_in_history(state, state["user_msg"])

    goals = (state.get("exercise_goals") or "").strip()
    if goals:
        state["last_question"] = "exercise_goals"
        return generate_day1_plan(state)

    is_voice = state.get("interaction_mode") == "voice"
    question = "✨ This is coming together really well.\n\n🎯 What are your main fitness goals? This helps us design the perfect plan for you!"
    
    if is_voice:
        from app.services.chatbot.bugzy_ams.voice_questions import VOICE_QUESTIONS
        q = VOICE_QUESTIONS.get("exercise_goals", question)
        state.setdefault("messages", []).append({"role": "assistant", "content": q})
    else:
        sections = [
            {
                "title": "Fitness Goals",
                "rows": [
                    {"id": "goal_weight_loss", "title": "📉 Weight Loss", "description": "Lose body fat"},
                    {"id": "goal_muscle_gain", "title": "💪 Muscle Gain", "description": "Build muscle mass"},
                    {"id": "goal_lean_athletic", "title": "🏃 Lean & Athletic", "description": "Get lean and fit"},
                    {"id": "goal_flexibility", "title": "🧘 Flexibility", "description": "Improve mobility"},
                    {"id": "goal_general_wellness", "title": "🌟 General Wellness", "description": "Overall health"},
                ]
            }
        ]
        _send_whatsapp_list(
            state["user_id"],
            question,
            "Your Goals 🎯",
            sections,
            header_text="Exercise Goals",
        )
    
    _store_question_in_history(state, question, "exercise_goals")
    
    state["last_question"] = "exercise_goals"
    state["pending_node"] = "collect_exercise_goals"
    return state



# --- DAY-BY-DAY EXERCISE PLAN NODES ---
# --- DAY-BY-DAY EXERCISE PLAN NODES ---
def generate_all_remaining_exercise_days(state: State) -> State:
    """Node: Generate all remaining exercise plans (Days 2-7) at once using separate LLM calls for each day."""
    user_id = state["user_id"]
    
    # IMPORTANT: Change state immediately to prevent re-triggering
    state["last_question"] = "generating_remaining_exercise_days"
    state["pending_node"] = None
    
    send_whatsapp_message(user_id, "🏋️‍♂️ Generating your complete 6-day exercise plan (Days 2-7)\nPlease wait...")
    if state.get("interaction_mode") != "voice":
        time.sleep(1)
    # Generate all days 2-7 - returns a dictionary with keys 'day2', 'day3', etc.
    individual_days = generate_complete_7day_exercise_plan(state)
    
    # Send each day plan as a message
    for day_key in ['day2', 'day3', 'day4', 'day5', 'day6', 'day7']:
        if day_key in individual_days:
            send_whatsapp_message(user_id, individual_days[day_key])
            if state.get("interaction_mode") != "voice":
                time.sleep(0.5)
    # Store individual days in state
    for day_key, day_content in individual_days.items():
        state[f"{day_key}_plan"] = day_content
    
    # Send completion message
    send_whatsapp_message(
        user_id,
        "✌🏻 Your complete 7-day exercise plan has been generated!"
    )
    
    # Store the complete plan (including Day 1) as a combined string for backward compatibility
    complete_plan = "\n\n".join([individual_days.get(f'day{i}', '') for i in range(2, 8)])
    full_plan = f"{state['day1_plan']}\n\n{complete_plan}"
    state["exercise_plan"] = full_plan
    state["exercise_plan_sent"] = True
    
    # Check if this is a journey restart / recreation (user came from post_plan_qna and chose Create New Plan)
    # Re-establish journey_restart_mode so route_after_exercise_plan_completion can END at post_plan_qna (not SNAP)
    logger.info("🔍 EXERCISE PLAN GENERATION: Checking journey_restart_mode")
    logger.info("  - journey_restart_mode: %s", state.get("journey_restart_mode"))
    logger.info("  - existing_exercise_plan_choice_origin: %s", state.get("existing_exercise_plan_choice_origin"))
    
    if state.get("existing_exercise_plan_choice_origin") == "post_plan_qna":
        state["journey_restart_mode"] = True
        logger.info("  - Re-established journey_restart_mode based on origin flag")
    
    if state.get("journey_restart_mode"):
        logger.info("🔄 Journey restart mode detected - exercise plan complete, staying in post_plan_qna")
        state["last_question"] = "post_plan_qna"
        state["current_agent"] = "post_plan_qna"
    else:
        logger.info("➡️ Normal flow - exercise plan complete, proceeding to SNAP")
        state["last_question"] = "exercise_plan_complete"
    
    # Store combined days 2-7 for reference
    state["exercise_days_2_7"] = complete_plan
    
    # Save complete exercise plan to dedicated collection with user context
    exercise_plan_data = {
        "day1_plan": state.get("day1_plan", ""),
        "day2_plan": state.get("day2_plan", ""),
        "day3_plan": state.get("day3_plan", ""),
        "day4_plan": state.get("day4_plan", ""),
        "day5_plan": state.get("day5_plan", ""),
        "day6_plan": state.get("day6_plan", ""),
        "day7_plan": state.get("day7_plan", ""),
        "exercise_plan": state["exercise_plan"],
        "exercise_plan_sent": True,
        "user_context": extract_exercise_plan_user_context(state)
    }
    save_exercise_plan(user_id, exercise_plan_data, product="ams")
    
    return state


def generate_day1_plan(state: State) -> State:
    """Node: Generate Day 1 exercise plan."""
    _set_if_expected(state, "exercise_goals", "exercise_goals")

    if state.get("user_msg"):
        _update_last_answer_in_history(state, state["user_msg"])

    is_voice = state.get("interaction_mode") == "voice"
    if not is_voice:
        goal = state.get('exercise_goals', 'fitness goal')
        response = get_conversational_response(f"Respond encouragingly to their fitness goal: {goal}", user_name=state.get('user_name', ''))
        send_whatsapp_message(state["user_id"], response)
        time.sleep(1.5)
        send_whatsapp_message(state["user_id"], "💪 Awesome! Give me a moment to design your personalized 7-day exercise plan...")

    logger.info("Generating Day 1 Plan...")
    state["profiling_collected_in_exercise"] = True
    state["day1_plan"] = generate_day_exercise_plan(state, 1, "Full Body Activation")

    save_exercise_plan(state["user_id"], {
        "day1_plan": state["day1_plan"],
        "user_context": extract_exercise_plan_user_context(state)
    }, product="ams")

    if is_voice:
        state["exercise_plan"] = state["day1_plan"]
        state["fresh_exercise_plan"] = True
        closing = "Your personalized Day 1 exercise plan is ready. I'm sending it to you on WhatsApp now. Have a great day! <<END_CALL>>"
        state.setdefault("messages", []).append({"role": "assistant", "content": closing})
    else:
        send_whatsapp_message(state["user_id"], state["day1_plan"])
        _send_whatsapp_buttons(
            state["user_id"],
            "What would you like to do next?",
            [
                {"type": "reply", "reply": {"id": "make_changes_exercise_day1", "title": "✏️ Make Changes"}},
                {"type": "reply", "reply": {"id": "continue_7day_exercise", "title": "✅ 7-Day Plan"}},
            ]
        )
    state["last_question"] = "day1_plan_review"
    return state


def generate_day2_plan(state: State) -> State:
    """Node: Generate Day 2 exercise plan."""
    # If resuming after image analysis, do not auto-generate. Ask for confirmation instead.
    if state.get("last_question") == "image_analysis_complete":
        _send_whatsapp_buttons(
            state["user_id"],
            "Shall I generate your Day 2 exercise plan now?",
            [
                {"type": "reply", "reply": {"id": "continue_7day", "title": "✅ Generate Day 2"}},
            ]
        )
        # Return to the prior review step so the existing button flow triggers generation explicitly
        state["last_question"] = "day1_plan_review"
        return state
    logger.info("Generating Day 2 Plan...")
    state["day2_plan"] = generate_day_exercise_plan(state, 2, "Cardio & Endurance")
    # send_whatsapp_message(state["user_id"], state["day2_plan"], "Once you've finished Day 2, let me know and I'll move on to Day 3!")
    send_whatsapp_message(state["user_id"], state["day2_plan"])
    _send_whatsapp_buttons(
        state["user_id"],
        "Let's Move on to Core Stability!",
        [
            {"type": "reply", "reply": {"id": "yes_day2", "title": "✅ Day 3"}},
        ]
    )
    state["last_question"] = "day2_complete"
    return state


def generate_day3_plan(state: State) -> State:
    """Node: Generate Day 3 exercise plan."""
    # If resuming after image analysis, do not auto-generate. Ask for confirmation instead.
    if state.get("last_question") == "image_analysis_complete":
        _send_whatsapp_buttons(
            state["user_id"],
            "Shall I generate your Day 3 exercise plan now?",
            [
                {"type": "reply", "reply": {"id": "yes_day2", "title": "✅ Generate Day 3"}},
            ]
        )
        state["last_question"] = "day2_complete"
        return state
    logger.info("Generating Day 3 Plan...")
    state["day3_plan"] = generate_day_exercise_plan(state, 3, "Core Stability")
    # send_whatsapp_message(state["user_id"], state["day3_plan"], "Once you've finished Day 3, let me know and I'll move on to Day 4!")
    send_whatsapp_message(state["user_id"], state["day3_plan"])
    _send_whatsapp_buttons(
        state["user_id"],
        "Let's Move on to Mobility & Stretching!",
        [
            {"type": "reply", "reply": {"id": "yes_day3", "title": "✅ Day 4"}},
        ]
    )
    state["last_question"] = "day3_complete"
    return state


def generate_day4_plan(state: State) -> State:
    """Node: Generate Day 4 exercise plan."""
    # If resuming after image analysis, do not auto-generate. Ask for confirmation instead.
    if state.get("last_question") == "image_analysis_complete":
        _send_whatsapp_buttons(
            state["user_id"],
            "Shall I generate your Day 4 exercise plan now?",
            [
                {"type": "reply", "reply": {"id": "yes_day3", "title": "✅ Generate Day 4"}},
            ]
        )
        state["last_question"] = "day3_complete"
        return state
    logger.info("Generating Day 4 Plan...")
    state["day4_plan"] = generate_day_exercise_plan(state, 4, "Mobility & Stretching")
    # send_whatsapp_message(state["user_id"], state["day4_plan"], "Once you've finished Day 4, let me know and I'll move on to Day 5!")
    send_whatsapp_message(state["user_id"], state["day4_plan"])
    _send_whatsapp_buttons(
        state["user_id"],
        "Let's Move on to Upper Body Strength!",
        [
            {"type": "reply", "reply": {"id": "yes_day4", "title": "✅ Day 5"}},
        ]
    )
    state["last_question"] = "day4_complete"
    return state


def generate_day5_plan(state: State) -> State:
    """Node: Generate Day 5 exercise plan."""
    # If resuming after image analysis, do not auto-generate. Ask for confirmation instead.
    if state.get("last_question") == "image_analysis_complete":
        _send_whatsapp_buttons(
            state["user_id"],
            "Shall I generate your Day 5 exercise plan now?",
            [
                {"type": "reply", "reply": {"id": "yes_day4", "title": "✅ Generate Day 5"}},
            ]
        )
        state["last_question"] = "day4_complete"
        return state
    logger.info("Generating Day 5 Plan...")
    state["day5_plan"] = generate_day_exercise_plan(state, 5, "Upper Body Strength")
    # send_whatsapp_message(state["user_id"], state["day5_plan"], "Once you've finished Day 5, let me know and I'll move on to Day 6!")
    send_whatsapp_message(state["user_id"], state["day5_plan"])
    _send_whatsapp_buttons(
        state["user_id"],
        "Let's Move on to Lower Body Power!",
        [
            {"type": "reply", "reply": {"id": "yes_day5", "title": "✅ Day 6"}},
        ]
    )
    state["last_question"] = "day5_complete"
    return state


def generate_day6_plan(state: State) -> State:
    """Node: Generate Day 6 exercise plan."""
    # If resuming after image analysis, do not auto-generate. Ask for confirmation instead.
    if state.get("last_question") == "image_analysis_complete":
        _send_whatsapp_buttons(
            state["user_id"],
            "Shall I generate your Day 6 exercise plan now?",
            [
                {"type": "reply", "reply": {"id": "yes_day5", "title": "✅ Generate Day 6"}},
            ]
        )
        state["last_question"] = "day5_complete"
        return state
    logger.info("Generating Day 6 Plan...")
    state["day6_plan"] = generate_day_exercise_plan(state, 6, "Lower Body Power")
    # send_whatsapp_message(state["user_id"], state["day6_plan"], "Once you've finished Day 6, let me know and I'll move on to Day 7!")
    send_whatsapp_message(state["user_id"], state["day6_plan"])
    _send_whatsapp_buttons(
        state["user_id"],
        "Let's Move on to Active Recovery!",
        [
            {"type": "reply", "reply": {"id": "yes_day6", "title": "✅ Day 7"}},
        ]
    )
    state["last_question"] = "day6_complete"
    return state


def generate_day7_plan(state: State) -> State:
    """Node: Generate Day 7 exercise plan."""
    # If resuming after image analysis, do not auto-generate. Ask for confirmation instead.
    if state.get("last_question") == "image_analysis_complete":
        _send_whatsapp_buttons(
            state["user_id"],
            "Shall I generate your Day 7 exercise plan now?",
            [
                {"type": "reply", "reply": {"id": "yes_day6", "title": "✅ Generate Day 7"}},
            ]
        )
        state["last_question"] = "day6_complete"
        return state
    logger.info("Generating Day 7 Plan...")
    state["day7_plan"] = generate_day_exercise_plan(state, 7, "Active Recovery")
    send_whatsapp_message(state["user_id"], state["day7_plan"])
    
    # Send completion message
    send_whatsapp_message(
        state["user_id"],
        "✌🏻 Your complete 7-day exercise plan has been generated!"
    )
    
    # Compile all day plans into a single exercise_plan field for backward compatibility
    full_plan = f"{state['day1_plan']}\n\n{state['day2_plan']}\n\n{state['day3_plan']}\n\n{state['day4_plan']}\n\n{state['day5_plan']}\n\n{state['day6_plan']}\n\n{state['day7_plan']}"
    state["exercise_plan"] = full_plan
    state["exercise_plan_sent"] = True
    state["last_question"] = "exercise_plan_complete"
    return state


# --- DAY 1 REVIEW & REVISION NODES ---
def handle_day1_review_choice(state: State) -> State:
    """Node: Handle user's choice after Day 1 plan generation."""
    user_msg = state.get("user_msg", "").strip()
    user_msg_lower = user_msg.lower()
    
    logger.debug("handle_day1_review_choice: user_msg='%s' (len=%d, repr=%r)", user_msg, len(user_msg), user_msg)
    
    # Guard: If no user message, just wait (don't send "didn't catch that" message)
    if not user_msg:
        logger.debug("No user message yet, waiting for button click...")
        return state
    
    # More flexible button detection - check for key phrases and emojis
    is_make_changes = (
        # Direct button references
        "make_changes_exercise_day1" in user_msg_lower or
        "make_changes_day1" in user_msg_lower or 
        # Soft Review Options (Change)
        "rev_almost" in user_msg_lower or
        "rev_tweak" in user_msg_lower or
        "rev_change" in user_msg_lower or

        "make changes" in user_msg_lower or
        "make change" in user_msg_lower or
        
        # Edit/modify actions
        "edit" in user_msg_lower or
        "modify" in user_msg_lower or
        "change" in user_msg_lower or
        "update" in user_msg_lower or
        "revise" in user_msg_lower or
        "adjust" in user_msg_lower or
        "alter" in user_msg_lower or
        "tweak" in user_msg_lower or
        "amend" in user_msg_lower or
        "correct" in user_msg_lower or
        "fix" in user_msg_lower or
        "improve" in user_msg_lower or
        "enhance" in user_msg_lower or
        "refine" in user_msg_lower or
        "customize" in user_msg_lower or
        "personalize" in user_msg_lower or
        "tailor" in user_msg_lower or
        "adapt" in user_msg_lower or
        "transform" in user_msg_lower or
        "rewrite" in user_msg_lower or
        "redo" in user_msg_lower or
        "reedit" in user_msg_lower or
        "rework" in user_msg_lower or
        
        # Add/remove actions
        "add" in user_msg_lower or
        "remove" in user_msg_lower or
        "delete" in user_msg_lower or
        "replace" in user_msg_lower or
        "swap" in user_msg_lower or
        "substitute" in user_msg_lower or
        "switch" in user_msg_lower or
        "insert" in user_msg_lower or
        "include" in user_msg_lower or
        "incorporate" in user_msg_lower or
        "append" in user_msg_lower or
        "put in" in user_msg_lower or
        "take out" in user_msg_lower or
        "leave out" in user_msg_lower or
        "drop" in user_msg_lower or
        "exclude" in user_msg_lower or
        "omit" in user_msg_lower or
        "exchange" in user_msg_lower or
        "trade" in user_msg_lower or
        
        # Action phrases with "want/need/like/would"
        "i want to change" in user_msg_lower or
        "i'd like to change" in user_msg_lower or
        "i want to add" in user_msg_lower or
        "i'd like to add" in user_msg_lower or
        "i want to edit" in user_msg_lower or
        "i'd like to edit" in user_msg_lower or
        "i want to modify" in user_msg_lower or
        "i'd like to modify" in user_msg_lower or
        "i want to update" in user_msg_lower or
        "i'd like to update" in user_msg_lower or
        "i want to remove" in user_msg_lower or
        "i'd like to remove" in user_msg_lower or
        "i want to replace" in user_msg_lower or
        "i'd like to replace" in user_msg_lower or
        "i want to swap" in user_msg_lower or
        "i'd like to swap" in user_msg_lower or
        "i would like to change" in user_msg_lower or
        "i would like to add" in user_msg_lower or
        "i would like to edit" in user_msg_lower or
        "i wanna change" in user_msg_lower or
        "i wanna add" in user_msg_lower or
        "i wanna edit" in user_msg_lower or
        "i wanna modify" in user_msg_lower or
        "let me change" in user_msg_lower or
        "let me edit" in user_msg_lower or
        "let me add" in user_msg_lower or
        "let me modify" in user_msg_lower or
        "let me update" in user_msg_lower or
        "let me remove" in user_msg_lower or
        "can i change" in user_msg_lower or
        "can i edit" in user_msg_lower or
        "can i add" in user_msg_lower or
        "can i modify" in user_msg_lower or
        "can i remove" in user_msg_lower or
        "can i replace" in user_msg_lower or
        "can i swap" in user_msg_lower or
        "could i change" in user_msg_lower or
        "could i edit" in user_msg_lower or
        "could i add" in user_msg_lower or
        "want to edit" in user_msg_lower or
        "want to change" in user_msg_lower or
        "want to add" in user_msg_lower or
        "want to modify" in user_msg_lower or
        "want to remove" in user_msg_lower or
        "want to replace" in user_msg_lower or
        "need to modify" in user_msg_lower or
        "need to change" in user_msg_lower or
        "need to add" in user_msg_lower or
        "need to edit" in user_msg_lower or
        "need to remove" in user_msg_lower or
        "need to update" in user_msg_lower or
        "need to fix" in user_msg_lower or
        "would like to change" in user_msg_lower or
        "would like to add" in user_msg_lower or
        "would like to edit" in user_msg_lower or
        "wish to change" in user_msg_lower or
        "wish to edit" in user_msg_lower or
        "wish to add" in user_msg_lower or
        "prefer to change" in user_msg_lower or
        "prefer to edit" in user_msg_lower or
        "prefer to add" in user_msg_lower or
        
        # Question patterns
        "how do i change" in user_msg_lower or
        "how do i edit" in user_msg_lower or
        "how do i add" in user_msg_lower or
        "how do i modify" in user_msg_lower or
        "how do i remove" in user_msg_lower or
        "how can i change" in user_msg_lower or
        "how can i edit" in user_msg_lower or
        "how can i add" in user_msg_lower or
        "how to change" in user_msg_lower or
        "how to edit" in user_msg_lower or
        "how to add" in user_msg_lower or
        "how to modify" in user_msg_lower or
        
        # Emoji variations (with and without variant selectors)
        "✏️" in user_msg or
        "✏" in user_msg or
        "📝" in user_msg or  # memo emoji
        "🖊️" in user_msg or  # pen emoji
        "🖊" in user_msg or
        "🖋️" in user_msg or  # fountain pen
        "🖋" in user_msg or
        "➕" in user_msg or  # plus sign
        "➖" in user_msg or  # minus sign
        "✖️" in user_msg or  # x mark
        "✖" in user_msg or
        "❌" in user_msg or  # cross mark
        "🔄" in user_msg or  # refresh/update
        "🔃" in user_msg or  # reload
        "♻️" in user_msg or  # recycle/redo
        "♻" in user_msg or
        "🔁" in user_msg or  # repeat
        "⚙️" in user_msg or  # settings/customize
        "⚙" in user_msg or
        "🛠️" in user_msg or  # tools
        "🛠" in user_msg or
        "🔧" in user_msg or  # wrench/fix
        "⚡" in user_msg or  # quick change
        "💡" in user_msg or  # idea/improve
        "💪" in user_msg or  # flexed biceps (workout related)
        "🏋️" in user_msg or  # weight lifter
        "🏋" in user_msg or
        "🏃" in user_msg or  # runner
        "🏃‍♂️" in user_msg or
        "🏃‍♀️" in user_msg or
        "🚴" in user_msg or  # cyclist
        "🚴‍♂️" in user_msg or
        "🚴‍♀️" in user_msg or
        
        # Starting patterns
        user_msg_lower.startswith("✏") or
        user_msg_lower.startswith("edit") or
        user_msg_lower.startswith("change") or
        user_msg_lower.startswith("modify") or
        user_msg_lower.startswith("add") or
        user_msg_lower.startswith("remove") or
        user_msg_lower.startswith("update") or
        user_msg_lower.startswith("delete") or
        user_msg_lower.startswith("replace") or
        user_msg_lower.startswith("swap") or
        user_msg_lower.startswith("fix") or
        user_msg_lower.startswith("adjust") or
        user_msg_lower.startswith("tweak") or
        user_msg_lower.startswith("revise") or
        user_msg_lower.startswith("customize") or
        user_msg_lower.startswith("let me") or
        user_msg_lower.startswith("can i") or
        user_msg_lower.startswith("could i") or
        user_msg_lower.startswith("i want") or
        user_msg_lower.startswith("i'd like") or
        user_msg_lower.startswith("i need") or
        user_msg_lower.startswith("i would like") or
        user_msg_lower.startswith("i wanna")
    )
    
    is_continue = (
        "continue_7day_exercise" in user_msg_lower or
        "continue_7day" in user_msg_lower or 
        "7-day plan" in user_msg_lower or 
        "7 day plan" in user_msg_lower or 
        "7day plan" in user_msg_lower or
        "generate 7-day" in user_msg_lower or 
        "✅" in user_msg or
        "✓" in user_msg or  # check mark
        user_msg_lower.startswith("✅") or
        user_msg_lower.startswith("✓")
    )
    
    logger.debug("is_make_changes=%s, is_continue=%s", is_make_changes, is_continue)
    
    if is_make_changes:
        send_whatsapp_message(
            state["user_id"],
            "Got it! 📝 Please tell me what changes you'd like to make to your Day 1 exercise plan.\n\nFor example:\n- \"Make it easier/harder\"\n- \"Add more cardio\"\n- \"Replace running with cycling\"\n- \"Shorter workout duration\""
        )
        state["last_question"] = "awaiting_day1_changes"
        state["pending_node"] = "collect_day1_changes"
    elif is_continue:
        send_whatsapp_message(
            state["user_id"],
            "Perfect! 💪 Let me generate the remaining 6 days of your personalized exercise plan\nJust type in *OK* to continue..."
        )
        if state.get("interaction_mode") != "voice":
            time.sleep(1)
        state["last_question"] = "day1_complete"
        state["pending_node"] = "generate_all_remaining_exercise_days"
    else:
        # User input unclear - ask for clarification instead of defaulting
        logger.warning("Unclear user input in day1 review: '%s'", user_msg)
        _send_whatsapp_buttons(
            state["user_id"],
            "Lets get back to the exercise plan. what Would you like to:",
            [
                {"type": "reply", "reply": {"id": "make_changes_day1", "title": "✏️ Make Changes"}},
                {"type": "reply", "reply": {"id": "continue_7day", "title": "✅ 7-Day Plan"}},
            ]
        )
        # Stay in same state to wait for clear input
        state["last_question"] = "day1_plan_review"
    
    return state


def collect_day1_changes(state: State) -> State:
    """Node: Collect user's requested changes for Day 1 plan."""
    user_msg = state.get("user_msg", "").strip()
    
    if not user_msg:
        send_whatsapp_message(state["user_id"], "Please describe the changes you'd like to make to your Day 1 plan.")
        state["last_question"] = "awaiting_day1_changes"
        state["pending_node"] = "collect_day1_changes"
        return state
    
    # Filter out simple acknowledgments (ok, yes, sure, etc.) - these are not actual change requests
    acknowledgments = ["ok", "okay", "yes", "yeah", "sure", "fine", "good", "alright", "k", "kk", "👍", "✓", "✔️"]
    if user_msg.lower() in acknowledgments:
        logger.debug("Ignoring acknowledgment message: '%s'", user_msg)
        # Don't regenerate, just wait for actual change request
        return state
    
    # Accumulate changes: append to existing change request if it exists
    # (API must NOT overwrite day1_change_request for this flow so we keep previous changes)
    existing_changes = state.get("day1_change_request", "").strip()
    if existing_changes:
        # Avoid duplicating if existing is exactly the current message (e.g. from API overwrite)
        if existing_changes.strip().lower() == user_msg.strip().lower():
            accumulated_changes = existing_changes
        else:
            # Combine previous changes with new change request
            state["day1_change_request"] = f"{existing_changes}; {user_msg}"
            accumulated_changes = state["day1_change_request"]
    else:
        # First change request
        state["day1_change_request"] = user_msg
        accumulated_changes = user_msg
    
    # Acknowledge and immediately start regenerating (no confirmation needed)
    send_whatsapp_message(
        state["user_id"],
        f"Got it! 🔄 Regenerating your Day 1 plan with all your changes: {accumulated_changes}\n\n⏳ One moment..."
    )
    
    # Immediately trigger regeneration (no waiting for confirmation)
    return regenerate_day1_plan(state)


def regenerate_day1_plan(state: State) -> State:
    """Node: Regenerate Day 1 plan based on user's feedback."""
    user_changes = state.get("day1_change_request", "")
    old_day1_plan = state.get("day1_plan", "")
    
    # Store the old plan for reference
    if not state.get("old_day1_plans"):
        state["old_day1_plans"] = []
    state["old_day1_plans"].append(old_day1_plan)
    
    # Format accumulated changes for clarity (split by semicolon if multiple)
    if ";" in user_changes:
        changes_list = [c.strip() for c in user_changes.split(";") if c.strip()]
        formatted_changes = "\n".join([f"• {change}" for change in changes_list])
        changes_header = "USER'S ACCUMULATED CHANGE REQUESTS (ALL must be applied):"
    else:
        formatted_changes = user_changes
        changes_header = "USER'S REQUESTED CHANGES:"
    
    # Generate revised plan using LLM with context of old plan and user feedback
    prompt = f"""
You are a professional fitness coach. The user has requested changes to their Day 1 exercise plan.

ORIGINAL DAY 1 PLAN:
{old_day1_plan}

{changes_header}
{formatted_changes}

USER PROFILE:
- Fitness Level: {state.get('fitness_level', 'Not specified')}
- Activity Types: {state.get('activity_types', 'Not specified')}
- Exercise Goals: {state.get('exercise_goals', 'Not specified')}
- Exercise Frequency: {state.get('exercise_frequency', 'Not specified')}
- Exercise Intensity: {state.get('exercise_intensity', 'Not specified')}
- Session Duration: {state.get('session_duration', 'Not specified')}

Create a REVISED Day 1 workout plan that incorporates ALL of the user's requested changes while maintaining the overall structure and effectiveness of the workout.

Format the plan as:
**Day 1: Full Body Activation** 🔥

[Revised workout details here - exercises, sets, reps, duration, etc.]

**💡 Tips:**
[Helpful tips for Day 1]

Keep it concise, practical, and well-structured.
"""
    
    response = llm.invoke(prompt)
    revised_plan = response.content.strip()
    
    # Remove any video references that the LLM might have generated (to avoid duplication)
    import re
    video_removal_patterns = [
        r'🎥[^\n]*Helpful Video References[^\n]*:.*?(?=\n\n🎥|\Z)',
        r'\n\n\*+Helpful Video References\*+:.*?(?=\n\n🎥|\Z)',
        r'\n\nHelpful Video References:.*?(?=\n\n🎥|\Z)',
        r'\n\n🎥.*?(?=\n\n🎥|\Z)'
    ]
    for pattern in video_removal_patterns:
        revised_plan = re.sub(pattern, '', revised_plan, flags=re.DOTALL | re.IGNORECASE)
    revised_plan = revised_plan.strip()
    
    # Try to add video references for the revised plan
    try:
        search_query = f"Full Body Activation {state.get('fitness_level', 'general')} workout exercises"
        videos = search_exercise_videos(search_query, max_results=3)
        video_references = format_video_references(videos)
        revised_plan = revised_plan + video_references
    except Exception as e:
        logger.error("⚠️ Could not add video references to revised plan: %s", e)
    
    # Remove markdown formatting for WhatsApp
    revised_plan = remove_markdown(revised_plan)
    
    state["day1_plan"] = revised_plan
    
    # Save to dedicated collection with old plans, change request, and user context
    exercise_plan_data = {
        "day1_plan": revised_plan,
        "old_day1_plans": state.get("old_day1_plans", []),
        "day1_change_request": state.get("day1_change_request", ""),
        "user_context": extract_exercise_plan_user_context(state)
    }
    save_exercise_plan(state["user_id"], exercise_plan_data, product="ams", increment_change_count=True)
    
    send_whatsapp_message(state["user_id"], revised_plan)
    
    # Ask if they want to make more changes or continue
    _send_whatsapp_buttons(
        state["user_id"],
        "How does this look?",
        [
            {"type": "reply", "reply": {"id": "more_changes_day1", "title": "✏️ More Changes"}},
            {"type": "reply", "reply": {"id": "continue_7day", "title": "✅ 7-Day Plan"}},
        ]
    )
    state["last_question"] = "day1_revised_review"
    return state


def handle_day1_revised_review(state: State) -> State:
    """Node: Handle user's choice after Day 1 plan revision."""
    user_msg = state.get("user_msg", "").strip()
    user_msg_lower = user_msg.lower()
    
    logger.debug("handle_day1_revised_review: user_msg='%s' (len=%d, repr=%r)", user_msg, len(user_msg), user_msg)
    
    # Guard: If no user message, just wait (don't send "didn't catch that" message)
    if not user_msg:
        logger.debug("No user message yet, waiting for button click...")
        return state
    
    # Special guard after SNAP/image analysis resume:
    # Only accept explicit button intents to avoid misclassification from media/auto texts.
    if state.get("snap_analysis_sent"):
        is_explicit_more_changes = ("more_changes_day1" in user_msg_lower)
        is_explicit_continue = ("continue_7day" in user_msg_lower)
        if not (is_explicit_more_changes or is_explicit_continue):
            logger.debug("Post-image analysis resume detected; re-showing clarification buttons for revised review.")
            _send_whatsapp_buttons(
                state["user_id"],
                "Lets get back to the exercise plan. what Would you like to:",
                [
                    {"type": "reply", "reply": {"id": "more_changes_day1", "title": "✏️ More Changes"}},
                    {"type": "reply", "reply": {"id": "continue_7day", "title": "✅ 7-Day Plan"}},
                ]
            )
            state["last_question"] = "day1_revised_review"
            return state
    
    # More flexible button detection - check for key phrases and emojis
    is_more_changes = (
        # Direct button references
        "more_changes_day1" in user_msg_lower or
        "more changes" in user_msg_lower or
        "more change" in user_msg_lower or
        "make changes" in user_msg_lower or
        "make change" in user_msg_lower or
        "additional changes" in user_msg_lower or
        "another change" in user_msg_lower or
        "more edits" in user_msg_lower or
        "more modifications" in user_msg_lower or
        "further changes" in user_msg_lower or
        "further edits" in user_msg_lower or
        "one more change" in user_msg_lower or
        "one more edit" in user_msg_lower or
        "some more changes" in user_msg_lower or
        "a few more changes" in user_msg_lower or
        "extra changes" in user_msg_lower or
        "other changes" in user_msg_lower or
        "different changes" in user_msg_lower or
        "new changes" in user_msg_lower or
        "other edits" in user_msg_lower or
        
        # Action phrases
        "change again" in user_msg_lower or
        "edit again" in user_msg_lower or
        "modify again" in user_msg_lower or
        "revise again" in user_msg_lower or
        "update again" in user_msg_lower or
        "adjust again" in user_msg_lower or
        "change more" in user_msg_lower or
        "edit more" in user_msg_lower or
        "add more" in user_msg_lower or
        "modify more" in user_msg_lower or
        "something else" in user_msg_lower or
        "also change" in user_msg_lower or
        "also edit" in user_msg_lower or
        "also add" in user_msg_lower or
        "also remove" in user_msg_lower or
        "also modify" in user_msg_lower or
        "and change" in user_msg_lower or
        "and edit" in user_msg_lower or
        "and add" in user_msg_lower or
        "and modify" in user_msg_lower or
        "plus" in user_msg_lower or
        
        # Continuation phrases
        "i want more changes" in user_msg_lower or
        "need more changes" in user_msg_lower or
        "want to change more" in user_msg_lower or
        "still need changes" in user_msg_lower or
        "not quite right" in user_msg_lower or
        "needs adjustment" in user_msg_lower or
        "needs more work" in user_msg_lower or
        "keep editing" in user_msg_lower or
        "keep changing" in user_msg_lower or
        "keep modifying" in user_msg_lower or
        "continue editing" in user_msg_lower or
        "continue changing" in user_msg_lower or
        "still editing" in user_msg_lower or
        "not done" in user_msg_lower or
        "not finished" in user_msg_lower or
        "not complete" in user_msg_lower or
        "next change" in user_msg_lower or
        "next edit" in user_msg_lower or
        "i also want to" in user_msg_lower or
        "i'd also like to" in user_msg_lower or
        "i want to also" in user_msg_lower or
        "let me also" in user_msg_lower or
        "can i also" in user_msg_lower or
        "could i also" in user_msg_lower or
        
        # Emoji variations
        "✏️" in user_msg or
        "✏" in user_msg or
        "📝" in user_msg or
        "🖊️" in user_msg or
        "🖊" in user_msg or
        "🖋️" in user_msg or
        "🖋" in user_msg or
        "🔄" in user_msg or  # counterclockwise arrows (repeat)
        "🔁" in user_msg or  # repeat button
        "🔃" in user_msg or  # reload
        "↩️" in user_msg or  # left arrow curving right
        "↩" in user_msg or
        "➕" in user_msg or  # plus sign
        "➡️" in user_msg or  # next/continue
        "➡" in user_msg or
        "▶️" in user_msg or  # play/continue
        "▶" in user_msg or
        "👉" in user_msg or  # pointing right
        "⏭️" in user_msg or  # next track
        "⏭" in user_msg or
        "💪" in user_msg or  # flexed biceps (workout related)
        "🏋️" in user_msg or  # weight lifter
        "🏋" in user_msg or
        "🏃" in user_msg or  # runner
        "🏃‍♂️" in user_msg or
        "🏃‍♀️" in user_msg or
        "🚴" in user_msg or  # cyclist
        "🚴‍♂️" in user_msg or
        "🚴‍♀️" in user_msg or
        
        # Starting patterns
        user_msg_lower.startswith("✏") or
        user_msg_lower.startswith("more") or
        user_msg_lower.startswith("additional") or
        user_msg_lower.startswith("another") or
        user_msg_lower.startswith("change") or
        user_msg_lower.startswith("edit") or
        user_msg_lower.startswith("modify") or
        user_msg_lower.startswith("also") or
        user_msg_lower.startswith("and") or
        user_msg_lower.startswith("plus") or
        user_msg_lower.startswith("keep") or
        user_msg_lower.startswith("still") or
        user_msg_lower.startswith("further") or
        user_msg_lower.startswith("extra") or
        user_msg_lower.startswith("other") or
        user_msg_lower.startswith("different") or
        user_msg_lower.startswith("one more") or
        user_msg_lower.startswith("i also") or
        user_msg_lower.startswith("let me also") or
        user_msg_lower.startswith("can i also")
    )

    is_continue = (
        # Direct button references
        "continue_7day_exercise" in user_msg_lower or
        "continue_7day" in user_msg_lower or
        # Soft Review Options (Continue)
        "rev_perfect" in user_msg_lower or
        "rev_trust" in user_msg_lower or
        "rev_no_changes" in user_msg_lower or
        
        # Button text variations
        "i trust you" in user_msg_lower or
        "this feels perfect" in user_msg_lower or
        "no big changes" in user_msg_lower or
        "do what feels best" in user_msg_lower or

        "continue" in user_msg_lower or
        
        # Plan references
        "7-day plan" in user_msg_lower or
        "7 day plan" in user_msg_lower or
        "7day plan" in user_msg_lower or
        "7 days plan" in user_msg_lower or
        "seven day plan" in user_msg_lower or
        "seven-day plan" in user_msg_lower or
        "weekly plan" in user_msg_lower or
        "full week" in user_msg_lower or
        "complete week" in user_msg_lower or
        "entire week" in user_msg_lower or
        "whole week" in user_msg_lower or
        "rest of week" in user_msg_lower or
        "remaining days" in user_msg_lower or
        
        # Action phrases
        "generate 7-day" in user_msg_lower or
        "generate 7 day" in user_msg_lower or
        "generate weekly" in user_msg_lower or
        "create 7-day" in user_msg_lower or
        "create 7 day" in user_msg_lower or
        "show 7-day" in user_msg_lower or
        "show me 7-day" in user_msg_lower or
        "give me 7-day" in user_msg_lower or
        "build 7-day" in user_msg_lower or
        "proceed" in user_msg_lower or
        "go ahead" in user_msg_lower or
        "move forward" in user_msg_lower or
        "move on" in user_msg_lower or
        "next" in user_msg_lower or
        "yes" in user_msg_lower or
        "yep" in user_msg_lower or
        "yeah" in user_msg_lower or
        "ok" in user_msg_lower or
        "okay" in user_msg_lower or
        "sure" in user_msg_lower or
        "good" in user_msg_lower or
        "great" in user_msg_lower or
        "looks good" in user_msg_lower or
        "sounds good" in user_msg_lower or
        "looks great" in user_msg_lower or
        "sounds great" in user_msg_lower or
        "perfect" in user_msg_lower or
        "approved" in user_msg_lower or
        "approve" in user_msg_lower or
        "accept" in user_msg_lower or
        "accepted" in user_msg_lower or
        "confirmed" in user_msg_lower or
        "confirm" in user_msg_lower or
        "done" in user_msg_lower or
        "finished" in user_msg_lower or
        "ready" in user_msg_lower or
        "all set" in user_msg_lower or
        "that works" in user_msg_lower or
        "that's fine" in user_msg_lower or
        "no changes" in user_msg_lower or
        "no change" in user_msg_lower or
        "don't change" in user_msg_lower or
        "keep it" in user_msg_lower or
        
        # Emoji variations
        "✅" in user_msg or
        "✓" in user_msg or
        "☑️" in user_msg or
        "☑" in user_msg or
        "👍" in user_msg or
        "👍🏻" in user_msg or
        "👍🏼" in user_msg or
        "👍🏽" in user_msg or
        "👍🏾" in user_msg or
        "👍🏿" in user_msg or
        "👌" in user_msg or  # OK hand
        "🆗" in user_msg or
        "✔️" in user_msg or
        "✔" in user_msg or
        "▶️" in user_msg or
        "▶" in user_msg or
        "➡️" in user_msg or
        "➡" in user_msg or
        "⏭️" in user_msg or
        "⏭" in user_msg or
        "⏩" in user_msg or  # fast-forward
        "🚀" in user_msg or  # rocket (go ahead)
        
        # Starting patterns
        user_msg_lower.startswith("✅") or
        user_msg_lower.startswith("✓") or
        user_msg_lower.startswith("yes") or
        user_msg_lower.startswith("yeah") or
        user_msg_lower.startswith("yep") or
        user_msg_lower.startswith("continue") or
        user_msg_lower.startswith("proceed") or
        user_msg_lower.startswith("next") or
        user_msg_lower.startswith("go") or
        user_msg_lower.startswith("ok") or
        user_msg_lower.startswith("sure") or
        user_msg_lower.startswith("perfect") or
        user_msg_lower.startswith("great") or
        user_msg_lower.startswith("good")
    )
    
    logger.debug("is_more_changes=%s, is_continue=%s", is_more_changes, is_continue)
    
    if is_more_changes:
        send_whatsapp_message(
            state["user_id"],
            "Sure! 📝 Tell me what additional changes you'd like to make to your Day 1 exercise plan."
        )
        state["last_question"] = "awaiting_day1_changes"
        state["pending_node"] = "collect_day1_changes"
    elif is_continue:
        send_whatsapp_message(
            state["user_id"],
            "Excellent! 💪 Let me generate the remaining 6 days of your personalized exercise plan\nJust type in *OK* to continue..."
        )
        if state.get("interaction_mode") != "voice":
            time.sleep(1)
        state["last_question"] = "day1_complete"
        state["pending_node"] = "generate_all_remaining_exercise_days"
    else:
        # User input unclear - ask for clarification instead of defaulting
        logger.warning("Unclear user input in day1 revised review: '%s'", user_msg)
        _send_whatsapp_buttons(
            state["user_id"],
            "Lets get back to the exercise plan. what Would you like to:",
            [
                {"type": "reply", "reply": {"id": "more_changes_day1", "title": "✏️ More Changes"}},
                {"type": "reply", "reply": {"id": "continue_7day", "title": "✅ 7-Day Plan"}},
            ]
        )
        # Stay in same state to wait for clear input
        state["last_question"] = "day1_revised_review"
    
    return state