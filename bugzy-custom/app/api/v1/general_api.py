
import logging
import asyncio
import time
import random
import os
from datetime import datetime
from typing import Optional
import requests

# Import services
from app.services.crm.sessions import SESSIONS, save_session_to_file, load_user_session
# UPDATED IMPORT for new location
from app.services.chatbot.bugzy_general.agent import graph
from app.services.whatsapp.client import send_whatsapp_message
from app.services.whatsapp.parser import extract_age
from app.services.chatbot.bugzy_general.constants import QUESTION_TO_NODE, TRANSITION_MESSAGES
from app.services.rag.qna import MedicalGuardrails, EmergencyDetector

# Logic constants
MESSAGE_BATCH_WINDOW = 1  # seconds to wait for additional messages
PENDING_MESSAGES: dict[str, dict] = {}  # user_id -> {messages: [], timer: time, last_question: str, flusher_running: bool}

# Global reference to the main event loop
MAIN_EVENT_LOOP = None

# Logger
logger = logging.getLogger(__name__)

# WhatsApp Credentials
WHATSAPP_API_TOKEN = os.getenv("WHATSAPP_API_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")


# ==============================================================================
# NODE CONFIGURATION & MAPPING
# ==============================================================================






# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def set_main_event_loop(loop):
    """Set the main event loop reference."""
    global MAIN_EVENT_LOOP
    MAIN_EVENT_LOOP = loop


def wa_typing(to_phone_number: str, duration_ms: int = 800) -> None:
    """Send a typing indicator to WhatsApp user."""
    if not all([WHATSAPP_API_TOKEN, WHATSAPP_PHONE_NUMBER_ID]):
        return
    url = f"https://graph.facebook.com/v20.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_API_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone_number,
        "type": "typing",
        "typing": {"duration": max(300, min(20000, int(duration_ms)))}
    }
    try:
        requests.post(url, headers=headers, json=payload, timeout=10)
    except Exception:
        pass


def send_whatsapp_reaction(to_phone_number: str, message_id: str, emoji: str) -> None:
    """Send a reaction emoji to a specific message."""
    if not all([WHATSAPP_API_TOKEN, WHATSAPP_PHONE_NUMBER_ID]):
        logger.error("❌ WHATSAPP: Missing credentials for reaction")
        return
    
    url = f"https://graph.facebook.com/v20.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_API_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_phone_number,
        "type": "reaction",
        "reaction": {"message_id": message_id, "emoji": emoji}
    }
    
    try:
        logger.info("📤 Sending reaction %s to message %s", emoji, message_id)
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        # logger.info("📱 Reaction API Response: %d - %s", response.status_code, response.text)
        response.raise_for_status()
        logger.info("✅ Reaction sent successfully: %s", emoji)
    except Exception as e:
        logger.error("❌ Reaction failed: %s", e)


def get_batched_message(user_id: str) -> Optional[str]:
    """Get the combined message from the batch and clear it."""
    batch = PENDING_MESSAGES.get(user_id)
    if not batch or not batch.get("messages"):
        return None
    
    # Combine all messages with newlines
    combined = "\n".join(batch["messages"])
    
    # Clear the batch
    PENDING_MESSAGES.pop(user_id, None)
    
    return combined


def handle_resume_flow(user_id: str, state: dict, current_question: str) -> None:
    """
    Handle resuming the conversation flow after an interruption (emergency, guardrail, snap).
    Update session state to point to the correct pending node and send transition message.
    """
    # Map current question to the corresponding node
    state["pending_node"] = QUESTION_TO_NODE.get(current_question, "collect_age")
    
    # Set last_question to indicate resuming
    state["last_question"] = "resuming_from_snap"
    logger.info("Set pending_node to: %s for user %s", state['pending_node'], user_id)
    logger.info("Set last_question to: resuming_from_snap to match snap behavior")
    
    # Send transition message
    random_message = random.choice(TRANSITION_MESSAGES)
    send_whatsapp_message(user_id, random_message)
    logger.info("📱 Sent transition message: %s", random_message)
    
    # Update session
    SESSIONS[user_id] = state
    save_session_to_file(user_id, state)
    logger.info("💾 Session saved for user %s (resume setup)", user_id)
    
    # Execute graph stream to resume
    try:
        # Ensure user_id is in state before streaming
        if "user_id" not in state:
            state["user_id"] = user_id
        
        final_state_from_graph = None
        for event in graph.stream(state):
            final_state_from_graph = event
        
        if final_state_from_graph:
            last_node_name = list(final_state_from_graph.keys())[0]
            new_state = final_state_from_graph[last_node_name]
            # Ensure user_id is preserved in the new state
            if "user_id" not in new_state:
                new_state["user_id"] = user_id
            SESSIONS[user_id] = new_state
            logger.info("Resumed to node: %s, now in state: %s", last_node_name, SESSIONS[user_id].get('last_question'))
            save_session_to_file(user_id, SESSIONS[user_id])
    except Exception as resume_error:
        logger.exception("Error during resume: %s", resume_error)
        # Ensure user_id is still in session even if resume fails
        if "user_id" not in state:
            state["user_id"] = user_id
        SESSIONS[user_id] = state
        save_session_to_file(user_id, state)


def get_button_text_from_id(button_id: str, button_title: str) -> str:
    """
    Maps a button ID to the corresponding text value for the chatbot.
    Returns the text to be processed.
    """
    text = button_title if button_title else ""  # Default to button title
    
    # Meal plan revision buttons
    if button_id == "make_changes_meal_day1":
        text = "make_changes_meal_day1"
    elif button_id == "continue_7day_meal":
        text = "continue_7day_meal"
    elif button_id == "more_changes_meal_day1":
        text = "more_changes_meal_day1"
    # Exercise plan revision buttons
    elif button_id == "make_changes_day1":
        text = "make_changes_day1"
    elif button_id == "continue_7day":
        text = "continue_7day"
    elif button_id == "more_changes_day1":
        text = "more_changes_day1"
    # Meal plan day progression buttons
    elif button_id == "yes_meal_day2":
        text = "yes_meal_day2"
    elif button_id == "yes_meal_day3":
        text = "yes_meal_day3"
    elif button_id == "yes_meal_day4":
        text = "yes_meal_day4"
    elif button_id == "yes_meal_day5":
        text = "yes_meal_day5"
    elif button_id == "yes_meal_day6":
        text = "yes_meal_day6"
    # Exercise plan day progression buttons
    elif button_id == "yes_day1":
        text = "Yes"
    elif button_id == "no_day1":
        text = "Not yet"
    elif button_id == "yes_day2":
        text = "Yes"
    elif button_id == "no_day2":
        text = "Not yet"
    elif button_id == "yes_day3":
        text = "Yes"
    elif button_id == "no_day3":
        text = "Not yet"
    elif button_id == "yes_day4":
        text = "Yes"
    elif button_id == "no_day4":
        text = "Not yet"
    elif button_id == "yes_day5":
        text = "Yes"
    elif button_id == "no_day5":
        text = "Not yet"
    elif button_id == "yes_day6":
        text = "Yes"
    elif button_id == "no_day6":
        text = "Not yet"
    elif button_id == "yes_day7":
        text = "Yes"
    elif button_id == "no_day7":
        text = "Not yet"
        
    # Health conditions buttons
    elif button_id == "health_none":
        text = "None"
    elif button_id == "health_diabetes":
        text = "Diabetes"
    elif button_id == "health_ibs":
        text = "IBS and gut issues"
    elif button_id == "health_hypertension":
        text = "Hypertension"
    elif button_id == "health_thyroid":
        text = "Thyroid Issues"
    elif button_id == "health_other":
        text = "Other health conditions"
        
    # Diet preference buttons
    elif button_id == "diet_non_veg":
        text = "Non-Vegetarian"
    elif button_id == "diet_pure_veg":
        text = "Pure Vegetarian"
    elif button_id == "diet_eggitarian":
        text = "Eggitarian"
    elif button_id == "diet_vegan":
        text = "Vegan"
    elif button_id == "diet_pescatarian":
        text = "Pescatarian"
    elif button_id == "diet_flexitarian":
        text = "Flexitarian"
    elif button_id == "diet_keto":
        text = "Keto"
        
    # Cuisine preference buttons
    elif button_id == "cuisine_all":
        text = "All cuisines"
    elif button_id == "cuisine_north_indian":
        text = "North Indian"
    elif button_id == "cuisine_south_indian":
        text = "South Indian"
    elif button_id == "cuisine_chinese":
        text = "Chinese"
    elif button_id == "cuisine_gujarati":
        text = "Gujarati"
    elif button_id == "cuisine_bengali":
        text = "Bengali"
    elif button_id == "cuisine_italian":
        text = "Italian"
    elif button_id == "cuisine_mexican":
        text = "Mexican"
        
    # Allergies buttons
    elif button_id == "allergy_none":
        text = "None"
    elif button_id == "allergy_dairy":
        text = "Dairy"
    elif button_id == "allergy_gluten":
        text = "Gluten/Wheat"
    elif button_id == "allergy_nuts":
        text = "Nuts"
    elif button_id == "allergy_eggs":
        text = "Eggs"
    elif button_id == "allergy_soy":
        text = "Soy"
    elif button_id == "allergy_shellfish":
        text = "Shellfish"
    elif button_id == "allergy_multiple":
        text = "Multiple"
        
    # Water intake buttons
    elif button_id == "water_1_2":
        text = "1-2 glasses"
    elif button_id == "water_3_5":
        text = "3-5 glasses"
    elif button_id == "water_6_8":
        text = "6-8 glasses"
    elif button_id == "water_9_plus":
        text = "9+ glasses"
        
    # Lifestyle buttons
    elif button_id == "lifestyle_rarely":
        text = "Rarely"
    elif button_id == "lifestyle_1_2":
        text = "1-2 times a week"
    elif button_id == "lifestyle_3_5":
        text = "3-5 times a week"
    elif button_id == "lifestyle_daily":
        text = "Almost daily"
        
    # Activity level buttons
    elif button_id == "activity_sedentary":
        text = "Sedentary"
    elif button_id == "activity_light":
        text = "Lightly Active"
    elif button_id == "activity_moderate":
        text = "Moderate"
    elif button_id == "activity_very":
        text = "Very Active"
    elif button_id == "activity_extreme":
        text = "Extreme"
        
    # Meal goals buttons
    elif button_id == "goal_weight_loss":
        text = "Weight Loss"
    elif button_id == "goal_weight_gain":
        text = "Weight Gain"
    elif button_id == "goal_weight_maintain":
        text = "Maintain Weight"
    elif button_id == "goal_gut_healing":
        text = "Gut Healing"
    elif button_id == "goal_energy":
        text = "Better Energy"
    elif button_id == "goal_immunity":
        text = "Boost Immunity"
    elif button_id == "goal_wellness":
        text = "General Wellness"
    
    # Fitness level buttons
    elif button_id == "fitness_beginner":
        text = "Beginner"
    elif button_id == "fitness_intermediate":
        text = "Intermediate"
    elif button_id == "fitness_advanced":
        text = "Advanced"
    
    # Activity type buttons
    elif button_id == "activity_walking":
        text = "Walking"
    elif button_id == "activity_running":
        text = "Running"
    elif button_id == "activity_cycling":
        text = "Cycling"
    elif button_id == "activity_yoga":
        text = "Yoga"
    elif button_id == "activity_gym":
        text = "Gym/Weights"
    elif button_id == "activity_sports":
        text = "Sports"
    elif button_id == "activity_none":
        text = "None"
    
    # Exercise frequency buttons
    elif button_id == "freq_0":
        text = "0 days"
    elif button_id == "freq_1_2":
        text = "1-2 days"
    elif button_id == "freq_3_4":
        text = "3-4 days"
    elif button_id == "freq_5_6":
        text = "5-6 days"
    elif button_id == "freq_7":
        text = "7 days"
    
    # Exercise intensity buttons
    elif button_id == "intensity_light":
        text = "Light"
    elif button_id == "intensity_moderate":
        text = "Moderate"
    elif button_id == "intensity_vigorous":
        text = "Vigorous"
    
    # Session duration buttons
    elif button_id == "duration_15":
        text = "15 mins"
    elif button_id == "duration_30":
        text = "30 mins"
    elif button_id == "duration_45":
        text = "45 mins"
    elif button_id == "duration_60":
        text = "1 hour"
    elif button_id == "duration_90_plus":
        text = "90+ mins"
    
    # Sedentary time buttons
    elif button_id == "sedentary_2_4":
        text = "2-4 hours"
    elif button_id == "sedentary_4_6":
        text = "4-6 hours"
    elif button_id == "sedentary_6_8":
        text = "6-8 hours"
    elif button_id == "sedentary_8_10":
        text = "8-10 hours"
    elif button_id == "sedentary_10_plus":
        text = "10+ hours"
    
    # Exercise goals buttons
    elif button_id == "goal_weight_loss":
        text = "Weight Loss"
    elif button_id == "goal_muscle_gain":
        text = "Muscle Gain"
    elif button_id == "goal_lean_athletic":
        text = "Lean & Athletic"
    elif button_id == "goal_flexibility":
        text = "Flexibility"
    elif button_id == "goal_wellness":
        text = "General Wellness"
    
    # Supplements buttons
    elif button_id == "supplements_none":
        text = "None"
    elif button_id == "supplements_multivitamin":
        text = "Multivitamin"
    elif button_id == "supplements_vitamin_d":
        text = "Vitamin D"
    elif button_id == "supplements_protein":
        text = "Protein Powder"
    elif button_id == "supplements_omega3":
        text = "Omega-3"
    elif button_id == "supplements_other":
        text = "Other supplements"
    
    # Gut health buttons
    elif button_id == "gut_none":
        text = "All Good"
    elif button_id == "gut_constipation":
        text = "Constipation"
    elif button_id == "gut_gas":
        text = "Gas/Bloating"
    elif button_id == "gut_acidity":
        text = "Acidity/Heartburn"
    elif button_id == "gut_irregular":
        text = "Irregular Bowel"
    elif button_id == "gut_multiple":
        text = "Multiple Issues"
    
    # Height range buttons
    elif button_id == "height_140_150":
        text = "140-150 cm / 4'7\"–4'11\""
    elif button_id == "height_150_160":
        text = "150-160 cm / 4'11\"–5'3\""
    elif button_id == "height_160_170":
        text = "160-170 cm / 5'3\"–5'7\""
    elif button_id == "height_170_180":
        text = "170-180 cm / 5'7\"–5'11\""
    elif button_id == "height_180_190":
        text = "180-190 cm / 5'11\"–6'3\""
    elif button_id == "height_190_200":
        text = "190-200 cm / 6'3\"–6'7\""
    
    # Weight range buttons
    elif button_id == "weight_40_50":
        text = "40-50 kg / 88–110 lbs"
    elif button_id == "weight_50_60":
        text = "50-60 kg / 110–132 lbs"
    elif button_id == "weight_60_70":
        text = "60-70 kg / 132–154 lbs"
    elif button_id == "weight_70_80":
        text = "70-80 kg / 154–176 lbs"
    elif button_id == "weight_80_90":
        text = "80-90 kg / 176–198 lbs"
    elif button_id == "weight_90_100":
        text = "90-100 kg / 198–220 lbs"
    elif button_id == "weight_100_110":
        text = "100-110 kg / 220–242 lbs"
    
    return text


def process_node_reaction(state: dict, user_id: str, message_id: str) -> None:
    """
    Analyzes the current state and sends an appropriate emoji reaction 
    to the user's message based on the active node.
    """
    # Control overall reaction probability (50% chance to send a reaction)
    REACTION_PROBABILITY = 0.5
    if random.random() > REACTION_PROBABILITY:
        return

    current_node = None
    try:
        current_node = (state.get("pending_node") or state.get("last_question") or "")
    except Exception:
        current_node = ""
    
    node = (current_node or "").lower()
    emoji = None
    reason = None

    # Map node categories to emojis
    def choose(options):
        return random.choice(options)

    if not node:
        pass
    elif node in ["verify_user"]:
        emoji, reason = choose(["👋🏻", "✨", "🌟"]), "verify_user"
    elif "age" in node:
        emoji, reason = choose(["🎂", "🧒", "✨"]), "age"
    elif "height" in node:
        emoji, reason = choose(["📏", "📐", "✨"]), "height"
    elif "weight" in node:
        emoji, reason = choose(["⚖️", "🏋️", "✨"]), "weight"
    elif "bmi" in node or "calculate_bmi" in node:
        emoji, reason = choose(["🧮", "📊", "ℹ️"]), "bmi"
    elif "health_conditions" in node:
        emoji, reason = choose(["🩺", "💚", "✨"]), "health"
    elif "medications" in node:
        emoji, reason = choose(["💊", "💚", "✨"]), "medications"
    elif "meal_timing" in node or ("breakfast" in node and "current_" not in node):
        emoji, reason = choose(["⏰", "🍽️", "🕒"]), "meal_timing"
    elif "current_breakfast" in node:
        emoji, reason = choose(["🍳", "🥣", "🥪"]), "current_breakfast"
    elif "current_lunch" in node:
        emoji, reason = choose(["🍛", "🍚", "🍽️"]), "current_lunch"
    elif "current_dinner" in node:
        emoji, reason = choose(["🍲", "🍝", "🍽️"]), "current_dinner"
    elif "diet_preference" in node:
        emoji, reason = choose(["🌱", "🥗", "🥦"]), "diet_preference"
    elif "cuisine_preference" in node:
        emoji, reason = choose(["🍜", "🍣", "🌮", "🍝"]), "cuisine_preference"
    elif "allergies" in node:
        emoji, reason = choose(["⚠️", "🌰", "🥜"]), "allergies"
    elif "water_intake" in node:
        emoji, reason = choose(["💧", "🚰", "🫗"]), "water_intake"
    elif "beverages" in node:
        emoji, reason = choose(["☕", "🧋", "🍵"]), "beverages"
    elif "lifestyle" in node:
        emoji, reason = choose(["🌿", "🧘", "😌"]), "lifestyle"
    elif "activity_level" in node:
        emoji, reason = choose(["⚡", "🏃", "💪🏻"]), "activity_level"
    elif "sleep_stress" in node:
        emoji, reason = choose(["😴", "🛌", "🧘"]), "sleep_stress"
    elif "supplements" in node:
        emoji, reason = choose(["💊", "💪", "🌿"]), "supplements"
    elif "gut_health" in node:
        emoji, reason = choose(["💩", "🦠", "🌿"]), "gut_health"
    elif "fitness_level" in node:
        emoji, reason = choose(["💪🏻", "🎯", "🌟"]), "fitness_level"
    elif "activity_types" in node:
        emoji, reason = choose(["🏃", "🚴", "🧘", "🏋️"]), "activity_types"
    elif "exercise_frequency" in node:
        emoji, reason = choose(["📅", "🔁", "⏱️"]), "exercise_frequency"
    elif "exercise_intensity" in node:
        emoji, reason = choose(["🔥", "⚡", "💪🏻"]), "exercise_intensity"
    elif "session_duration" in node:
        emoji, reason = choose(["⏱️", "⌛", "🕒"]), "session_duration"
    elif "sedentary_time" in node:
        emoji, reason = choose(["🪑", "🧍", "🚶"]), "sedentary_time"
    elif "exercise_goals" in node:
        emoji, reason = choose(["🎯", "🏆", "💪🏻"]), "exercise_goals"
    elif "generate" in node and "exercise" in node:
        emoji, reason = choose(["⚙️", "🏋️", "⏳"]), "generate_exercise"
    elif "generate" in node and "meal" in node:
        emoji, reason = choose(["⚙️", "🍱", "⏳"]), "generate_meal"
    elif "plan" in node or "review" in node:
        emoji, reason = choose(["✅", "📄", "📝"]), "plan_review"
    elif "post_plan_qna" in node or "qna" in node:
        emoji, reason = choose(["❓", "💬", "🤝"]), "qna"
    else:
        # Soft fallback by agent context (reduced from 40% to 10%)
        agent = (state.get("current_agent") or "").lower()
        if agent == "meal":
            emoji, reason = choose(["🥗", "🍽️", "🍱", "🌱"]), "meal_context"
        elif agent == "exercise":
            emoji, reason = choose(["💪🏻", "🏃", "⚡", "🏋️"]), "exercise_context"
        elif random.random() < 0.1:
            emoji, reason = choose(["👍🏻", "✨", "🌟", "💫"]), "random"

    if emoji:
        logger.info("🎯 Node-based reaction: %s (node: %s, reason: %s)", emoji, node, reason)
        send_whatsapp_reaction(user_id, message_id, emoji)


# ==============================================================================
# CORE PROCESSING FUNCTIONS
# ==============================================================================

def schedule_batch_flush(user_id: str) -> None:
    """Start a background flusher that waits for inactivity then processes the batch.
    
    This function schedules the async _flusher task on the running event loop 
    since it is always called from an async context (webhook background task).
    """
    try:
        batch = PENDING_MESSAGES.get(user_id)
        if not batch:
            return
        
        if batch.get("flusher_running"):
            return

        batch["flusher_running"] = True

        async def _flusher():
            try:
                # Wait until the inactivity window has elapsed since the last message
                while True:
                    b = PENDING_MESSAGES.get(user_id)
                    if not b:
                        return
                    elapsed = time.time() - b.get("timer", 0)
                    remaining = MESSAGE_BATCH_WINDOW - elapsed
                    if remaining <= 0:
                        break
                    await asyncio.sleep(min(remaining, 0.2))

                combined = get_batched_message(user_id)
                if not combined:
                    return

                try:
                    await wa_typing(user_id, duration_ms=800)
                except Exception:
                    pass

                logger.info("📦 Background flush for user %s with batched message", user_id)
                await asyncio.to_thread(process_batched_message, user_id, combined)
            finally:
                batch_ref = PENDING_MESSAGES.get(user_id)
                if batch_ref is not None:
                    batch_ref["flusher_running"] = False

        # Schedule the async task on the running loop
        asyncio.create_task(_flusher())
            
    except Exception as e:
        logger.exception("⚠️ Error scheduling batch flush: %s", e)
        import traceback
        traceback.print_exc()


def process_batched_message(user_id: str, combined_text: str) -> None:
    """Process a batched message through the agent system."""
    start_time = time.time()
    
    logger.info("\n%s", '='*70)
    logger.info("🔄 PROCESSING BATCHED MESSAGE")
    logger.info("="*70)
    logger.info("User ID: %s", user_id)
    logger.info("Message: %s%s", combined_text[:100], '...' if len(combined_text) > 100 else '')
    logger.info("User in SESSIONS: %s", user_id in SESSIONS)
    
    try:
        # =====================================================
        # FAST PATH FOR NEW USERS
        # =====================================================
        if user_id not in SESSIONS:
            logger.info("📊 User %s NOT in SESSIONS, checking MongoDB...", user_id)
            # Check if user has any existing session in MongoDB
            try:
                user_session = load_user_session(user_id)
                logger.info("📊 MongoDB query result: %s", 'Found session' if user_session else 'No session found')
                if not user_session:
                    # Brand new user - skip ALL heavy logic and use fast path
                    logger.info("🆕 New user %s detected - using fast path", user_id)
                    
                    # Create minimal initial session with only essential fields
                    initial_state = {
                        "user_id": user_id,
                        "user_msg": combined_text,
                        "last_question": None,  # Will be set by graph

                        "conversation_history": [],
                        "journey_history": [],
                        "full_chat_history": [{
                            "role": "user", 
                            "content": combined_text,
                            "timestamp": datetime.now().isoformat()
                        }],
                        # Add placeholder fields that graph might expect
                        "age": None,
                        "height": None,
                        "weight": None,
                        "bmi": None,
                        "health_conditions": None,
                        "medications": None,
                        "meal_timings": {},
                        "current_breakfast": None,
                        "current_lunch": None,
                        "current_dinner": None,
                        "diet_preference": None,
                        "cuisine_preference": None,
                        "allergies": None,
                        "water_intake": None,
                        "beverages": None,
                        "lifestyle": None,
                        "activity_level": None,
                        "sleep_stress": None,
                        "supplements": None,
                        "gut_health": None,
                        "meal_goals": None,
                        "meal_plan": None,
                        "meal_plan_sent": None,
                        "fitness_level": None,
                        "activity_types": None,
                        "exercise_frequency": None,
                        "exercise_intensity": None,
                        "session_duration": None,
                        "sedentary_time": None,
                        "exercise_goals": None,
                        "exercise_plan": None,
                        "exercise_plan_sent": None,
                        "current_agent": None,
                        "user_name": None,
                        "phone_number": None,
                        "crm_user_data": None,
                        # Order fields
                        "user_order": None,
                        "user_order_date": None,
                        "has_orders": False,
                    }
                    
                    # Save to memory and database immediately
                    SESSIONS[user_id] = initial_state
                    save_session_to_file(user_id, initial_state)
                    logger.info("💾 Initial session created and saved for new user %s", user_id)
                    
                    # Stream through graph starting from beginning
                    final_state_from_graph = None
                    for event in graph.stream(initial_state):
                        final_state_from_graph = event
                    
                    if final_state_from_graph:
                        last_node_name = list(final_state_from_graph.keys())[0]
                        
                        # CRITICAL FIX: Merge graph state into existing SESSIONS instead of replacing
                        graph_state = final_state_from_graph[last_node_name]
                        
                        # Initialize SESSIONS[user_id] if it doesn't exist
                        if user_id not in SESSIONS:
                            SESSIONS[user_id] = {}
                        
                        # Update SESSIONS with graph state, but preserve existing fields
                        for key, value in graph_state.items():
                            SESSIONS[user_id][key] = value
                        
                        SESSIONS[user_id]["user_id"] = user_id
                        save_session_to_file(user_id, SESSIONS[user_id])
                        elapsed = time.time() - start_time
                        logger.info("✅ New user %s initialized and sent first question via fast path", user_id)
                        logger.info("⏱️ Fast path processing time for new user %s: %.2fs", user_id, elapsed)
                    
                    return  # Exit early - skip all heavy logic below
                else:
                    # User has existing session in DB, load it
                    logger.info("✅ Loaded session for user %s from persistent storage (single fetch)", user_id)
                    SESSIONS[user_id] = user_session
            except Exception as e:
                logger.exception("⚠️ Error in fast path check for user %s: %s", user_id, e)
                # Continue to normal flow on error
        
        # =====================================================
        # EXISTING USER FLOW
        # =====================================================
        # Load session or create a new one
        if user_id not in SESSIONS:
            # Load only this user's session from persistent storage
            try:
                user_session = load_user_session(user_id)
                if user_session:
                    logger.info("✅ Loaded session for user %s from persistent storage (single fetch)", user_id)
                    SESSIONS[user_id] = user_session
                    
                    # CRITICAL FIX: Initialize exercise fields if missing (for sessions created before these fields were added)
                    exercise_fields = ["fitness_level", "activity_types", "exercise_frequency", "exercise_intensity", "session_duration", "sedentary_time", "exercise_goals"]
                    for field in exercise_fields:
                        if field not in SESSIONS[user_id]:
                            SESSIONS[user_id][field] = None
                else:
                    logger.info("ℹ️ No existing session for user %s; creating new session", user_id)
            except Exception as e:
                logger.error("⚠️ Error loading session for user %s: %s", user_id, e)
        
        # Get the session or create a new one if not found
        state = SESSIONS.get(user_id, {
            "user_id": user_id,
            "user_msg": None,
            "last_question": None,
            "conversation_history": [],
            "journey_history": [],
            "full_chat_history": [],
            "age": None,
            "height": None,
            "weight": None,
            "bmi": None,
            "health_conditions": None,
            "medications": None,
            "meal_timings": {},
            "current_breakfast": None,
            "current_lunch": None,
            "current_dinner": None,
            "diet_preference": None,
            "cuisine_preference": None,
            "allergies": None,
            "water_intake": None,
            "beverages": None,
            "lifestyle": None,
            "activity_level": None,
            "sleep_stress": None,
            "supplements": None,
            "gut_health": None,
            "meal_goals": None,
            "meal_plan": None,
            "meal_plan_sent": None,
            "fitness_level": None,
            "activity_types": None,
            "exercise_frequency": None,
            "exercise_intensity": None,
            "session_duration": None,
            "sedentary_time": None,
            "exercise_goals": None,
            "exercise_plan": None,
            "exercise_plan_sent": None,
            "current_agent": None,
            "user_name": None,
            "phone_number": None,
            "crm_user_data": None,
        })
        
        if user_id not in SESSIONS:
            logger.info("🆕 Creating new session for user %s", user_id)

        state["interaction_mode"] = "chat"
        state["user_msg"] = combined_text
        
        # =====================================================
        # GUARDRAIL CHECK: Gut Coach Connection & Emergency Detection
        # Check BEFORE processing as profile field answer
        # =====================================================
        
        medical_guardrails = MedicalGuardrails()
        emergency_detector = EmergencyDetector()
        
        # Check for emergency first
        is_emergency, ctas_level, emergency_category, emergency_response = \
            emergency_detector.detect_emergency(combined_text)
        
        if is_emergency:
            logger.info("🚨 Emergency detected in user message: %s...", combined_text[:50])
            send_whatsapp_message(user_id, emergency_response)
            
            # Log to conversation history
            if state.get("conversation_history") is None:
                state["conversation_history"] = []
            state["conversation_history"].append({"role": "user", "content": combined_text})
            state["conversation_history"].append({"role": "assistant", "content": emergency_response})
            
            # Add to full chat history
            if state.get("full_chat_history") is None:
                state["full_chat_history"] = []
            
            state["full_chat_history"].append({
                "role": "user", 
                "content": combined_text,
                "timestamp": datetime.now().isoformat()
            })
            state["full_chat_history"].append({
                "role": "assistant", 
                "content": emergency_response,
                "timestamp": datetime.now().isoformat()
            })
            
            # Resume flow logic
            current_question = state.get("last_question")
            plans_completed = state.get("meal_plan_sent") and state.get("exercise_plan_sent")
            
            # SNAP states should NOT trigger resume flow - they handle themselves via router
            snap_states = ["transitioning_to_snap", "snap_complete", "transitioning_to_gut_coach"]
            
            # Check if user is in the middle of a flow
            if current_question and current_question not in [None, "verified", "post_plan_qna", "health_qna_answered", "product_qna_answered"] + snap_states and not plans_completed:
                logger.info("User %s is in middle of flow at: %s (plans_completed=%s), resuming...", user_id, current_question, plans_completed)
                handle_resume_flow(user_id, state, current_question)
            else:
                # User is not in middle of flow OR plans are completed
                logger.info("User %s not in middle of flow or plans completed, just saving session", user_id)
                SESSIONS[user_id] = state
                save_session_to_file(user_id, state)
            
            return  # Exit early, don't process as profile field
        
        # Check for gut coach connection and other medical guardrails
        health_context = {
            "health_conditions": state.get("health_conditions", ""),
            "allergies": state.get("allergies", ""),
            "medications": state.get("medications", ""),
            "supplements": state.get("supplements", ""),
            "gut_health": state.get("gut_health", "")
        }
        
        guardrail_triggered, guardrail_type, guardrail_response = \
            medical_guardrails.check_guardrails(combined_text, health_context)
        
        if guardrail_triggered:
            logger.info("🛡️ Guardrail triggered (%s) in user message: %s...", guardrail_type, combined_text[:50])
            send_whatsapp_message(user_id, guardrail_response)
            
            # Log to conversation history
            if state.get("conversation_history") is None:
                state["conversation_history"] = []
            state["conversation_history"].append({"role": "user", "content": combined_text})
            state["conversation_history"].append({"role": "assistant", "content": guardrail_response})
            
            # Add to full chat history
            if state.get("full_chat_history") is None:
                state["full_chat_history"] = []
            
            state["full_chat_history"].append({
                "role": "user", 
                "content": combined_text,
                "timestamp": datetime.now().isoformat()
            })
            state["full_chat_history"].append({
                "role": "assistant", 
                "content": guardrail_response,
                "timestamp": datetime.now().isoformat()
            })
            
            # Resume flow logic
            current_question = state.get("last_question")
            plans_completed = state.get("meal_plan_sent") and state.get("exercise_plan_sent")
            
            # SNAP states should NOT trigger resume flow - they handle themselves via router
            snap_states = ["transitioning_to_snap", "snap_complete", "transitioning_to_gut_coach"]
            
            # Check if user is in the middle of a flow
            if current_question and current_question not in [None, "verified", "post_plan_qna", "health_qna_answered", "product_qna_answered"] + snap_states and not plans_completed:
                logger.info("User %s is in middle of flow at: %s (plans_completed=%s), resuming...", user_id, current_question, plans_completed)
                handle_resume_flow(user_id, state, current_question)
            else:
                # User is not in middle of flow OR plans are completed
                logger.info("User %s not in middle of flow or plans completed, just saving session", user_id)
                SESSIONS[user_id] = state
                save_session_to_file(user_id, state)
            
            return  # Exit early, don't process as profile field

        # Persist the user's answer to the last asked question BEFORE routing
        last_question = state.get("last_question")
        
        # Store the current field being updated for logging
        current_field = None
        
        # Process input based on last question
        if last_question == "age":
            current_field = "age"
            # Extract age intelligently from user input
            extracted_age = extract_age(combined_text)
            state["age"] = extracted_age if extracted_age else combined_text
                
        elif last_question == "height":
            current_field = "height"
            state["height"] = combined_text
                
        elif last_question == "weight":
            current_field = "weight"
            state["weight"] = combined_text
                
        elif last_question == "health_conditions":
            current_field = "health_conditions"
            state["health_conditions"] = combined_text
                
        elif last_question == "medications":
            current_field = "medications"
            state["medications"] = combined_text
                
        elif last_question == "meal_timing_breakfast":
            current_field = "meal_timings.breakfast"
            state.setdefault("meal_timings", {})["breakfast"] = combined_text
                
        elif last_question == "meal_timing_lunch":
            current_field = "meal_timings.lunch"
            state.setdefault("meal_timings", {})["lunch"] = combined_text
                
        elif last_question == "meal_timing_dinner":
            current_field = "meal_timings.dinner"
            state.setdefault("meal_timings", {})["dinner"] = combined_text
                
        elif last_question == "current_breakfast":
            current_field = "current_breakfast"
            state["current_breakfast"] = combined_text
                
        elif last_question == "current_lunch":
            current_field = "current_lunch"
            state["current_lunch"] = combined_text
                
        elif last_question == "current_dinner":
            current_field = "current_dinner"
            state["current_dinner"] = combined_text
                
        elif last_question == "diet_preference":
            current_field = "diet_preference"
            state["diet_preference"] = combined_text
                
        elif last_question == "cuisine_preference":
            current_field = "cuisine_preference"
            state["cuisine_preference"] = combined_text
                
        elif last_question == "allergies":
            current_field = "allergies"
            state["allergies"] = combined_text
                
        elif last_question == "water_intake":
            current_field = "water_intake"
            state["water_intake"] = combined_text
                
        elif last_question == "beverages":
            current_field = "beverages"
            state["beverages"] = combined_text
                
        elif last_question == "lifestyle":
            current_field = "lifestyle"
            state["lifestyle"] = combined_text
                
        elif last_question == "activity_level":
            current_field = "activity_level"
            state["activity_level"] = combined_text
                
        elif last_question == "sleep_stress":
            current_field = "sleep_stress"
            state["sleep_stress"] = combined_text
                
        elif last_question == "supplements":
            current_field = "supplements"
            state["supplements"] = combined_text
                
        elif last_question == "gut_health":
            current_field = "gut_health"
            state["gut_health"] = combined_text
                
        elif last_question == "meal_goals":
            current_field = "meal_goals"
            state["meal_goals"] = combined_text
                
        elif last_question == "fitness_level":
            current_field = "fitness_level"
            state["fitness_level"] = combined_text
                
        elif last_question == "activity_types":
            current_field = "activity_types"
            state["activity_types"] = combined_text
                
        elif last_question == "exercise_frequency":
            current_field = "exercise_frequency"
            state["exercise_frequency"] = combined_text
                
        elif last_question == "exercise_intensity":
            current_field = "exercise_intensity"
            state["exercise_intensity"] = combined_text
                
        elif last_question == "session_duration":
            current_field = "session_duration"
            state["session_duration"] = combined_text
                
        elif last_question == "sedentary_time":
            current_field = "sedentary_time"
            state["sedentary_time"] = combined_text
                
        elif last_question == "exercise_goals":
            current_field = "exercise_goals"
            state["exercise_goals"] = combined_text
        
        # Meal plan change requests: do NOT overwrite - node accumulates changes
        elif last_question == "awaiting_meal_day1_changes":
            current_field = None  # Node handles storage and accumulation
        
        # Exercise plan change requests  
        elif last_question == "awaiting_day1_changes":
            current_field = "day1_change_request"
            state["day1_change_request"] = combined_text
        
        # Review states (button interactions - no data to store, but recognized to avoid warnings)
        elif last_question in ["meal_day1_plan_review", "meal_day1_revised_review", 
                               "day1_plan_review", "day1_revised_review"]:
            current_field = "review_state"  # Placeholder - no actual storage needed
            # These are button interaction states, not data collection
        
        # Log which field was updated
        if current_field:
            logger.info("📝 Field '%s' processed with batched input: '%s'", current_field, combined_text)
        elif last_question is None:
            logger.info("ℹ️ Processing initial message or new flow (no pending question)")
        else:
            logger.warning("⚠️ No matching field for last_question: '%s'", last_question)
        
        # Save session to persistent storage after updating state with user's answer
        if user_id in SESSIONS:
            # Only update fields that have been explicitly set in this function
            # to prevent overwriting other fields with invalid data
            if current_field:
                # For nested fields like meal_timings.breakfast
                if '.' in current_field:
                    parent, child = current_field.split('.')
                    if parent in state and isinstance(state[parent], dict):
                        SESSIONS[user_id].setdefault(parent, {})
                        if child in state[parent]:
                            SESSIONS[user_id][parent][child] = state[parent][child]
                else:
                    # Only update if the field was actually set (passed validation)
                    if current_field in state and state[current_field] is not None:
                        SESSIONS[user_id][current_field] = state[current_field]
            
            # Always update user_msg and last_question
            SESSIONS[user_id]["user_msg"] = state["user_msg"]
            if "last_question" in state:
                SESSIONS[user_id]["last_question"] = state["last_question"]
                
            save_session_to_file(user_id, SESSIONS[user_id])
            logger.info("💾 Session updated for user %s with batched response to: %s", user_id, last_question)
        
        # Ensure required invariants before routing
        # Always carry user_id inside the state passed to the graph
        state["user_id"] = user_id

        # Log user message to full_chat_history
        if state.get("full_chat_history") is None:
            state["full_chat_history"] = []
        
        state["full_chat_history"].append({
            "role": "user",
            "content": state["user_msg"],
            "timestamp": datetime.now().isoformat()
        })

        # Run ONE STEP using graph.stream
        logger.info("\n🎯 Starting graph.stream for EXISTING user %s...", user_id)
        logger.info("📊 Current state last_question: %s", state.get('last_question', 'None'))
        logger.info("📊 User message: %s...", state.get('user_msg', 'None')[:50])
        final_state_from_graph = None
        # Ensure user_id is in state before streaming
        if "user_id" not in state:
            state["user_id"] = user_id
        
        for event in graph.stream(state):
            final_state_from_graph = event
            logger.info("📍 Graph event received: %s", list(event.keys())[0] if event else 'None')

        # Save the updated state from the graph's output
        logger.info("🏁 Graph streaming completed. Final state: %s", 'Found' if final_state_from_graph else 'None')
        if final_state_from_graph:
            last_node_name = list(final_state_from_graph.keys())[0]
            logger.info("📌 Last node executed: %s", last_node_name)
            
            # CRITICAL FIX: Merge graph state into existing SESSIONS instead of replacing
            # This preserves all previously collected fields (exercise fields, meal fields, etc.)
            graph_state = final_state_from_graph[last_node_name]
            
            # Update SESSIONS with graph state, but preserve existing fields
            for key, value in graph_state.items():
                SESSIONS[user_id][key] = value
            
            # Preserve invariant: always keep user_id in session state
            SESSIONS[user_id]["user_id"] = user_id
            
            # Save session to persistent storage
            save_session_to_file(user_id, SESSIONS[user_id])
            logger.info("💾 Session saved for user %s at step: %s", user_id, SESSIONS[user_id].get('last_question'))
            
            # Log performance metrics for existing user flow
            elapsed = time.time() - start_time
            logger.info("⏱️ Processing time for existing user %s: %.2fs", user_id, elapsed)

    except Exception as e:
        elapsed = time.time() - start_time
        logger.error("\n%s", '='*70)
        logger.error("❌ ERROR PROCESSING BATCHED MESSAGE")
        logger.error("="*70)
        logger.error("User ID: %s", user_id)
        logger.error("Time elapsed: %.2fs", elapsed)
        logger.error("Error: %s", e)
        logger.error("="*70)
        import traceback
        traceback.print_exc()
        logger.error("="*70)
