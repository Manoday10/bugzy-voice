"""
Meal Plan Nodes Module

This module contains all meal plan related nodes for the Bugzy agent.
These nodes handle meal plan generation, review, and revision.
"""

import time
import logging
from app.services.chatbot.bugzy_gut_cleanse.state import State
from app.services.chatbot.bugzy_gut_cleanse.constants import (
    EDIT_EXISTING_MEAL_PLAN,
    CREATE_NEW_MEAL_PLAN,
)
from app.services.whatsapp.utils import (
    _set_if_expected,
    llm,
    _store_question_in_history,
    _update_last_answer_in_history,
    _store_system_message,
)
from app.services.whatsapp.client import (
    send_whatsapp_message,
    _send_whatsapp_buttons,
    _send_whatsapp_list,
)
from app.services.whatsapp.messages import remove_markdown
from app.services.crm.sessions import save_meal_plan, extract_gut_cleanse_meal_user_context, load_meal_plan

from app.services.prompts.gut_cleanse.meal import (
    generate_day_meal_plan,
    generate_complete_7day_meal_plan,
)

from app.services.prompts.gut_cleanse.meal_plan_template import (
    build_meal_plan_prompt,
    build_disclaimers,
    _remove_llm_disclaimers,
)
from app.services.chatbot.bugzy_gut_cleanse.nodes.user_verification_nodes import collect_health_safety_screening
logger = logging.getLogger(__name__)


def _gut_voice_owns_turn(state: State) -> bool:
    """Voice call active: skip duplicate WhatsApp promotion UI (no import cycle vs user_verification_nodes)."""
    return state.get("interaction_mode") == "voice" or state.get("voice_call_active") is True


# --- MEAL PLAN COLLECTION NODES ---
def ask_meal_plan_preference(state: State) -> State:
    """Node: Ask if user wants a meal plan."""
    # Store previous answer if coming from medications
    if state.get("user_msg"):
        _update_last_answer_in_history(state, state["user_msg"])

    # Skip educational hook and shorten question when re-asking after invalid input (router already sent error)
    reasking = state.get("meal_plan_preference_question_sent") is True
    if not reasking:
        message1 = "Did you know? 🧠\n70% of detox success depends on what you eat DURING the cleanse!"
        send_whatsapp_message(state["user_id"], message1)
        _store_system_message(state, message1)

    question = (
        "Want a personalized detox meal plan?"
        if reasking
        else (
            "Want a personalized detox meal plan?\n\n"
            "It'll guide you on:\n"
            "✅ What to eat each day\n"
            "✅ Foods that support cleansing\n"
            "✅ What to absolutely avoid\n"
            "✅ Easy gut-friendly recipes"
        )
    )

    _send_whatsapp_buttons(
        state["user_id"],
        question,
        [
            {"type": "reply", "reply": {"id": "create_meal_plan", "title": "Create plan 🍴"}},
            {"type": "reply", "reply": {"id": "has_meal_plan", "title": "Already have one 📋"}},
            {"type": "reply", "reply": {"id": "no_meal_plan", "title": "Not now"}},
        ]
    )
    
    # Store question in history
    full_question = question if reasking else f"Did you know? 🧠\n70% of detox success depends on what you eat DURING the cleanse!\n\n{question}"
    _store_question_in_history(state, full_question, "ask_meal_plan_preference")
    
    state["last_question"] = "ask_meal_plan_preference"
    state["pending_node"] = "ask_meal_plan_preference"
    state["meal_plan_preference_question_sent"] = True
    return state


def voice_agent_promotion_meal(state: State) -> State:
    """Node: Present choice between chat and voice agent meal planning."""
    from app.services.whatsapp.client import _send_whatsapp_call_button

    if _gut_voice_owns_turn(state):
        state["voice_agent_promotion_shown"] = True
        state.setdefault("voice_agent_context", "meal_planning")
        state["last_question"] = "voice_agent_promotion_meal"
        state["pending_node"] = "handle_voice_agent_choice_meal"
        if state.get("user_id"):
            from app.services.crm.sessions import save_session_to_file
            save_session_to_file(state["user_id"], state)
        return state

    benefits_message = (
        "Great! You can create your meal plan in two ways:\n\n"
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
    
    state["last_question"] = "voice_agent_promotion_meal"
    state["pending_node"] = "handle_voice_agent_choice_meal"
    state["voice_agent_promotion_shown"] = True
    state["voice_agent_context"] = "meal_planning"

    if state.get("user_id"):
        from app.services.crm.sessions import save_session_to_file
        save_session_to_file(state["user_id"], state)
    
    return state



def ask_existing_meal_plan_choice(state: State) -> State:
    """Node: Ask whether to edit existing plan or create a new one."""
    if state.get("user_msg"):
        _update_last_answer_in_history(state, state["user_msg"])

    question = (
        "It looks like you already have a meal plan.\n\n*✏️ Edit Day* to modify a specific day\n*🆕 New Plan* to start fresh with new questions"
    )

    _send_whatsapp_buttons(
        state["user_id"],
        question,
        [
            {
                "type": "reply",
                "reply": {"id": EDIT_EXISTING_MEAL_PLAN, "title": "✏️ Edit Existing Plan"},
            },
            {
                "type": "reply",
                "reply": {"id": CREATE_NEW_MEAL_PLAN, "title": "🆕 Create New Plan"},
            },
        ],
    )

    _store_question_in_history(state, question, "existing_meal_plan_choice")

    state["last_question"] = "existing_meal_plan_choice"
    state["pending_node"] = "ask_existing_meal_plan_choice"
    return state


def load_existing_meal_plan_for_edit(state: State) -> State:
    """Node: Load an existing meal plan and start the edit flow."""
    user_id = state["user_id"]
    meal_plan_data = state.get("existing_meal_plan_data") or load_meal_plan(user_id) or {}

    if not meal_plan_data:
        send_whatsapp_message(
            user_id,
            "I couldn't find your existing meal plan. Let's start a new one.",
        )
        return collect_health_safety_screening(state)

    for day_num in range(1, 8):
        key = f"meal_day{day_num}_plan"
        if meal_plan_data.get(key):
            state[key] = meal_plan_data[key]

    if meal_plan_data.get("meal_plan"):
        state["meal_plan"] = meal_plan_data["meal_plan"]

    sections = [
        {
            "title": "📅 Select Day to Edit",
            "rows": [
                {"id": f"edit_meal_day{i}", "title": f"Day {i}", "description": f"Edit Day {i} meal plan"}
                for i in range(1, 8)
            ],
        }
    ]

    _send_whatsapp_list(
        user_id=user_id,
        body_text="Which day's meal plan would you like to edit?",
        button_text="Select Day 📅",
        sections=sections,
        header_text="Edit Meal Plan",
    )

    state["edit_mode"] = "meal"
    state["last_question"] = "select_meal_day_to_edit"
    state["pending_node"] = "handle_meal_day_selection_for_edit"
    return state





# --- NEW 11-QUESTION MEAL PLAN FLOW ---

def collect_dietary_preference(state: State) -> State:
    """Node: Q1 - Collect dietary preference."""
    # Capture detox experience/reason if coming from profiling
    last_q = state.get("last_question")
    msg = (state.get("user_msg") or "").lower()
    msg_id = state.get("user_msg", "")
    
    if last_q == "detox_experience":
        if "no" in msg or "first" in msg or "detox_exp_no" in msg_id:
             state["detox_experience"] = "no"
             _update_last_answer_in_history(state, "No, first time")
        elif "long" in msg or "ago" in msg or "detox_exp_long_ago" in msg_id:
             state["detox_experience"] = "long_ago"
             _update_last_answer_in_history(state, "Yes, but long ago")
        # Mark profiling as explicitly collected since we finished the flow
        state["profiling_collected"] = True
             
    elif last_q == "detox_recent_reason":
         if "incomplete" in msg or "finish" in msg or "detox_reason_incomplete" in msg_id:
            state["detox_recent_reason"] = "incomplete"
            _update_last_answer_in_history(state, "Didn't finish")
         elif "results" in msg or "detox_reason_no_results" in msg_id:
            state["detox_recent_reason"] = "no_results"
            _update_last_answer_in_history(state, "No results")
         elif "symptoms" in msg or "back" in msg or "detox_reason_symptoms_back" in msg_id:
            state["detox_recent_reason"] = "symptoms_back"
            _update_last_answer_in_history(state, "Symptoms back")
         elif "maintenance" in msg or "detox_reason_maintenance" in msg_id:
            state["detox_recent_reason"] = "maintenance"
            _update_last_answer_in_history(state, "Maintenance")
         # Mark profiling as explicitly collected since we finished the flow
         state["profiling_collected"] = True

    # Store medications from user_msg (if coming from medications)
    if state.get("user_msg") and state.get("last_question") == "medications":
        _set_if_expected(state, "medications", "medications")
        _update_last_answer_in_history(state, state["user_msg"])

    _set_if_expected(state, "dietary_preference", "dietary_preference")

    dietary = (state.get("dietary_preference") or "").strip()
    if dietary:
        state["last_question"] = "dietary_preference"
        return collect_cuisine_preference(state)

    # CRITICAL: Re-establish ALL recreation flags if this is a recreation from post_plan_qna
    # Router sets these in memory, but we MUST set them in NODE to persist to database
    if state.get("existing_meal_plan_choice_origin") == "post_plan_qna":
        state["journey_restart_mode"] = True
        state["current_agent"] = "meal"  # Must persist agent change
        state["meal_plan_sent"] = False  # Must clear old plan flag
        logger.info("🔄 NODE: Re-established recreation flags (journey_restart_mode=True, current_agent=meal, meal_plan_sent=False)")

    question = "🌈 Let's start with the basics\n\n🥗 What's your dietary preference?"

    is_voice = state.get("interaction_mode") == "voice"
    if is_voice:
        from app.services.chatbot.bugzy_gut_cleanse.voice_questions import VOICE_QUESTIONS
        question = VOICE_QUESTIONS.get("dietary_preference", question)
        state.setdefault("messages", []).append({"role": "assistant", "content": question})
    else:
        _send_whatsapp_list(
            state["user_id"],
            question,
            "Your Eating Styles 🍴",
            [
                {
                    "title": "🍴 Dietary Preferences",
                    "rows": [
                        {"id": "diet_non_veg", "title": "🍗 Non-Vegetarian", "description": "Includes all food groups including meat"},
                        {"id": "diet_pure_veg", "title": "🥛 Pure Vegetarian", "description": "No meat, no seafood, no eggs; includes dairy"},
                        {"id": "diet_eggitarian", "title": "🥚 Eggitarian", "description": "No meat, no seafood; includes dairy and eggs"},
                        {"id": "diet_vegan", "title": "🌱 Vegan", "description": "No animal products at all"},
                        {"id": "diet_pescatarian", "title": "🐟 Pescatarian", "description": "Vegetarian diet plus seafood"},
                        {"id": "diet_flexitarian", "title": "🥦 Flexitarian", "description": "Mostly plant-based with occasional meat"},
                        {"id": "diet_keto", "title": "🥩 Keto", "description": "Low-carb, high-fat diet"}
                    ]
                }
            ],
            header_text="Dietary Preference"
        )

    _store_question_in_history(state, question, "dietary_preference")
    
    state["last_question"] = "dietary_preference"
    state["pending_node"] = "collect_dietary_preference"
    return state


def collect_cuisine_preference(state: State) -> State:
    """Node: Q2 - Collect cuisine preference."""
    _set_if_expected(state, "dietary_preference", "dietary_preference")
    _set_if_expected(state, "cuisine_preference", "cuisine_preference")

    if state.get("user_msg"):
        _update_last_answer_in_history(state, state["user_msg"])

    cuisine = (state.get("cuisine_preference") or "").strip()
    if cuisine:
        state["last_question"] = "cuisine_preference"
        return collect_food_allergies_intolerances(state)

    question = "✨ Nice going! We're just a step away from wrapping this up\n\n🍛 Do you have any cuisine preferences?"
    
    is_voice = state.get("interaction_mode") == "voice"
    if is_voice:
        from app.services.chatbot.bugzy_gut_cleanse.voice_questions import VOICE_QUESTIONS
        question = VOICE_QUESTIONS.get("cuisine_preference", question)
        state.setdefault("messages", []).append({"role": "assistant", "content": question})
    else:
        _send_whatsapp_list(
            state["user_id"],
            question,
            "Your Cravings 🍲",
            [
                {
                    "title": "🇮🇳 Indian Cuisines",
                    "rows": [
                        {"id": "cuisine_north_indian", "title": "🍛 North Indian", "description": "Roti, paneer, curry dishes"},
                        {"id": "cuisine_south_indian", "title": "🍚 South Indian", "description": "Dosa, idli, sambhar, rasam"},
                        {"id": "cuisine_gujarati", "title": "🥗 Gujarati", "description": "Dhokla, thepla, khandvi"},
                        {"id": "cuisine_bengali", "title": "🐟 Bengali", "description": "Fish curry, mishti doi, rasgulla"}
                    ]
                },
                {
                    "title": "🌍 International Cuisines",
                    "rows": [
                        {"id": "cuisine_chinese", "title": "🥢 Chinese", "description": "Noodles, stir-fry, dim sum"},
                        {"id": "cuisine_italian", "title": "🍝 Italian", "description": "Pasta, pizza, risotto"},
                        {"id": "cuisine_mexican", "title": "🌮 Mexican", "description": "Tacos, burritos, guacamole"},
                        {"id": "cuisine_all", "title": "🍽️ All cuisines", "description": "No specific preference"}
                    ]
                }
            ],
            header_text="Cuisine Preferences"
        )

    _store_question_in_history(state, question, "cuisine_preference")

    state["last_question"] = "cuisine_preference"
    state["pending_node"] = "collect_cuisine_preference"
    return state


def collect_food_allergies_intolerances(state: State) -> State:
    """Node: Q4 - Collect food allergies or intolerances."""
    _set_if_expected(state, "cuisine_preference", "cuisine_preference")
    _set_if_expected(state, "food_allergies_intolerances", "food_allergies_intolerances")

    if state.get("user_msg"):
        _update_last_answer_in_history(state, state["user_msg"])

    allergies = (state.get("food_allergies_intolerances") or "").strip()
    if allergies:
        state["last_question"] = "food_allergies_intolerances"
        return collect_daily_eating_pattern(state)

    question = "🔒 Before I finalize this\n\n🚫 Do you have any food allergies or intolerances?"
    
    is_voice = state.get("interaction_mode") == "voice"
    if is_voice:
        from app.services.chatbot.bugzy_gut_cleanse.voice_questions import VOICE_QUESTIONS
        question = VOICE_QUESTIONS.get("food_allergies_intolerances", question)
        state.setdefault("messages", []).append({"role": "assistant", "content": question})
    else:
        _send_whatsapp_list(
            state["user_id"],
            question,
            "Tummy Trouble List 😅",
            [
                {
                    "title": "🚨 Allergies",
                    "rows": [
                        {"id": "allergy_none", "title": "No allergies", "description": "No food allergies"},
                        {"id": "allergy_dairy", "title": "Dairy allergy", "description": "All dairy strictly avoided"},
                        {"id": "allergy_gluten", "title": "Gluten allergy", "description": "All gluten/wheat strictly avoided"},
                        {"id": "allergy_nuts", "title": "Nut allergy", "description": "All nuts strictly avoided"},
                        {"id": "allergy_eggs", "title": "Egg allergy", "description": "All eggs strictly avoided"},
                        {"id": "allergy_multiple", "title": "Multiple allergies", "description": "More than one allergy(type them)"}
                    ]
                },
                {
                    "title": "⚠️ Intolerances",
                    "rows": [
                        {"id": "intolerance_lactose", "title": "Lactose intolerant", "description": "Can have yogurt/curd, not milk"},
                        {"id": "intolerance_gluten", "title": "Gluten sensitive", "description": "Reduced gluten flexibility"},
                        {"id": "intolerance_spicy", "title": "Spice intolerant", "description": "Prefer mild foods"},
                        {"id": "intolerance_multiple", "title": "Multiple intolerances", "description": "More than one intolerance(type them)"}
                    ]
                }
            ],
            header_text="Allergies and Intolerances"
        )
    
    _store_question_in_history(state, question, "food_allergies_intolerances")
    
    state["last_question"] = "food_allergies_intolerances"
    state["pending_node"] = "collect_food_allergies_intolerances"
    return state


def collect_daily_eating_pattern(state: State) -> State:
    """Node: Q5 - Collect daily eating pattern."""
    _set_if_expected(state, "food_allergies_intolerances", "food_allergies_intolerances")
    _set_if_expected(state, "daily_eating_pattern", "daily_eating_pattern")

    if state.get("user_msg"):
        _update_last_answer_in_history(state, state["user_msg"])

    pattern = (state.get("daily_eating_pattern") or "").strip()
    if pattern:
        state["last_question"] = "daily_eating_pattern"
        return collect_foods_avoid(state)

    question = "🍽️ What do you usually eat throughout the day?\n\nShare any 3 dishes 😋"
    is_voice = state.get("interaction_mode") == "voice"
    if is_voice:
        from app.services.chatbot.bugzy_gut_cleanse.voice_questions import VOICE_QUESTIONS
        question = VOICE_QUESTIONS.get("daily_eating_pattern", question)
        state.setdefault("messages", []).append({"role": "assistant", "content": question})
    else:
        send_whatsapp_message(state["user_id"], question)
    
    _store_question_in_history(state, question, "daily_eating_pattern")
    
    state["last_question"] = "daily_eating_pattern"
    state["pending_node"] = "collect_daily_eating_pattern"
    return state


def collect_foods_avoid(state: State) -> State:
    """Node: Q6 - Collect foods user avoids."""
    _set_if_expected(state, "daily_eating_pattern", "daily_eating_pattern")
    _set_if_expected(state, "foods_avoid", "foods_avoid")

    if state.get("user_msg"):
        _update_last_answer_in_history(state, state["user_msg"])

    avoid = (state.get("foods_avoid") or "").strip()
    if avoid is not None and avoid != "":
        state["last_question"] = "foods_avoid"
        return collect_supplements(state)

    question = "🚨 Any foods you absolutely avoid or dislike?\n\n*Note:* Type None if no restrictions"
    is_voice = state.get("interaction_mode") == "voice"
    if is_voice:
        from app.services.chatbot.bugzy_gut_cleanse.voice_questions import VOICE_QUESTIONS
        question = VOICE_QUESTIONS.get("foods_avoid", question)
        state.setdefault("messages", []).append({"role": "assistant", "content": question})
    else:
        send_whatsapp_message(state["user_id"], question)
    
    _store_question_in_history(state, question, "foods_avoid")
    
    state["last_question"] = "foods_avoid"
    state["pending_node"] = "collect_foods_avoid"
    return state


def collect_supplements(state: State) -> State:
    """Node: Q7 - Collect supplements information."""
    _set_if_expected(state, "foods_avoid", "foods_avoid")
    _set_if_expected(state, "supplements", "supplements")

    if state.get("user_msg"):
        _update_last_answer_in_history(state, state["user_msg"])

    supps = (state.get("supplements") or "").strip()
    if supps is not None and supps != "":
        state["last_question"] = "supplements"
        return collect_digestive_issues(state)

    question = "💊 Are you currently taking any supplements?\n\n*Example:* Multivitamin, vitamin D, protein powder"
    is_voice = state.get("interaction_mode") == "voice"
    if is_voice:
        from app.services.chatbot.bugzy_gut_cleanse.voice_questions import VOICE_QUESTIONS
        question = VOICE_QUESTIONS.get("supplements", question)
        state.setdefault("messages", []).append({"role": "assistant", "content": question})
    else:
        send_whatsapp_message(state["user_id"], question)
    
    _store_question_in_history(state, question, "supplements")
    
    state["last_question"] = "supplements"
    state["pending_node"] = "collect_supplements"
    return state


def collect_digestive_issues(state: State) -> State:
    """Node: Q8 - Collect digestive issues with follow-up message."""
    _set_if_expected(state, "supplements", "supplements")
    _set_if_expected(state, "digestive_issues", "digestive_issues")

    if state.get("user_msg"):
        _update_last_answer_in_history(state, state["user_msg"])

    digestive = (state.get("digestive_issues") or "").strip()
    if digestive:
        state["last_question"] = "digestive_issues"
        return collect_hydration(state)

    question = "🤍 Before we go further, let's quickly check in on your digestion. I want this plan to feel gentle and supportive for your gut.\n\n💩 Do you experience any of these digestive issues?"
    
    is_voice = state.get("interaction_mode") == "voice"
    if is_voice:
        from app.services.chatbot.bugzy_gut_cleanse.voice_questions import VOICE_QUESTIONS
        question = VOICE_QUESTIONS.get("digestive_issues", question)
        state.setdefault("messages", []).append({"role": "assistant", "content": question})
    else:
        _send_whatsapp_list(
            state["user_id"],
            question,
            "Gut Health Check 🦠",
            [
                {
                    "title": "💩 Digestive Issues",
                    "rows": [
                        {"id": "digestive_none", "title": "None currently ✅", "description": "No digestive issues"},
                        {"id": "digestive_bloating", "title": "Bloating 🎈", "description": "Feel swollen/gassy"},
                        {"id": "digestive_constipation", "title": "Constipation 🚽", "description": "Difficulty passing stools"},
                        {"id": "digestive_acidity", "title": "Acidity or heartburn 🔥", "description": "Acid reflux or heartburn"},
                        {"id": "digestive_gas", "title": "Gas 💨", "description": "Excessive gas"},
                        {"id": "digestive_irregular", "title": "Irregular bowels 🔄", "description": "Inconsistent bowel movements"},
                        {"id": "digestive_heavy", "title": "Heavy/slow digestion 😓", "description": "Feel weighed down after meals"},
                        {"id": "digestive_sugar", "title": "Sugar cravings 🍫", "description": "Strong sugar cravings"}
                    ]
                }
            ],
            header_text="Digestive Issues"
        )
    
    _store_question_in_history(state, question, "digestive_issues")
    
    state["last_question"] = "digestive_issues"
    state["pending_node"] = "collect_digestive_issues"
    return state


def collect_hydration(state: State) -> State:
    """Node: Q9 - Collect hydration information."""
    _set_if_expected(state, "digestive_issues", "digestive_issues")
    _set_if_expected(state, "hydration", "hydration")

    if state.get("user_msg"):
        _update_last_answer_in_history(state, state["user_msg"])
        is_resuming = state.get("last_question") in ["resuming_from_health_qna", "resuming_from_product_qna", "resuming_from_snap"]
        digestive_value = state.get("digestive_issues", "").strip().lower()
        if not is_resuming and digestive_value and "digestive_none" not in digestive_value and "none currently" not in digestive_value:
            follow_up = (
                "Got it 💚 I'll track these throughout your journey.\n\n"
                "By Day 14, clinical studies show:\n"
                "• 70% less bloating\n"
                "• 79% relief from constipation\n"
                "• 75% less acidity\n\n"
                "I'll check in regularly to track your progress 📊"
            )
            send_whatsapp_message(state["user_id"], follow_up)
            _store_system_message(state, follow_up)

    hydration_val = (state.get("hydration") or "").strip()
    if hydration_val:
        state["last_question"] = "hydration"
        return collect_other_beverages(state)

    question = "💧 Now let's talk hydration. During detox, staying well hydrated helps your body flush toxins and keeps your energy steady.\n\nRoughly how much water do you drink in a day?"
    
    is_voice = state.get("interaction_mode") == "voice"
    if is_voice:
        from app.services.chatbot.bugzy_gut_cleanse.voice_questions import VOICE_QUESTIONS
        question = VOICE_QUESTIONS.get("hydration", question)
        state.setdefault("messages", []).append({"role": "assistant", "content": question})
    else:
        _send_whatsapp_list(
            state["user_id"],
            question,
            "Daily Hydration 💧",
            [
                {
                    "title": "💧 Water Intake",
                    "rows": [
                        {"id": "hydration_less_1l", "title": "💧 Less than 1L", "description": "Minimal daily water intake"},
                        {"id": "hydration_1_2l", "title": "💦 1–2 liters", "description": "Moderate daily hydration"},
                        {"id": "hydration_2_3l", "title": "💙 2–3 liters", "description": "Good daily hydration"},
                        {"id": "hydration_more_3l", "title": "🌊 More than 3L", "description": "Excellent daily hydration"}
                    ]
                }
            ],
            header_text="Hydration Level"
        )
    
    _store_question_in_history(state, question, "hydration")
    
    state["last_question"] = "hydration"
    state["pending_node"] = "collect_hydration"
    return state


def collect_other_beverages(state: State) -> State:
    """Node: Q10 - Collect other beverages with follow-up logic."""
    _set_if_expected(state, "hydration", "hydration")
    _set_if_expected(state, "other_beverages", "other_beverages")

    if state.get("user_msg"):
        _update_last_answer_in_history(state, state["user_msg"])

    beverages = (state.get("other_beverages") or "").strip()
    if beverages:
        state["last_question"] = "other_beverages"
        return collect_gut_sensitivity(state)

    question = "☕ One last lifestyle check before we move ahead. Your beverage habits can strongly influence how effective the cleanse feels.\n\nHow many cups of tea/coffee/other beverages do you have daily?"
    
    is_voice = state.get("interaction_mode") == "voice"
    if is_voice:
        from app.services.chatbot.bugzy_gut_cleanse.voice_questions import VOICE_QUESTIONS
        question = VOICE_QUESTIONS.get("other_beverages", question)
        state.setdefault("messages", []).append({"role": "assistant", "content": question})
    else:
        _send_whatsapp_list(
            state["user_id"],
            question,
            "Beverage Habits ☕",
            [
                {
                    "title": "☕ Daily Beverages",
                    "rows": [
                        {"id": "beverages_none", "title": "☕ None", "description": "Water only, no caffeine drinks"},
                        {"id": "beverages_1_2", "title": "☕ 1–2 cups", "description": "Light tea/coffee intake"},
                        {"id": "beverages_3_4", "title": "☕ 3–4 cups", "description": "Moderate tea/coffee intake"},
                        {"id": "beverages_5_plus", "title": "☕ 5+ cups", "description": "Heavy tea/coffee intake"}
                    ]
                }
            ],
            header_text="Beverage Intake"
        )
    
    _store_question_in_history(state, question, "other_beverages")
    
    state["last_question"] = "other_beverages"
    state["pending_node"] = "collect_other_beverages"
    return state


def collect_gut_sensitivity(state: State) -> State:
    """Node: Q11 - Collect gut sensitivity (final question)."""
    _set_if_expected(state, "other_beverages", "other_beverages")
    _set_if_expected(state, "gut_sensitivity", "gut_sensitivity")

    if state.get("user_msg"):
        _update_last_answer_in_history(state, state["user_msg"])
        is_resuming = state.get("last_question") in ["resuming_from_health_qna", "resuming_from_product_qna", "resuming_from_snap"]
        beverages_value = state.get("other_beverages", "").strip().lower()
        if not is_resuming and beverages_value:
            FOLLOW_UPS: list[tuple[tuple[str, ...], str]] = [
                (("beverages_none", "none"), "That's wonderful! 🌟 You're already setting yourself up beautifully for this journey."),
                (("beverages_1_2", "1-2", "1–2"), "I hear you ☕ Just so you know, we'll gently pause these during the cleanse to help your body reset.\n\nI know it might feel like a shift, but many find they sleep better and feel more energized once they adjust 💚"),
                (("beverages_3_4", "3-4", "3–4"), "I totally get it—tea and coffee can be such comforting rituals ☕ During the cleanse, we'll need to take a complete break from these.\n\nIt might feel challenging at first, but I'll be here to support you through any withdrawal headaches or fatigue.\nMost people feel so much lighter by day 3-4 💙"),
                (("beverages_5_plus", "5+", "5–plus"), "That's quite a bit of caffeine ☕ I want to be honest with you—pausing all of these will be essential for the cleanse to work its magic.\n\nThe first few days might be tough (hello, headaches! 😅), but your energy will stabilize and you'll likely feel clearer than you have in ages.\nI'm here for you every step of the way 🤍"),
            ]
            for keywords, msg in FOLLOW_UPS:
                if any(k in beverages_value for k in keywords):
                    send_whatsapp_message(state["user_id"], msg)
                    _store_system_message(state, msg)
                    break

    sensitivity = (state.get("gut_sensitivity") or "").strip()
    if sensitivity:
        state["last_question"] = "gut_sensitivity"
        return generate_meal_plan(state)

    question = "🌿 Almost there. One last thing to help fine-tune your meals.\n\nHow sensitive is your stomach?"
    
    is_voice = state.get("interaction_mode") == "voice"
    if is_voice:
        from app.services.chatbot.bugzy_gut_cleanse.voice_questions import VOICE_QUESTIONS
        question = VOICE_QUESTIONS.get("gut_sensitivity", question)
        state.setdefault("messages", []).append({"role": "assistant", "content": question})
    else:
        _send_whatsapp_list(
            state["user_id"],
            question,
            "Gut Comfort 🌿",
            [
                {
                    "title": "🌿 Sensitivity Level",
                    "rows": [
                        {"id": "sensitivity_very", "title": "😣 Very sensitive", "description": "Easily upset, needs gentle foods"},
                        {"id": "sensitivity_moderate", "title": "😐 Moderate", "description": "Sometimes reactive to certain foods"},
                        {"id": "sensitivity_not", "title": "💪 Not sensitive", "description": "Strong digestion, handles most foods"}
                    ]
                }
            ],
            header_text="Gut Sensitivity"
        )
    
    _store_question_in_history(state, question, "gut_sensitivity")
    
    state["last_question"] = "gut_sensitivity"
    state["pending_node"] = "collect_gut_sensitivity"
    return state



def generate_meal_plan(state: State) -> State:
    """Node: Generate Day 1 meal plan using LLM."""
    # Store gut sensitivity from user_msg (final question)
    _set_if_expected(state, "gut_sensitivity", "gut_sensitivity")

    # Update the previous question's answer
    if state.get("user_msg"):
        _update_last_answer_in_history(state, state["user_msg"])

    is_voice = state.get("interaction_mode") == "voice"

    # Only send progress messages to WhatsApp chat (voice: generate silently, plan sent post-call)
    if not is_voice:
        send_whatsapp_message(state["user_id"], "✨ Thank you for sharing all that with me! Give me a moment to create your personalized 7-day meal plan...")
        time.sleep(1)
        send_whatsapp_message(state["user_id"], "🍽️ Generating Day 1 Plan...")

    logger.info("Generating Day 1 Plan...")
    # Generate Day 1 meal plan
    meal_plan = generate_day_meal_plan(state, 1)

    state["meal_day1_plan"] = meal_plan

    # Mark meal profiling as collected
    state["profiling_collected_in_meal"] = True

    save_meal_plan(state["user_id"], {
        "meal_day1_plan": meal_plan,
        "user_context": extract_gut_cleanse_meal_user_context(state)
    }, product="gut_cleanse")

    if is_voice:
        # Voice: flag the plan for post-call WhatsApp delivery (same as AMS)
        # The livekit_agent's _send_plan_to_node sends the plan + Make Changes/7-Day Plan buttons after the call
        state["meal_plan"] = meal_plan
        state["fresh_meal_plan"] = True
        closing = "Your personalized Day 1 meal plan is ready. I'm sending it to you on WhatsApp now. Have a great day! <<END_CALL>>"
        state.setdefault("messages", []).append({"role": "assistant", "content": closing})
    else:
        # Chat: send the plan and choice buttons directly
        send_whatsapp_message(state["user_id"], meal_plan)
        _send_whatsapp_buttons(
            state["user_id"],
            "What would you like to do next?",
            [
                {"type": "reply", "reply": {"id": "make_changes_meal_day1", "title": "✏️ Make Changes"}},
                {"type": "reply", "reply": {"id": "continue_7day_meal", "title": "✅ 7-Day Plan"}},
            ]
        )
    state["last_question"] = "meal_day1_plan_review"
    return state




# --- MEAL PLAN DAY 1 REVIEW & REVISION NODES ---
def handle_meal_day1_review_choice(state: State) -> State:
    """Node: Handle user's choice after Day 1 meal plan generation."""
    user_msg = state.get("user_msg", "").strip()
    user_msg_lower = user_msg.lower()
    
    logger.debug("handle_meal_day1_review_choice: user_msg='%s' (len=%d, repr=%r)", user_msg, len(user_msg), user_msg)
    
    # Guard: If no user message, just wait (don't send "didn't catch that" message)
    if not user_msg:
        logger.debug("No user message yet, waiting for button click...")
        return state
    
    # More flexible button detection - check for key phrases and emojis
    is_make_changes = (
        # Direct button references
        "make changes" in user_msg_lower or
        "make_changes_meal_day1" in user_msg_lower or
        # Soft Review Options (Change)
        "rev_almost" in user_msg_lower or
        "rev_tweak" in user_msg_lower or
        "rev_change" in user_msg_lower or

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
        # Direct button references
        "continue" in user_msg_lower or
        "continue_7day_meal" in user_msg_lower or
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
        
        # Plan references
        "7-day plan" in user_msg_lower or
        "7 day plan" in user_msg_lower or
        "7day plan" in user_msg_lower or
        "7 days plan" in user_msg_lower or
        "seven day plan" in user_msg_lower or
        "seven-day plan" in user_msg_lower or
        "weekly plan" in user_msg_lower or
        "full plan" in user_msg_lower or
        "complete plan" in user_msg_lower or
        "entire plan" in user_msg_lower or
        
        # Action phrases
        "generate 7-day" in user_msg_lower or
        "generate 7 day" in user_msg_lower or
        "create 7-day" in user_msg_lower or
        "show me 7-day" in user_msg_lower or
        "give me 7-day" in user_msg_lower or
        "proceed" in user_msg_lower or
        "go ahead" in user_msg_lower or
        "next" in user_msg_lower or
        "yes" in user_msg_lower or
        "yep" in user_msg_lower or
        "yeah" in user_msg_lower or
        "yup" in user_msg_lower or
        "ok" in user_msg_lower or
        "okay" in user_msg_lower or
        "sure" in user_msg_lower or
        "good" in user_msg_lower or
        "looks good" in user_msg_lower or
        "sounds good" in user_msg_lower or
        "perfect" in user_msg_lower or
        "approved" in user_msg_lower or
        "accept" in user_msg_lower or
        
        # Emoji variations
        "✅" in user_msg or
        "✓" in user_msg or
        "☑️" in user_msg or
        "☑" in user_msg or
        "👍" in user_msg or  # thumbs up
        "👍🏻" in user_msg or
        "👍🏼" in user_msg or
        "👍🏽" in user_msg or
        "👍🏾" in user_msg or
        "👍🏿" in user_msg or
        "🆗" in user_msg or  # OK button
        "▶️" in user_msg or  # play button
        "▶" in user_msg or
        "➡️" in user_msg or  # right arrow
        "➡" in user_msg or
        "⏭️" in user_msg or  # next track
        "⏭" in user_msg or
        
        # Starting patterns
        user_msg_lower.startswith("✅") or
        user_msg_lower.startswith("✓") or
        user_msg_lower.startswith("yes") or
        user_msg_lower.startswith("continue") or
        user_msg_lower.startswith("proceed") or
        user_msg_lower.startswith("next")
    )
    
    logger.debug("is_make_changes=%s, is_continue=%s", is_make_changes, is_continue)
    
    is_voice = state.get("interaction_mode") == "voice"
    if is_make_changes:
        if is_voice:
            from app.services.chatbot.bugzy_gut_cleanse.voice_questions import VOICE_QUESTIONS
            prompt = VOICE_QUESTIONS.get("meal_day1_changes_prompt", "What changes would you like to make to Day 1?")
            state.setdefault("messages", []).append({"role": "assistant", "content": prompt})
        else:
            send_whatsapp_message(
                state["user_id"],
                "Got it! 📝 Please tell me what changes you'd like to make to your Day 1 meal plan.\n\nFor example:\n- \"Add more protein\"\n- \"Replace breakfast with something lighter\"\n- \"Include more vegetables\"\n- \"Less spicy food\""
            )
        state["last_question"] = "awaiting_meal_day1_changes"
        state["pending_node"] = "collect_meal_day1_changes"
    elif is_continue:
        if is_voice:
            from app.services.chatbot.bugzy_gut_cleanse.voice_questions import VOICE_QUESTIONS
            prompt = VOICE_QUESTIONS.get("meal_day1_continue", "Perfect! I'm generating your complete 7-day plan now. You'll receive it on WhatsApp shortly.")
            state.setdefault("messages", []).append({"role": "assistant", "content": prompt})
        else:
            send_whatsapp_message(
                state["user_id"],
                "Perfect! 🍽️ Let me generate the remaining 6 days of your personalized meal plan\nJust type in *OK* to continue..."
            )
            if state.get("interaction_mode") != "voice":
                time.sleep(1)
        state["last_question"] = "meal_day1_complete"
        state["pending_node"] = "generate_all_remaining_meal_days"
    else:
        logger.warning("Unclear user input: '%s'", user_msg)
        if is_voice:
            from app.services.chatbot.bugzy_gut_cleanse.voice_questions import VOICE_QUESTIONS
            prompt = VOICE_QUESTIONS.get("meal_day1_review", "Would you like to make changes or continue with your 7-day plan?")
            state.setdefault("messages", []).append({"role": "assistant", "content": prompt})
        else:
            _send_whatsapp_buttons(
                state["user_id"],
                "Lets get back to the meal plan. what Would you like to:",
                [
                    {"type": "reply", "reply": {"id": "more_changes_meal_day1", "title": "✏️ Make Changes"}},
                    {"type": "reply", "reply": {"id": "continue_7day_meal", "title": "✅ 7-Day Plan"}},
                ]
            )
        state["last_question"] = "meal_day1_plan_review"
    return state


def collect_meal_day1_changes(state: State) -> State:
    """Node: Collect user's requested changes for Day 1 meal plan."""
    user_msg = state.get("user_msg", "").strip()
    
    if not user_msg:
        send_whatsapp_message(
            state["user_id"],
            "I didn't get your changes. Please tell me what you'd like to modify in your Day 1 meal plan."
        )
        return state
    
    # Filter out simple acknowledgments (ok, yes, sure, etc.) - these are not actual change requests
    acknowledgments = ["ok", "okay", "yes", "yeah", "sure", "fine", "good", "alright", "k", "kk", "👍", "✓", "✔️"]
    if user_msg.lower() in acknowledgments:
        logger.debug("Ignoring acknowledgment message: '%s'", user_msg)
        # Don't regenerate, just wait for actual change request
        return state
    
    # Accumulate changes: append to existing change request if it exists
    # (API must NOT overwrite meal_day1_change_request for this flow so we keep previous changes)
    existing_changes = state.get("meal_day1_change_request", "").strip()
    if existing_changes:
        # Avoid duplicating if existing is exactly the current message (e.g. from API overwrite)
        if existing_changes.strip().lower() == user_msg.strip().lower():
            accumulated_changes = existing_changes
        else:
            # Combine previous changes with new change request
            state["meal_day1_change_request"] = f"{existing_changes}; {user_msg}"
            accumulated_changes = state["meal_day1_change_request"]
    else:
        # First change request
        state["meal_day1_change_request"] = user_msg
        accumulated_changes = user_msg
    
    is_voice = state.get("interaction_mode") == "voice"
    if is_voice:
        state.setdefault("messages", []).append({
            "role": "assistant",
            "content": "Got it! I'm updating Day 1 with your changes now."
        })
    else:
        send_whatsapp_message(
            state["user_id"],
            f"Got it! 🔄 Regenerating your Day 1 meal plan with all your changes: {accumulated_changes}\n\n⏳ One moment..."
        )
    return regenerate_meal_day1_plan(state)


def regenerate_meal_day1_plan(state: dict) -> dict:
    """
    Regenerate Day 1 meal plan based on user's feedback.
    Uses the unified template for consistent formatting.
    
    Args:
        state: User state dictionary (must contain 'meal_day1_change_request')
    
    Returns:
        Updated state dictionary
    """
    user_changes = state.get("meal_day1_change_request", "")
    old_day1_plan = state.get("meal_day1_plan", "")
    
    # Store old plan for reference
    if not state.get("old_meal_day1_plans"):
        state["old_meal_day1_plans"] = []
    state["old_meal_day1_plans"].append(old_day1_plan)
    
    # Build base prompt using unified template (with revision flag)
    prompt = build_meal_plan_prompt(
        state=state,
        day_number=1,
        previous_meals=None,
        day1_plan=None,
        change_request=user_changes,
        is_revision=True
    )
    
    # Format accumulated changes for clarity (split by semicolon if multiple)
    if ";" in user_changes:
        changes_list = [c.strip() for c in user_changes.split(";") if c.strip()]
        formatted_changes = "\n".join([f"• {change}" for change in changes_list])
        changes_header = "USER'S ACCUMULATED CHANGE REQUESTS (ALL must be applied):"
    else:
        formatted_changes = user_changes
        changes_header = "USER'S REQUESTED CHANGES:"
    
    # Add the old plan context and revision instructions to the prompt
    revision_context = f"""
═══════════════════════════════════════════════════════════════
🔄 REVISION MODE - DAY 1 REGENERATION
═══════════════════════════════════════════════════════════════

ORIGINAL DAY 1 PLAN THAT USER WANTS TO CHANGE:
{old_day1_plan}

{changes_header}
{formatted_changes}

REVISION INSTRUCTIONS:
1. Incorporate ALL of the user's requested changes listed above (if multiple, apply ALL of them)
2. Maintain the EXACT format from the template
3. Keep the same level of detail as the original plan
4. Ensure all required sections are present (snacks, gut health, etc.)
5. Keep the warm, supportive tone
6. If changes conflict with each other, prioritize the most recent one, but try to satisfy all when possible

"""
    
    # Combine revision context with the base prompt
    full_prompt = revision_context + prompt
    
    # Generate using LLM
    response = llm.invoke(full_prompt)
    revised_plan = response.content.strip()
    
    # Clean up any accidental disclaimers from LLM
    revised_plan = _remove_llm_disclaimers(revised_plan)
    
    # Add our standardized disclaimers
    disclaimers = build_disclaimers(state)
    if disclaimers:
        revised_plan = revised_plan.rstrip() + disclaimers
    
    # Remove markdown for WhatsApp
    revised_plan = remove_markdown(revised_plan)
    
    # Update state
    state["meal_day1_plan"] = revised_plan
    
    # Save to dedicated collection with old plans, change request, and user context
    meal_plan_data = {
        "meal_day1_plan": revised_plan,
        "old_meal_day1_plans": state.get("old_meal_day1_plans", []),
        "meal_day1_change_request": state.get("meal_day1_change_request", ""),
        "user_context": extract_gut_cleanse_meal_user_context(state)
    }
    # Increment change counter since this is a user-requested revision
    save_meal_plan(state["user_id"], meal_plan_data, product="gut_cleanse", increment_change_count=True)
    
    is_voice = state.get("interaction_mode") == "voice"
    send_whatsapp_message(state["user_id"], revised_plan)
    if is_voice:
        from app.services.chatbot.bugzy_gut_cleanse.voice_questions import VOICE_QUESTIONS
        prompt = VOICE_QUESTIONS.get("meal_day1_revised_review", "Would you like more changes or continue with your 7-day plan?")
        state.setdefault("messages", []).append({"role": "assistant", "content": prompt})
    else:
        _send_whatsapp_buttons(
            state["user_id"],
            "How about this version?",
            [
                {"type": "reply", "reply": {"id": "more_changes_meal_day1", "title": "✏️ More Changes"}},
                {"type": "reply", "reply": {"id": "continue_7day_meal", "title": "✅ 7-Day Plan"}},
            ]
        )
    state["last_question"] = "meal_day1_revised_review"
    state["pending_node"] = "handle_meal_day1_revised_review"
    return state


def handle_meal_day1_revised_review(state: State) -> State:
    """Node: Handle user's choice after Day 1 meal plan revision."""
    user_msg = state.get("user_msg", "").strip()
    user_msg_lower = user_msg.lower()
    
    logger.debug("handle_meal_day1_revised_review: user_msg='%s' (len=%d, repr=%r)", user_msg, len(user_msg), user_msg)
    
    # Guard: If no user message, just wait (don't send "didn't catch that" message)
    # This prevents the error message from appearing immediately after buttons are shown
    if not user_msg:
        logger.debug("No user message yet, waiting for button click...")
        return state
    
    # More flexible button detection - check for key phrases and emojis
    is_more_changes = (
        "more_changes_meal_day1" in user_msg_lower or 
        "more changes" in user_msg_lower or
        "make changes" in user_msg_lower or
        "additional changes" in user_msg_lower or
        "another change" in user_msg_lower or
        "more edits" in user_msg_lower or
        "keep editing" in user_msg_lower or
        "continue editing" in user_msg_lower or
        "add more" in user_msg_lower or
        "change more" in user_msg_lower or
        "edit more" in user_msg_lower or
        "modify more" in user_msg_lower or
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
        "something else" in user_msg_lower or
        "also change" in user_msg_lower or
        "also edit" in user_msg_lower or
        "also add" in user_msg_lower or
        "also remove" in user_msg_lower or
        "and change" in user_msg_lower or
        "and edit" in user_msg_lower or
        "and add" in user_msg_lower or
        "plus" in user_msg_lower or
        "still editing" in user_msg_lower or
        "not done" in user_msg_lower or
        "not finished" in user_msg_lower or
        "next change" in user_msg_lower or
        "next edit" in user_msg_lower or
        "i also want to" in user_msg_lower or
        "i'd also like to" in user_msg_lower or
        "i want to also" in user_msg_lower or
        "let me also" in user_msg_lower or
        "can i also" in user_msg_lower or
        
        # Emojis
        "✏️" in user_msg or
        "✏" in user_msg or  # pencil without variant selector
        "➕" in user_msg or  # plus sign
        "🔄" in user_msg or  # refresh
        "🔃" in user_msg or  # reload
        "➡️" in user_msg or  # next/continue
        "➡" in user_msg or
        "▶️" in user_msg or  # play/continue
        "▶" in user_msg or
        "👉" in user_msg or  # pointing right
        "⏭️" in user_msg or  # next track
        "⏭" in user_msg or
        
        # Starting patterns
        user_msg_lower.startswith("✏") or
        user_msg_lower.startswith("more") or
        user_msg_lower.startswith("add") or
        user_msg_lower.startswith("another") or
        user_msg_lower.startswith("also") or
        user_msg_lower.startswith("and") or
        user_msg_lower.startswith("plus") or
        user_msg_lower.startswith("keep") or
        user_msg_lower.startswith("still") or
        user_msg_lower.startswith("further") or
        user_msg_lower.startswith("additional") or
        user_msg_lower.startswith("extra") or
        user_msg_lower.startswith("other") or
        user_msg_lower.startswith("different") or
        user_msg_lower.startswith("one more") or
        user_msg_lower.startswith("i also")
    )
    
    is_continue = (
        "continue_7day_meal" in user_msg_lower or
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
    
    logger.debug("is_more_changes=%s, is_continue=%s", is_more_changes, is_continue)
    
    is_voice = state.get("interaction_mode") == "voice"
    if is_more_changes:
        if is_voice:
            from app.services.chatbot.bugzy_gut_cleanse.voice_questions import VOICE_QUESTIONS
            prompt = VOICE_QUESTIONS.get("meal_day1_changes_prompt", "What additional changes would you like?")
            state.setdefault("messages", []).append({"role": "assistant", "content": prompt})
        else:
            send_whatsapp_message(
                state["user_id"],
                "Sure! 📝 Tell me what additional changes you'd like to make to your Day 1 meal plan."
            )
        state["last_question"] = "awaiting_meal_day1_changes"
        state["pending_node"] = "collect_meal_day1_changes"
    elif is_continue:
        if is_voice:
            from app.services.chatbot.bugzy_gut_cleanse.voice_questions import VOICE_QUESTIONS
            prompt = VOICE_QUESTIONS.get("meal_day1_continue", "Perfect! I'm generating your complete 7-day plan now. You'll receive it on WhatsApp shortly.")
            state.setdefault("messages", []).append({"role": "assistant", "content": prompt})
        else:
            send_whatsapp_message(
                state["user_id"],
                "Excellent! 🍽️ Let me generate the remaining 6 days of your personalized meal plan\nJust type in *OK* to continue..."
            )
            if state.get("interaction_mode") != "voice":
                time.sleep(1)
        state["last_question"] = "meal_day1_complete"
        state["pending_node"] = "generate_all_remaining_meal_days"
    else:
        logger.warning("Unclear user input: '%s'", user_msg)
        if is_voice:
            from app.services.chatbot.bugzy_gut_cleanse.voice_questions import VOICE_QUESTIONS
            prompt = VOICE_QUESTIONS.get("meal_day1_revised_review", "Would you like more changes or continue with your 7-day plan?")
            state.setdefault("messages", []).append({"role": "assistant", "content": prompt})
        else:
            _send_whatsapp_buttons(
                state["user_id"],
                "Lets get back to the meal plan. what Would you like to:",
                [
                    {"type": "reply", "reply": {"id": "more_changes_meal_day1", "title": "✏️ More Changes"}},
                    {"type": "reply", "reply": {"id": "continue_7day_meal", "title": "✅ 7-Day Plan"}},
                ]
            )
        # Stay in same state to wait for clear input
        state["last_question"] = "meal_day1_revised_review"
    
    return state


# --- DAY-BY-DAY MEAL PLAN NODES ---
def generate_all_remaining_meal_days(state: State) -> State:
    """Node: Generate all remaining meal plans (Days 2-7) at once using single LLM call."""
    user_id = state["user_id"]
    
    # IMPORTANT: Change state immediately to prevent re-triggering
    state["last_question"] = "generating_remaining_meal_days"
    state["pending_node"] = None
    
    send_whatsapp_message(user_id, "🍽️ Generating your complete 6-day meal plan (Days 2-7)\nPlease wait...")
    if state.get("interaction_mode") != "voice":
        time.sleep(1)
    # Generate all days 2-7 in a single LLM call
    individual_days = generate_complete_7day_meal_plan(state)
    
    # Send each day plan as a message (without disclaimers)
    for day_key in ['meal_day2', 'meal_day3', 'meal_day4', 'meal_day5', 'meal_day6', 'meal_day7']:
        if day_key in individual_days:
            send_whatsapp_message(user_id, individual_days[day_key])
            if state.get("interaction_mode") != "voice":
                time.sleep(0.5)
    if 'disclaimers' in individual_days:
        send_whatsapp_message(user_id, individual_days['disclaimers'])
        if state.get("interaction_mode") != "voice":
            time.sleep(0.5)
    
    # Store individual days in state (excluding disclaimers key)
    for day_key, day_content in individual_days.items():
        if day_key != 'disclaimers':
            state[f"{day_key}_plan"] = day_content
    
    # Already sent days 2-7 above; skip sending the entire block again
    
    send_whatsapp_message(user_id, "🎉 Your complete 7-day meal plan has been generated!")
    if state.get("interaction_mode") == "voice":
        state.setdefault("messages", []).append({
            "role": "assistant",
            "content": "Your complete 7-day meal plan is ready on WhatsApp. Is there anything else you'd like help with?",
        })

    # Store the complete plan (including Day 1)
    complete_plan = "\n\n".join([individual_days.get(f'meal_day{i}', '') for i in range(2, 8)])  
    state["meal_plan"] = complete_plan
    state["meal_plan_sent"] = True
    
    # Check if this is a journey restart / recreation (user came from post_plan_qna and chose Create New Plan)
    # Re-establish journey_restart_mode so route_after_meal_plan_completion can END at post_plan_qna (not SNAP)
    if state.get("existing_meal_plan_choice_origin") == "post_plan_qna":
        state["journey_restart_mode"] = True
    if state.get("journey_restart_mode"):
        logger.info("Journey restart mode detected - meal plan complete, staying in post_plan_qna")
        state["last_question"] = "post_plan_qna"
        state["current_agent"] = "post_plan_qna"
    else:
        state["last_question"] = "meal_plan_complete"
    
    # Store combined days 2-7 for reference
    state["meal_days_2_7"] = complete_plan
    
    # Save complete meal plan to dedicated collection with user context
    meal_plan_data = {
        "meal_day1_plan": state.get("meal_day1_plan", ""),
        "meal_day2_plan": state.get("meal_day2_plan", ""),
        "meal_day3_plan": state.get("meal_day3_plan", ""),
        "meal_day4_plan": state.get("meal_day4_plan", ""),
        "meal_day5_plan": state.get("meal_day5_plan", ""),
        "meal_day6_plan": state.get("meal_day6_plan", ""),
        "meal_day7_plan": state.get("meal_day7_plan", ""),
        "meal_plan": state["meal_plan"],
        "meal_plan_sent": True,
        "user_context": extract_gut_cleanse_meal_user_context(state)
    }
    save_meal_plan(state["user_id"], meal_plan_data, product="gut_cleanse")
    
    return state


def generate_meal_day2_plan(state: State) -> State:
    """Node: Generate Day 2 meal plan."""
    send_whatsapp_message(state["user_id"], "🍽️ Generating Day 2 Plan...")
    state["meal_day2_plan"] = generate_day_meal_plan(state, 2)
    send_whatsapp_message(state["user_id"], state["meal_day2_plan"])
    _send_whatsapp_buttons(
        state["user_id"],
        "Let's continue!",
        [
            {"type": "reply", "reply": {"id": "yes_meal_day2", "title": "✅ Day 3"}},
        ]
    )
    state["last_question"] = "meal_day2_complete"
    return state


def generate_meal_day3_plan(state: State) -> State:
    """Node: Generate Day 3 meal plan."""
    # If resuming after image analysis, do not auto-generate. Ask for confirmation instead.
    if state.get("last_question") == "image_analysis_complete":
        _send_whatsapp_buttons(
            state["user_id"],
            "Shall I generate your Day 3 meal plan now?",
            [
                {"type": "reply", "reply": {"id": "yes_meal_day2", "title": "✅ Generate Day 3"}},
            ]
        )
        # Return to the prior step so the existing button flow triggers generation explicitly
        state["last_question"] = "meal_day2_complete"
        return state
    send_whatsapp_message(state["user_id"], "🍽️ Generating Day 3 Plan...")
    state["meal_day3_plan"] = generate_day_meal_plan(state, 3)
    send_whatsapp_message(state["user_id"], state["meal_day3_plan"])
    _send_whatsapp_buttons(
        state["user_id"],
        "Keep going!",
        [
            {"type": "reply", "reply": {"id": "yes_meal_day3", "title": "✅ Day 4"}},
        ]
    )
    state["last_question"] = "meal_day3_complete"
    return state


def generate_meal_day4_plan(state: State) -> State:
    """Node: Generate Day 4 meal plan."""
    # If resuming after image analysis, do not auto-generate. Ask for confirmation instead.
    if state.get("last_question") == "image_analysis_complete":
        _send_whatsapp_buttons(
            state["user_id"],
            "Shall I generate your Day 4 meal plan now?",
            [
                {"type": "reply", "reply": {"id": "yes_meal_day3", "title": "✅ Generate Day 4"}},
            ]
        )
        state["last_question"] = "meal_day3_complete"
        return state
    send_whatsapp_message(state["user_id"], "🍽️ Generating Day 4 Plan...")
    state["meal_day4_plan"] = generate_day_meal_plan(state, 4)
    send_whatsapp_message(state["user_id"], state["meal_day4_plan"])
    _send_whatsapp_buttons(
        state["user_id"],
        "Almost there!",
        [
            {"type": "reply", "reply": {"id": "yes_meal_day4", "title": "✅ Day 5"}},
        ]
    )
    state["last_question"] = "meal_day4_complete"
    return state


def generate_meal_day5_plan(state: State) -> State:
    """Node: Generate Day 5 meal plan."""
    # If resuming after image analysis, do not auto-generate. Ask for confirmation instead.
    if state.get("last_question") == "image_analysis_complete":
        _send_whatsapp_buttons(
            state["user_id"],
            "Shall I generate your Day 5 meal plan now?",
            [
                {"type": "reply", "reply": {"id": "yes_meal_day4", "title": "✅ Generate Day 5"}},
            ]
        )
        state["last_question"] = "meal_day4_complete"
        return state
    send_whatsapp_message(state["user_id"], "🍽️ Generating Day 5 Plan...")
    state["meal_day5_plan"] = generate_day_meal_plan(state, 5)
    send_whatsapp_message(state["user_id"], state["meal_day5_plan"])
    _send_whatsapp_buttons(
        state["user_id"],
        "Two more days!",
        [
            {"type": "reply", "reply": {"id": "yes_meal_day5", "title": "✅ Day 6"}},
        ]
    )
    state["last_question"] = "meal_day5_complete"
    return state


def generate_meal_day6_plan(state: State) -> State:
    """Node: Generate Day 6 meal plan."""
    # If resuming after image analysis, do not auto-generate. Ask for confirmation instead.
    if state.get("last_question") == "image_analysis_complete":
        _send_whatsapp_buttons(
            state["user_id"],
            "Shall I generate your Day 6 meal plan now?",
            [
                {"type": "reply", "reply": {"id": "yes_meal_day5", "title": "✅ Generate Day 6"}},
            ]
        )
        state["last_question"] = "meal_day5_complete"
        return state
    send_whatsapp_message(state["user_id"], "🍽️ Generating Day 6 Plan...")
    state["meal_day6_plan"] = generate_day_meal_plan(state, 6)
    send_whatsapp_message(state["user_id"], state["meal_day6_plan"])
    _send_whatsapp_buttons(
        state["user_id"],
        "Last day!",
        [
            {"type": "reply", "reply": {"id": "yes_meal_day6", "title": "✅ Day 7"}},
        ]
    )
    state["last_question"] = "meal_day6_complete"
    return state


def generate_meal_day7_plan(state: State) -> State:
    """Node: Generate Day 7 meal plan."""
    # If resuming after image analysis, do not auto-generate. Ask for confirmation instead.
    if state.get("last_question") == "image_analysis_complete":
        _send_whatsapp_buttons(
            state["user_id"],
            "Shall I generate your Day 7 meal plan now?",
            [
                {"type": "reply", "reply": {"id": "yes_meal_day6", "title": "✅ Generate Day 7"}},
            ]
        )
        state["last_question"] = "meal_day6_complete"
        return state
    send_whatsapp_message(state["user_id"], "🍽️ Generating Day 7 Plan...")
    state["meal_day7_plan"] = generate_day_meal_plan(state, 7)
    send_whatsapp_message(state["user_id"], state["meal_day7_plan"])
    
    # Send completion message
    send_whatsapp_message(
        state["user_id"],
        "🎉 Your complete 7-day meal plan has been generated!"
    )
    
    # Compile all day plans into a single meal_plan field for backward compatibility
    full_plan = f"{state['meal_day1_plan']}\n\n{state['meal_day2_plan']}\n\n{state['meal_day3_plan']}\n\n{state['meal_day4_plan']}\n\n{state['meal_day5_plan']}\n\n{state['meal_day6_plan']}\n\n{state['meal_day7_plan']}"
    state["meal_plan"] = full_plan
    state["meal_plan_sent"] = True
    state["last_question"] = "meal_plan_complete"
    return state