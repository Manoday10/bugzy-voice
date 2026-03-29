"""
Meal Plan Nodes Module

This module contains all meal plan related nodes for the Bugzy agent.
These nodes handle meal plan generation, review, and revision.
"""

import time
import logging
from app.services.chatbot.bugzy_ams.state import State
from app.services.chatbot.bugzy_ams.constants import (
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
from app.services.crm.sessions import save_meal_plan, extract_ams_meal_user_context, load_meal_plan

from app.services.prompts.ams.meal import (
    generate_day_meal_plan,
    generate_complete_7day_meal_plan,
)
from app.services.prompts.ams.conversational import get_conversational_response

from app.services.prompts.ams.meal_plan_template import (
    build_meal_plan_prompt,
    build_disclaimers,
    _remove_llm_disclaimers,
)
from app.services.chatbot.bugzy_ams.nodes.user_verification_nodes import _ams_voice_owns_turn

logger = logging.getLogger(__name__)


# --- MEAL PLAN COLLECTION NODES ---
def ask_meal_plan_preference(state: State) -> State:
    """Node: Ask if user wants a meal plan."""
    # Store previous answer if coming from medications
    if state.get("user_msg"):
        _update_last_answer_in_history(state, state["user_msg"])

    # More empathetic question
    question = "Let's get started, would you like me to create your personalized meal plan? 🍴"

    _send_whatsapp_buttons(
        state["user_id"],
        question,
        [
            {"type": "reply", "reply": {"id": "create_meal_plan", "title": "Create meal plan"}},
            {"type": "reply", "reply": {"id": "has_meal_plan", "title": "Already have one"}},
            {"type": "reply", "reply": {"id": "no_meal_plan", "title": "Maybe later"}},
        ]
    )
    
    # Store question in history
    _store_question_in_history(state, question, "ask_meal_plan_preference")
    
    state["last_question"] = "ask_meal_plan_preference"
    state["pending_node"] = "ask_meal_plan_preference"
    return state


def voice_agent_promotion_meal(state: State) -> State:
    """Node: Present choice between chat and voice agent meal planning."""
    from app.services.whatsapp.client import _send_whatsapp_call_button

    if _ams_voice_owns_turn(state):
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
        return collect_health_conditions(state)

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


def collect_health_conditions(state: State) -> State:
    """Node: Ask about health conditions (now part of meal planner flow)."""
    state["current_agent"] = "meal"

    # Store user's answer when routed back with user_msg (avoids re-asking)
    _set_if_expected(state, "health_conditions", "health_conditions")
    if state.get("user_msg"):
        _update_last_answer_in_history(state, state["user_msg"])

    hc = (state.get("health_conditions") or "").strip().lower()
    none_values = ["none", "no", "nil", "nothing", "health_none"]
    if hc:
        state["last_question"] = "health_conditions"
        # Chain to next node so we speak the next question, not the health one again
        if hc not in none_values:
            return collect_medications(state)
        return collect_diet_preference(state)

    question = "🌸 Let's start with your health profile!\n\n🩺 Do you have any health conditions I should know about? I want to make sure this supports your body properly 💚"

    is_voice = state.get("interaction_mode") == "voice"
    if is_voice:
        from app.services.chatbot.bugzy_ams.voice_questions import VOICE_QUESTIONS
        question = VOICE_QUESTIONS.get("health_conditions", question)
        state.setdefault("messages", []).append({"role": "assistant", "content": question})
    else:
        _send_whatsapp_list(
            state["user_id"],
            question,
            "Mark Your Health ⚕️",
            [
                {
                    "title": "⚕️ Health Conditions",
                    "rows": [
                        {"id": "health_none", "title": "✅ None", "description": "No health conditions"},
                        {"id": "health_diabetes", "title": "🍬 Diabetes", "description": "Type 1 or Type 2"},
                        {"id": "health_ibs", "title": "💩 IBS/Gut Issues", "description": "Irritable Bowel Syndrome or other gut issues"},
                        {"id": "health_hypertension", "title": "💓 Hypertension", "description": "High blood pressure"},
                        {"id": "health_thyroid", "title": "🧬 Thyroid Issues", "description": "Hypo or hyperthyroidism"},
                        {"id": "health_other", "title": "⚠️ Other", "description": "Other health conditions not listed, just type them out"}
                    ]
                }
            ],
            header_text="Health Conditions",
        )

    _store_question_in_history(state, question, "health_conditions")
    
    state["last_question"] = "health_conditions"
    state["pending_node"] = "collect_health_conditions"
    return state


def collect_medications(state: State) -> State:
    """Node: Ask about medications - only shown if health conditions exist."""
    # Store health conditions and medications from user_msg
    _set_if_expected(state, "health_conditions", "health_conditions")
    _set_if_expected(state, "medications", "medications")

    if state.get("user_msg"):
        _update_last_answer_in_history(state, state["user_msg"])

    # Already collected medications (incl. "none") — advance to diet preference
    med = (state.get("medications") or "").strip().lower()
    if med:
        state["last_question"] = "medications"
        return collect_diet_preference(state)

    # Check if we're resuming from Q&A or snap - if so, only send the question
    is_resuming = state.get("last_question") in ["resuming_from_health_qna", "resuming_from_product_qna", "resuming_from_snap"]
    
    if not is_resuming:
        # Get the health condition value and check if it's actually "none"
        health_condition_value = state.get('health_conditions', '').strip().lower()
        
        # Only send empathetic response if there's an actual health condition (not "none")
        if health_condition_value and health_condition_value not in ["none", "no", "nil", "nothing", "health_none"]:
            # User has a real health condition - acknowledge it empathetically
            response = get_conversational_response(
                f"Respond empathetically and supportively to the user's health condition: {state['health_conditions']}. "
                f"Acknowledge their condition with care and understanding. Keep it brief and warm.",
                user_name=state.get('user_name', '')
            )
            send_whatsapp_message(state["user_id"], response)
            # Store empathetic response as a complete system message
            _store_system_message(state, response)
    
    question = "🌱 Just staying thoughtful about the details now."
    question_0 = "💊 Are you currently on any medications? This helps me tailor your plan safely. Feel free to say 'None' if not."
    if state.get("interaction_mode") == "voice":
        from app.services.chatbot.bugzy_ams.voice_questions import VOICE_QUESTIONS
        med_q = VOICE_QUESTIONS.get("medications", question_0)
        state.setdefault("messages", []).append({"role": "assistant", "content": med_q})
    else:
        send_whatsapp_message(state["user_id"], question)
        send_whatsapp_message(state["user_id"], question_0)
    
    # Store the question in conversation history
    _store_question_in_history(state, question, "medications")
    
    state["last_question"] = "medications"
    state["pending_node"] = "collect_medications"
    return state






def collect_diet_preference(state: State) -> State:
    """Node: Collect dietary preferences."""
    _set_if_expected(state, "medications", "medications")
    _set_if_expected(state, "diet_preference", "diet_preference")

    if state.get("user_msg"):
        _update_last_answer_in_history(state, state["user_msg"])

    # Already collected diet preference — advance to cuisine
    diet = (state.get("diet_preference") or "").strip().lower()
    if diet:
        state["last_question"] = "diet_preference"
        return collect_cuisine_preference(state)

    question = "🌈 Looking good so far — let's fine-tune this a bit.\n\n🥗 What's your dietary preference?"
    is_voice = state.get("interaction_mode") == "voice"
    if is_voice:
        from app.services.chatbot.bugzy_ams.voice_questions import VOICE_QUESTIONS
        question = VOICE_QUESTIONS.get("diet_preference", question)
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
            header_text="Dietary Preferences",
        )
    
    # Store the question in conversation history
    _store_question_in_history(state, question, "diet_preference")
    
    state["last_question"] = "diet_preference"
    state["pending_node"] = "collect_diet_preference"
    return state


def collect_cuisine_preference(state: State) -> State:
    """Node: Collect cuisine preferences."""
    _set_if_expected(state, "diet_preference", "diet_preference")
    _set_if_expected(state, "cuisine_preference", "cuisine_preference")

    if state.get("user_msg"):
        _update_last_answer_in_history(state, state["user_msg"])

    cuisine = (state.get("cuisine_preference") or "").strip()
    if cuisine:
        state["last_question"] = "cuisine_preference"
        return collect_current_dishes(state)

    is_voice = state.get("interaction_mode") == "voice"
    is_resuming = state.get("last_question") in ["resuming_from_health_qna", "resuming_from_product_qna", "resuming_from_snap"]

    if not is_resuming and not is_voice:
        response = get_conversational_response(f"Affirm to user's diet preference: {state['diet_preference']}", user_name=state.get('user_name', ''))
        send_whatsapp_message(state["user_id"], response)
        _store_system_message(state, response)

    question = "✨ Nice going! We're just a step away from wrapping this up.\n\n🍛 Now, do you have any cuisine preferences?"
    if is_voice:
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
                    {"id": "cuisine_all", "title": "🍽️ All Cuisines", "description": "No specific preference"}
                ]
            }
        ],
        header_text="Cuisine Preferences",
    )

    # Store the question in conversation history
    _store_question_in_history(state, question, "cuisine_preference")

    state["last_question"] = "cuisine_preference"
    state["pending_node"] = "collect_cuisine_preference"
    return state


def collect_current_dishes(state: State) -> State:
    """Node: Ask about typical dishes eaten (simplified question)."""
    _set_if_expected(state, "cuisine_preference", "cuisine_preference")
    _set_if_expected(state, "current_dishes", "current_dishes")

    if state.get("user_msg"):
        _update_last_answer_in_history(state, state["user_msg"])

    dishes = (state.get("current_dishes") or "").strip()
    if dishes:
        state["last_question"] = "current_dishes"
        return collect_allergies(state)

    question = "💭 I want this to feel right for you — one small check.\n\nWhat do you usually eat throughout the day? Share any 3 dishes to give me an idea! 😋"
    if state.get("interaction_mode") == "voice":
        state.setdefault("messages", []).append({"role": "assistant", "content": question})
    else:
        send_whatsapp_message(state["user_id"], question)
    
    _store_question_in_history(state, question, "current_dishes")
    
    state["last_question"] = "current_dishes"
    state["pending_node"] = "collect_current_dishes"
    return state


def collect_allergies(state: State) -> State:
    """Node: Ask about allergies and intolerances."""
    _set_if_expected(state, "current_dishes", "current_dishes")
    _set_if_expected(state, "allergies", "allergies")

    if state.get("user_msg"):
        _update_last_answer_in_history(state, state["user_msg"])

    allergies_val = (state.get("allergies") or "").strip()
    if allergies_val:
        state["last_question"] = "allergies"
        return collect_water_intake(state)

    is_resuming = state.get("last_question") in ["resuming_from_health_qna", "resuming_from_product_qna", "resuming_from_snap"]
    
    is_voice = state.get("interaction_mode") == "voice"
    if not is_resuming and not is_voice:
        response = get_conversational_response(f"Affirm to user's meal dishes: {state.get('current_dishes', '')}", user_name=state.get('user_name', ''))
        send_whatsapp_message(state["user_id"], response)
        _store_system_message(state, response)

    question = "🔒 Before I finalize this, I want to make sure it fits you perfectly.\n\n🚫 Do you have any food allergies or intolerances?\n\n*Note:* Allergies are strictly avoided, while intolerances allow some flexibility."
    if is_voice:
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
                    {"id": "allergy_none", "title": "No Allergies", "description": "No food allergies"},
                    {"id": "allergy_dairy", "title": "Dairy Allergy", "description": "All dairy strictly avoided"},
                    {"id": "allergy_gluten", "title": "Gluten Allergy", "description": "All gluten/wheat strictly avoided"},
                    {"id": "allergy_nuts", "title": "Nut Allergy", "description": "All nuts strictly avoided"},
                    {"id": "allergy_eggs", "title": "Egg Allergy", "description": "All eggs strictly avoided"},
                    {"id": "allergy_multiple", "title": "Multiple Allergies", "description": "More than one allergy"}
                ]
            },
            {
                "title": "⚠️ Intolerances",
                "rows": [
                    {"id": "intolerance_lactose", "title": "Lactose Intolerant", "description": "Can have yogurt/curd, not milk"},
                    {"id": "intolerance_gluten", "title": "Gluten Sensitive", "description": "Reduced gluten flexibility"},
                    {"id": "intolerance_spicy", "title": "Spice Intolerant", "description": "Prefer mild foods"},
                    {"id": "intolerance_multiple", "title": "Multiple Intolerances", "description": "More than one intolerance"}
                ]
            }
        ],
        header_text="Allergies and Intolerances",
    )
    
    # Store the question in conversation history
    _store_question_in_history(state, question, "allergies")
    
    state["last_question"] = "allergies"
    state["pending_node"] = "collect_allergies"
    return state


def collect_water_intake(state: State) -> State:
    """Node: Ask about water intake."""
    _set_if_expected(state, "allergies", "allergies")
    _set_if_expected(state, "water_intake", "water_intake")

    if state.get("user_msg"):
        _update_last_answer_in_history(state, state["user_msg"])

    water = (state.get("water_intake") or "").strip()
    if water:
        state["last_question"] = "water_intake"
        return collect_beverages(state)

    is_resuming = state.get("last_question") in ["resuming_from_health_qna", "resuming_from_product_qna", "resuming_from_snap"]
    
    is_voice = state.get("interaction_mode") == "voice"
    if not is_resuming and not is_voice:
        response = get_conversational_response(f"Affirm to user's allergies: {state['allergies']}", user_name=state.get('user_name', ''))
        send_whatsapp_message(state["user_id"], response)
        _store_system_message(state, response)

    question = "🌿 A little fine-tuning so this works smoothly for you.\n\n💧 Hydration check! Roughly how much *water* do you drink in a day? You can answer in glasses or liters 💦"
    if is_voice:
        state.setdefault("messages", []).append({"role": "assistant", "content": question})
    else:
        _send_whatsapp_list(
            state["user_id"],
            question,
            "Hydration Check-In 🥤",
            [{"title": "🚰 Daily Water Intake", "rows": [
                {"id": "water_1_2", "title": "🥤 1–2 glasses", "description": "Less than 500ml per day"},
                {"id": "water_3_5", "title": "💧 3–5 glasses", "description": "About 1 liter per day"},
                {"id": "water_6_8", "title": "🚰 6–8 glasses", "description": "About 1.5–2 liters per day"},
                {"id": "water_9_plus", "title": "🌊 9+ glasses", "description": "More than 2 liters per day"}
            ]}],
            header_text="Water Intake",
        )
    
    # Store the question in conversation history
    _store_question_in_history(state, question, "water_intake")
    
    state["last_question"] = "water_intake"
    state["pending_node"] = "collect_water_intake"
    return state


def collect_beverages(state: State) -> State:
    """Node: Ask about beverages."""
    _set_if_expected(state, "water_intake", "water_intake")
    _set_if_expected(state, "beverages", "beverages")

    if state.get("user_msg"):
        _update_last_answer_in_history(state, state["user_msg"])

    beverages_val = (state.get("beverages") or "").strip()
    if beverages_val:
        state["last_question"] = "beverages"
        return collect_supplements(state)

    question = "✅ Almost done — quick personalization check.\n\n☕ Any other beverages you regularly have? (Tea, Coffee, Soft drinks, None) If yes, how many cups/glasses per day?"
    if state.get("interaction_mode") == "voice":
        state.setdefault("messages", []).append({"role": "assistant", "content": question})
    else:
        send_whatsapp_message(state["user_id"], question)
    
    _store_question_in_history(state, question, "beverages")
    
    state["last_question"] = "beverages"
    state["pending_node"] = "collect_beverages"
    return state


def collect_supplements(state: State) -> State:
    """Node: Ask about supplements intake."""
    _set_if_expected(state, "beverages", "beverages")
    _set_if_expected(state, "supplements", "supplements")

    if state.get("user_msg"):
        _update_last_answer_in_history(state, state["user_msg"])

    supplements_val = (state.get("supplements") or "").strip()
    if supplements_val:
        state["last_question"] = "supplements"
        return collect_gut_health(state)

    is_resuming = state.get("last_question") in ["resuming_from_health_qna", "resuming_from_product_qna", "resuming_from_snap"]
    
    is_voice = state.get("interaction_mode") == "voice"
    if not is_resuming and not is_voice:
        response = get_conversational_response(
            f"Acknowledge the user's beverage information: {state.get('beverages', 'their preferences')}. Keep it brief.",
            user_name=state.get('user_name', '')
        )
        send_whatsapp_message(state["user_id"], response)
        _store_system_message(state, response)

    question = "🛠️ Almost locked in — a few finishing touches first.\n\n💊 Are you currently taking any supplements? (Vitamins, Minerals, Protein powder, etc.)"
    if is_voice:
        state.setdefault("messages", []).append({"role": "assistant", "content": question})
    else:
        _send_whatsapp_list(
        state["user_id"],
        question,
        "Supplement Check 💊",
        [
            {
                "title": "💊 Supplement Types",
                "rows": [
                    {"id": "supplements_none", "title": "❌ None", "description": "Not taking any supplements"},
                    {"id": "supplements_multivitamin", "title": "🌈 Multivitamin", "description": "Daily multivitamin"},
                    {"id": "supplements_vitamin_d", "title": "☀️ Vitamin D", "description": "Vitamin D supplements"},
                    {"id": "supplements_protein", "title": "💪 Protein Powder", "description": "Whey, plant-based, etc."},
                    {"id": "supplements_omega3", "title": "🐟 Omega-3", "description": "Fish oil or algae"},
                    {"id": "supplements_other", "title": "📝 Other", "description": "Other supplements, just type them out"}
                ]
            }
        ],
        header_text="Supplements",
    )
    
    # Store the question in conversation history
    _store_question_in_history(state, question, "supplements")
    
    state["last_question"] = "supplements"
    state["pending_node"] = "collect_supplements"
    return state


def collect_gut_health(state: State) -> State:
    """Node: Ask about gut health issues."""
    _set_if_expected(state, "supplements", "supplements")
    _set_if_expected(state, "gut_health", "gut_health")

    if state.get("user_msg"):
        _update_last_answer_in_history(state, state["user_msg"])

    gut = (state.get("gut_health") or "").strip()
    if gut:
        state["last_question"] = "gut_health"
        return collect_meal_goals(state)

    is_resuming = state.get("last_question") in ["resuming_from_health_qna", "resuming_from_product_qna", "resuming_from_snap"]
    
    is_voice = state.get("interaction_mode") == "voice"
    if not is_resuming and not is_voice:
        response = get_conversational_response(
            f"Acknowledge the user's supplement information: {state.get('supplements', 'their supplement routine')}. Keep it brief.",
            user_name=state.get('user_name', '')
        )
        send_whatsapp_message(state["user_id"], response)
        _store_system_message(state, response)

    question = "🤍 Let's make sure this supports your body properly.\n\n💩 How's your gut health? Do you experience any of these digestive issues?"
    if is_voice:
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
                    {"id": "gut_none", "title": "✅ All Good", "description": "No digestive issues"},
                    {"id": "gut_constipation", "title": "🚽 Constipation", "description": "Difficulty passing stools"},
                    {"id": "gut_gas", "title": "💨 Gas/Bloating", "description": "Excessive gas or bloating"},
                    {"id": "gut_acidity", "title": "🔥 Acidity/Heartburn", "description": "Acid reflux or heartburn"},
                    {"id": "gut_irregular", "title": "🔄 Irregular Bowel", "description": "Irregular bowel movements"},
                    {"id": "gut_multiple", "title": "📝 Multiple Issues", "description": "More than one issue, type them out"}
                    ]
                }
            ],
            header_text="Gut Health",
        )

    _store_question_in_history(state, question, "gut_health")
    
    state["last_question"] = "gut_health"
    state["pending_node"] = "collect_gut_health"
    return state


def collect_meal_goals(state: State) -> State:
    """Node: Ask about meal goals."""
    _set_if_expected(state, "gut_health", "gut_health")
    _set_if_expected(state, "meal_goals", "meal_goals")

    if state.get("user_msg"):
        _update_last_answer_in_history(state, state["user_msg"])

    goals = (state.get("meal_goals") or "").strip()
    if goals:
        state["last_question"] = "meal_goals"
        return generate_meal_plan(state)

    is_resuming = state.get("last_question") in ["resuming_from_health_qna", "resuming_from_product_qna", "resuming_from_snap"]
    is_voice = state.get("interaction_mode") == "voice"
    if not is_resuming and not is_voice:
        response = get_conversational_response(
            f"Acknowledge the user's gut health information: {state.get('gut_health', 'their digestive health')}. Keep it brief and supportive.",
            user_name=state.get('user_name', '')
        )
        send_whatsapp_message(state["user_id"], response)
        _store_system_message(state, response)

    question = "🌟 You're right at the finish line now.\n\n🎯 Lastly — what's your *main health or nutrition goal* right now?"
    if is_voice:
        state.setdefault("messages", []).append({"role": "assistant", "content": question})
    else:
        _send_whatsapp_list(
            state["user_id"],
            question,
            "Pick a Goal 🎯",
            [
                {
                    "title": "⚖️ Weight Management",
                    "rows": [
                        {"id": "goal_weight_loss", "title": "Weight Loss", "description": "Reduce body weight"},
                        {"id": "goal_weight_gain", "title": "Weight Gain", "description": "Increase body weight"},
                        {"id": "goal_weight_maintain", "title": "Maintain Weight", "description": "Maintain current weight"}
                    ]
                },
                {
                    "title": "💪 Health Goals",
                    "rows": [
                        {"id": "goal_gut_healing", "title": "Gut Healing", "description": "Improve digestive health"},
                        {"id": "goal_energy", "title": "Better Energy", "description": "Increase daily energy levels"},
                        {"id": "goal_immunity", "title": "Boost Immunity", "description": "Strengthen immune system"},
                        {"id": "goal_wellness", "title": "General Wellness", "description": "Overall health improvement"}
                    ]
                }
            ],
            header_text="Meal Goals",
        )
    
    # Store the question in conversation history
    _store_question_in_history(state, question, "meal_goals")
    
    state["last_question"] = "meal_goals"
    state["pending_node"] = "collect_meal_goals"
    return state



def generate_meal_plan(state: State) -> State:
    """Node: Generate Day 1 meal plan using LLM."""
    _set_if_expected(state, "meal_goals", "meal_goals")

    if state.get("user_msg"):
        _update_last_answer_in_history(state, state["user_msg"])

    is_voice = state.get("interaction_mode") == "voice"
    if not is_voice:
        send_whatsapp_message(state["user_id"], "💚 I want this to truly feel made for you.\n\n✨ Thank you for sharing all that with me! Give me a moment to create your personalized 7-day meal plan...")
        time.sleep(1)

    logger.info("Generating Day 1 Plan...")
    meal_plan = generate_day_meal_plan(state, 1)

    state["profiling_collected_in_meal"] = True
    state["meal_day1_plan"] = meal_plan

    save_meal_plan(state["user_id"], {
        "meal_day1_plan": meal_plan,
        "user_context": extract_ams_meal_user_context(state)
    }, product="ams")

    if is_voice:
        state["meal_plan"] = meal_plan
        state["fresh_meal_plan"] = True
        closing = "Your personalized Day 1 meal plan is ready. I'm sending it to you on WhatsApp now. Have a great day! <<END_CALL>>"
        state.setdefault("messages", []).append({"role": "assistant", "content": closing})
    else:
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


def transition_to_exercise(state: State) -> State:
    """Node: Automatic transition from meal plan to exercise plan."""
    user_name = state.get('user_name', 'there')
    if state.get("interaction_mode") != "voice":
        send_whatsapp_message(
            state["user_id"],
            f"\n💪 Now let's move on to your exercise plan {user_name}!"
        )
    # Voice: skip WhatsApp; collect_fitness_level will speak next question
    state["current_agent"] = "exercise"
    state["last_question"] = "transitioning_to_exercise"
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
            from app.services.chatbot.bugzy_ams.voice_questions import VOICE_QUESTIONS
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
            from app.services.chatbot.bugzy_ams.voice_questions import VOICE_QUESTIONS
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
            from app.services.chatbot.bugzy_ams.voice_questions import VOICE_QUESTIONS
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
        "user_context": extract_ams_meal_user_context(state)
    }
    save_meal_plan(state["user_id"], meal_plan_data, product="ams", increment_change_count=True)
    
    is_voice = state.get("interaction_mode") == "voice"
    send_whatsapp_message(state["user_id"], revised_plan)
    if is_voice:
        from app.services.chatbot.bugzy_ams.voice_questions import VOICE_QUESTIONS
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
            from app.services.chatbot.bugzy_ams.voice_questions import VOICE_QUESTIONS
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
            from app.services.chatbot.bugzy_ams.voice_questions import VOICE_QUESTIONS
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
            from app.services.chatbot.bugzy_ams.voice_questions import VOICE_QUESTIONS
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
    # Re-establish journey_restart_mode so route_after_meal_plan_completion can END at post_plan_qna (not exercise/SNAP)
    logger.info("🔍 MEAL PLAN GENERATION: Checking journey_restart_mode")
    logger.info("  - journey_restart_mode: %s", state.get("journey_restart_mode"))
    logger.info("  - existing_meal_plan_choice_origin: %s", state.get("existing_meal_plan_choice_origin"))
    
    if state.get("existing_meal_plan_choice_origin") == "post_plan_qna":
        state["journey_restart_mode"] = True
        logger.info("  - Re-established journey_restart_mode based on origin flag")
    
    if state.get("journey_restart_mode"):
        logger.info("🔄 Journey restart mode detected - meal plan complete, staying in post_plan_qna")
        state["last_question"] = "post_plan_qna"
        state["current_agent"] = "post_plan_qna"
    else:
        logger.info("➡️ Normal flow - meal plan complete, proceeding to exercise preference")
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
        "user_context": extract_ams_meal_user_context(state)
    }
    save_meal_plan(state["user_id"], meal_plan_data, product="ams")
    
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