"""
Exercise Plan Nodes Module

This module contains all exercise plan related nodes for the Bugzy agent.
These nodes handle exercise plan generation, review, and revision.
"""

import time
import logging
from app.services.chatbot.bugzy_gut_cleanse.state import State
from app.services.chatbot.bugzy_gut_cleanse.constants import (
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

from app.services.prompts.gut_cleanse.exercise import (
    generate_day_exercise_plan,
    generate_complete_7day_exercise_plan,
)

from app.services.prompts.gut_cleanse.conversational import get_conversational_response
from app.services.media.video import search_exercise_videos, format_video_references
logger = logging.getLogger(__name__)


# --- EXERCISE PLAN COLLECTION NODES ---



# --- EXERCISE PLAN COLLECTION NODES ---

def ask_exercise_plan_preference(state: State) -> State:
    """Node: Ask if user wants an exercise plan."""
    # No input to store from previous step usually, but good practice to check
    if state.get("user_msg") and state.get("last_question") != "meal_plan_complete":
        _update_last_answer_in_history(state, state["user_msg"])

    # More empathetic question
    question = "You're doing amazing!\n💪 I can also design a custom exercise routine to complement your goals.\n\nShould I add that to your plan?"

    _send_whatsapp_buttons(
        state["user_id"],
        question,
        [
            {"type": "reply", "reply": {"id": "yes_exercise_plan", "title": "✅ Yes, create plan"}},
            {"type": "reply", "reply": {"id": "no_exercise_plan", "title": "❌ No, skip for now"}},
        ]
    )

    # Store question in history
    _store_question_in_history(state, question, "ask_exercise_plan_preference")
    
    state["last_question"] = "ask_exercise_plan_preference"
    state["pending_node"] = "ask_exercise_plan_preference"
    return state


def ask_existing_exercise_plan_choice(state: State) -> State:
    """Node: Ask whether to edit existing workout plan or create a new one."""
    if state.get("user_msg"):
        _update_last_answer_in_history(state, state["user_msg"])

    question = "It looks like you already have a workout plan. What would you like to do?"

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
        # Start fresh exercise journey - for gut_cleanse, first question is collect_workout_posture_gut
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


def collect_workout_posture_gut(state: State) -> State:
    """Node: Ask about posture (Gut Cleanse specific - FIRST exercise question)."""
    
    # NEW: Ensure correct agent context if entering here from router skip (Full profiling exists)
    # This handles the case where user has Age/Height/Weight/BMI and jumps straight to exercise questions
    msg = (state.get("user_msg") or "").lower()
    is_yes = any(keyword in msg for keyword in ["yes", "create", "plan", "ok", "sure"])
    if state.get("last_question") == "ask_exercise_plan_preference" and is_yes:
        state["wants_exercise_plan"] = True
        state["current_agent"] = "exercise"
        logger.info("CONTEXT: Set agent to EXERCISE (entering at collect_workout_posture_gut)")
    
    question = "Let's get moving! 🧘‍♀️ Good digestion starts with good posture.\n\nHow would you describe your daily posture?"
    
    sections = [
        {
            "title": "Posture Types",
            "rows": [
                {"id": "posture_sedentary", "title": "🪑 Sedentary", "description": "Sitting most of the day"},
                {"id": "posture_standing", "title": "🧍 Standing", "description": "On feet all day"},
                {"id": "posture_active", "title": "🏃 Active", "description": "Moving constantly"},
                {"id": "posture_mixed", "title": "🔄 Mixed", "description": "Mix of sitting/standing"}
            ]
        }
    ]

    _send_whatsapp_list(
        state["user_id"],
        question,
        "Daily Posture 🪑",
        sections,
        header_text="Posture Check"
    )

    _store_question_in_history(state, question, "workout_posture_gut")

    state["last_question"] = "workout_posture_gut"
    state["pending_node"] = "collect_workout_posture_gut"
    return state


def collect_workout_hydration_gut(state: State) -> State:
    """Node: Ask about hydration during workout (Gut Cleanse specific)."""
    # Store posture from user_msg
    _set_if_expected(state, "workout_posture_gut", "workout_posture_gut")

    if state.get("user_msg"):
        _update_last_answer_in_history(state, state["user_msg"])

    question = "Next up: Hydration! 💧 Water is fuel! Keeping hydrated keeps your system moving smoothly.\n\nHow hydrated do you feel during workouts?"
    
    sections = [
        {
            "title": "Hydration Level",
            "rows": [
                {"id": "hydra_well", "title": "💧 Well Hydrated", "description": "Drink regularly"},
                {"id": "hydra_sip", "title": "🚰 Sip Occasionally", "description": "Drink sometimes"},
                {"id": "hydra_after", "title": "🏁 Only After", "description": "Drink only after workout"},
                {"id": "hydra_dehyd", "title": "🏜️ Often Dehydrated", "description": "Feel thirsty/tired"}
            ]
        }
    ]

    _send_whatsapp_list(
        state["user_id"],
        question,
        "Hydration Check 💧",
        sections,
        header_text="Hydration"
    )

    _store_question_in_history(state, question, "workout_hydration_gut")

    state["last_question"] = "workout_hydration_gut"
    state["pending_node"] = "collect_workout_hydration_gut"
    return state


def collect_workout_gut_mobility_gut(state: State) -> State:
    """Node: Ask about gut mobility exercises (Gut Cleanse specific)."""
    # Store hydration from user_msg
    _set_if_expected(state, "workout_hydration_gut", "workout_hydration_gut")

    if state.get("user_msg"):
        _update_last_answer_in_history(state, state["user_msg"])

    question = "Moving on to movement types. 🤸‍♀️ Movement is medicine! Gentle mobility can work wonders for digestion.\n\nDo you do any specific movements for gut health?"
    
    sections = [
        {
            "title": "Gut Movements",
            "rows": [
                {"id": "move_yoga", "title": "🧘 Yoga/Twists", "description": "Twisting/Stretching"},
                {"id": "move_walk", "title": "🚶 Walking", "description": "Gentle walking"},
                {"id": "move_core", "title": "💪 Core Work", "description": "Ab exercises"},
                {"id": "move_none", "title": "❌ None", "description": "No specific exercises"}
            ]
        }
    ]

    _send_whatsapp_list(
        state["user_id"],
        question,
        "Gut Mobility 🤸",
        sections,
        header_text="Gut Mobility"
    )

    _store_question_in_history(state, question, "workout_gut_mobility_gut")

    state["last_question"] = "workout_gut_mobility_gut"
    state["pending_node"] = "collect_workout_gut_mobility_gut"
    return state


def collect_workout_relaxation_gut(state: State) -> State:
    """Node: Ask about relaxation (Gut Cleanse specific)."""
    # Store gut mobility from user_msg
    _set_if_expected(state, "workout_gut_mobility_gut", "workout_gut_mobility_gut")

    if state.get("user_msg"):
        _update_last_answer_in_history(state, state["user_msg"])

    question = "Now, let's talk about rest. 🌿 Relaxation is part of the work! A calm mind supports a healthy gut.\n\nWhat helps you relax your body and mind?"
    
    sections = [
        {
            "title": "Relaxation",
            "rows": [
                {"id": "relax_breath", "title": "🌬️ Breathing", "description": "Deep breathing/meditation"},
                {"id": "relax_nature", "title": "🌳 Nature/Walk", "description": "Being outside"},
                {"id": "relax_hobby", "title": "📚 Reading/Music", "description": "Hobbies/Music"},
                {"id": "relax_sleep", "title": "😴 Sleep", "description": "Just sleeping"},
                {"id": "relax_none", "title": "❌ None", "description": "Hard to relax"}
            ]
        }
    ]

    _send_whatsapp_list(
        state["user_id"],
        question,
        "Relaxation Routine 🌿",
        sections,
        header_text="Relaxation"
    )

    _store_question_in_history(state, question, "workout_relaxation_gut")

    state["last_question"] = "workout_relaxation_gut"
    state["pending_node"] = "collect_workout_relaxation_gut"
    return state


def collect_workout_gut_awareness_gut(state: State) -> State:
    """Node: Ask about gut awareness (Gut Cleanse specific)."""
    # Store relaxation from user_msg
    _set_if_expected(state, "workout_relaxation_gut", "workout_relaxation_gut")

    if state.get("user_msg"):
        _update_last_answer_in_history(state, state["user_msg"])

    question = "We're in the home stretch now! 🏁 One final detail to customize your routine.\n\n🧠 How aware are you of your gut signals during exercise?"
    
    sections = [
        {
            "title": "Gut Awareness",
            "rows": [
                {"id": "aware_very", "title": "👀 Very Aware", "description": "Feel every signal"},
                {"id": "aware_some", "title": "🤷 Sometimes", "description": "Notice occasionally"},
                {"id": "aware_pain", "title": "⚠️ Only when pain", "description": "Only notice discomfort"},
                {"id": "aware_none", "title": "❌ Not Aware", "description": "Don't really notice"}
            ]
        }
    ]

    _send_whatsapp_list(
        state["user_id"],
        question,
        "Gut Awareness 🧠",
        sections,
        header_text="Awareness"
    )

    _store_question_in_history(state, question, "workout_gut_awareness_gut")

    state["last_question"] = "workout_gut_awareness_gut"
    state["pending_node"] = "collect_workout_gut_awareness_gut"
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
    
    # Check if this is a journey restart - if so, set state for post_plan_qna
    # NOTE: Do NOT clear journey_restart_mode here - the routing function needs to check it!
    # The routing function will END the graph instead of routing to post_plan_qna node
    if state.get("journey_restart_mode"):
        logger.info("Journey restart mode detected - exercise plan complete, staying in post_plan_qna")
        state["last_question"] = "post_plan_qna"
        state["current_agent"] = "post_plan_qna"
        # Routing function will END the graph, so no node will be executed
    else:
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
    save_exercise_plan(user_id, exercise_plan_data)
    
    return state


def generate_day1_plan(state: State) -> State:
    """Node: Generate Day 1 exercise plan."""
    # Store gut awareness from user_msg
    _set_if_expected(state, "workout_gut_awareness_gut", "workout_gut_awareness_gut")

    # Update the previous question's answer
    if state.get("user_msg"):
        _update_last_answer_in_history(state, state["user_msg"])
    
    response = get_conversational_response(f"Respond encouragingly to their gut awareness level: {state['workout_gut_awareness_gut']}", user_name=state.get('user_name', ''))
    send_whatsapp_message(state["user_id"], response)
    if state.get("interaction_mode") != "voice":
        time.sleep(1.5)
    send_whatsapp_message(state["user_id"], "💪 Awesome! Give me a moment to design your personalized 7-day exercise plan...")
    send_whatsapp_message(state["user_id"], "🏋️‍♂️ Generating Day 1 Plan...")
    state["day1_plan"] = generate_day_exercise_plan(state, 1, "Full Body Activation")
    # send_whatsapp_message(state["user_id"], state["day1_plan"], "Once you've finished Day 1, let me know and I'll move on to Day 2!")
    send_whatsapp_message(state["user_id"], state["day1_plan"])
    
    # Mark exercise profiling as collected
    state["profiling_collected_in_exercise"] = True
    
    # Save Day 1 plan to dedicated collection with user context
    save_exercise_plan(state["user_id"], {
        "day1_plan": state["day1_plan"],
        "user_context": extract_exercise_plan_user_context(state)
    })
    
    # Ask user if they want to make changes or continue with 7-day plan
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
    send_whatsapp_message(state["user_id"], "🏋️‍♂️ Generating Day 2 Plan...")
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
    send_whatsapp_message(state["user_id"], "🏋️‍♂️ Generating Day 3 Plan...")
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
    send_whatsapp_message(state["user_id"], "🏋️‍♂️ Generating Day 4 Plan...")
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
    send_whatsapp_message(state["user_id"], "🏋️‍♂️ Generating Day 5 Plan...")
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
    send_whatsapp_message(state["user_id"], "🏋️‍♂️ Generating Day 6 Plan...")
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
    send_whatsapp_message(state["user_id"], "🏋️‍♂️ Generating Day 7 Plan...")
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
        # Soft Review Options (Continue)
        "rev_perfect" in user_msg_lower or
        "rev_trust" in user_msg_lower or
        "rev_no_changes" in user_msg_lower or
        
        # Button text variations
        "i trust you" in user_msg_lower or
        "this feels perfect" in user_msg_lower or
        "no big changes" in user_msg_lower or
        "do what feels best" in user_msg_lower or
        
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
            "Perfect! 💪 Let me generate the remaining 6 days of your personalized exercise plan\nJust type in '*OK*' to continue..."
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
    user_changes = state.get("user_msg", "").strip()
    
    if not user_changes:
        send_whatsapp_message(state["user_id"], "Please describe the changes you'd like to make to your Day 1 plan.")
        state["last_question"] = "awaiting_day1_changes"
        state["pending_node"] = "collect_day1_changes"
        return state
    
    # Filter out simple acknowledgments (ok, yes, sure, etc.) - these are not actual change requests
    acknowledgments = ["ok", "okay", "yes", "yeah", "sure", "fine", "good", "alright", "k", "kk", "👍", "✓", "✔️"]
    if user_changes.lower() in acknowledgments:
        logger.debug("Ignoring acknowledgment message: '%s'", user_changes)
        # Don't regenerate, just wait for actual change request
        return state
    
    # Store the requested changes
    state["day1_change_request"] = user_changes
    
    # Acknowledge and immediately start regenerating (no confirmation needed)
    send_whatsapp_message(
        state["user_id"],
        f"Got it! 🔄 Regenerating your Day 1 plan with: {user_changes}\n\n⏳ One moment..."
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
    
    # Generate revised plan using LLM with context of old plan and user feedback
    prompt = f"""
You are a professional fitness coach. The user has requested changes to their Day 1 exercise plan.

ORIGINAL DAY 1 PLAN:
{old_day1_plan}

USER'S REQUESTED CHANGES:
{user_changes}

USER PROFILE:
- Fitness Level: {state.get('fitness_level', 'Not specified')}
- Activity Types: {state.get('activity_types', 'Not specified')}
- Exercise Goals: {state.get('exercise_goals', 'Not specified')}
- Exercise Frequency: {state.get('exercise_frequency', 'Not specified')}
- Exercise Intensity: {state.get('exercise_intensity', 'Not specified')}
- Session Duration: {state.get('session_duration', 'Not specified')}

Create a REVISED Day 1 workout plan that incorporates the user's requested changes while maintaining the overall structure and effectiveness of the workout.

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
    save_exercise_plan(state["user_id"], exercise_plan_data)
    
    send_whatsapp_message(state["user_id"], revised_plan)
    
    # Ask if they want to make more changes or continue
    # Ask if they want to make more changes or continue
    sections = [
        {
            "title": "Ready to Proceed? 🚀",
            "rows": [
                {"id": "rev_perfect", "title": "✨ This feels perfect", "description": "Go ahead and create my plan"},
                {"id": "rev_trust", "title": "🤝 I trust you", "description": "Do what feels best and finalize"},
                {"id": "rev_no_changes", "title": "🌊 No big changes", "description": "I'm ready when you are"}
            ]
        },
        {
            "title": "Needs Refinement? 🛠️",
            "rows": [
                {"id": "rev_almost", "title": "🌸 Almost perfect", "description": "Make very small adjustments"},
                {"id": "rev_tweak", "title": "💭 Just a minor tweak", "description": "One small adjustment needed"},
                {"id": "rev_change", "title": "✏️ Make changes", "description": "I need to edit something"}
            ]
        }
    ]

    _send_whatsapp_list(
        state["user_id"],
        "How does this look? 🏋️‍♂️",
        "Review Revision 📋",
        sections,
        header_text="Revision Review"
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
        "continue_7day" in user_msg_lower or
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
            "Excellent! 💪 Let me generate the remaining 6 days of your personalized exercise plan\nJust type in '*OK*' to continue..."
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