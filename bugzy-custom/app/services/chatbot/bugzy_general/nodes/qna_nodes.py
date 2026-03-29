"""
QnA nodes for health, product, and post-plan questions.

This module contains nodes for handling health-related questions, product questions,
post-plan Q&A, and plan editing functionality.
"""

import re
import random
from typing import Optional
from app.services.chatbot.bugzy_general.state import State
from app.services.whatsapp.client import send_whatsapp_message
import logging

logger = logging.getLogger(__name__)
from app.services.whatsapp.utils import (
    llm,
)
from app.services.whatsapp.messages import send_multiple_messages
from app.services.prompts.general.prompt_store import load_prompt
from app.services.chatbot.bugzy_general.router import extract_day_number, is_meal_edit_request, is_exercise_edit_request

from app.services.chatbot.bugzy_general.context_manager import (
    build_optimized_context,
    detect_user_intent
)


def health_qna_node(state: State) -> State:
    """Node: Answer health-related questions and return to flow."""
    user_question = state.get("user_msg", "")
    
    from app.services.rag.emergency_detection import EmergencyDetector
    from app.services.rag.medical_guardrails import MedicalGuardrails
    
    # Initialize guardrails
    medical_guardrails = MedicalGuardrails()
    emergency_detector = EmergencyDetector()

    # Detect intent (and store for analytics/debugging)
    detected_intent = detect_user_intent(user_question, state)
    state["detected_intent"] = detected_intent
    
    # Build optimized context using new modular system
    user_context = build_optimized_context(
        state=state,
        user_question=user_question,
        llm_client=llm,
        intent=detected_intent,
        include_plans=True,
        max_recent_messages=6
    )
    
    # =====================================================
    # GUARDRAIL CHECK 1: Emergency Detection (CTAS)
    # =====================================================
    is_emergency, ctas_level, emergency_category, emergency_response = \
        emergency_detector.detect_emergency(user_question)
    
    if is_emergency:
        # Send emergency response immediately
        send_multiple_messages(state["user_id"], emergency_response, send_whatsapp_message)
        
        # Log to conversation history
        if state.get("conversation_history") is None:
            state["conversation_history"] = []
        state["conversation_history"].append({"role": "user", "content": user_question})
        state["conversation_history"].append({"role": "assistant", "content": emergency_response})
        
        # Keep conversation history manageable
        if len(state["conversation_history"]) > 20:
            state["conversation_history"] = state["conversation_history"][-20:]
        
        state["health_qna_answered"] = True
        return state
    
    # =====================================================
    # GUARDRAIL CHECK 2: Medical Guardrails (including Gut Coach Connection)
    # =====================================================
    # Build health context from state
    health_context = {
        "health_conditions": state.get("health_conditions", ""),
        "allergies": state.get("allergies", ""),
        "medications": state.get("medications", ""),
        "supplements": state.get("supplements", ""),
        "gut_health": state.get("gut_health", "")
    }
    
    guardrail_triggered, guardrail_type, guardrail_response = \
        medical_guardrails.check_guardrails(user_question, health_context)
    
    if guardrail_triggered:
        # Send guardrail response immediately
        send_multiple_messages(state["user_id"], guardrail_response, send_whatsapp_message)
        
        # Log to conversation history
        if state.get("conversation_history") is None:
            state["conversation_history"] = []
        state["conversation_history"].append({"role": "user", "content": user_question})
        state["conversation_history"].append({"role": "assistant", "content": guardrail_response})
        
        # Keep conversation history manageable
        if len(state["conversation_history"]) > 20:
            state["conversation_history"] = state["conversation_history"][-20:]
        
        state["health_qna_answered"] = True
        return state
    
    # Use LLM to answer health question
    template = load_prompt("agent/health_qna_node.md")
    prompt = template.format(
        user_context=user_context,
        user_question=user_question,
        user_name=state.get("user_name", ""),
        user_order=state.get("user_order", "None"),
        user_order_date=state.get("user_order_date", "")
    )
    
    response = llm.invoke(prompt)
    answer = response.content.strip()
    
    # Send the answer
    send_multiple_messages(state["user_id"], answer, send_whatsapp_message)
    
    # Mirror product_qna_node behavior: log Q&A into conversation history only
    if state.get("conversation_history") is None:
        state["conversation_history"] = []
    
    # Add user question
    state["conversation_history"].append({
        "role": "user",
        "content": user_question
    })
    
    # Add assistant answer
    state["conversation_history"].append({
        "role": "assistant",
        "content": answer
    })
    
    # Keep conversation history manageable (last 20 messages)
    if len(state["conversation_history"]) > 20:
        state["conversation_history"] = state["conversation_history"][-20:]
    
    # Preserve the current state before setting health_qna_answered
    # Map the current last_question to the appropriate pending_node if not already set
    current_last_question = state.get("last_question", "")
    
    # Only update pending_node if it's not already set or if we're in a review/plan state
    if not state.get("pending_node") or current_last_question in [
        "day1_plan_review", "meal_day1_plan_review", "day1_revised_review", "meal_day1_revised_review",
        "awaiting_day1_changes", "awaiting_meal_day1_changes", "day1_complete", "meal_day1_complete",
        "day2_complete", "meal_day2_complete", "day3_complete", "meal_day3_complete",
        "day4_complete", "meal_day4_complete", "day5_complete", "meal_day5_complete",
        "day6_complete", "meal_day6_complete", "exercise_plan_complete", "meal_plan_complete"
    ]:
        # Map last_question to the appropriate node
        question_to_node = {
            # Basic info
            "age": "collect_age",
            "height": "collect_height",
            "weight": "collect_weight",
            "bmi_calculated": "calculate_bmi",
            
            # Meal plan collection
            "health_conditions": "collect_health_conditions",
            "medications": "collect_medications",
            "meal_timing_breakfast": "collect_meal_timing_breakfast",
            "meal_timing_lunch": "collect_meal_timing_lunch",
            "meal_timing_dinner": "collect_meal_timing_dinner",
            "current_breakfast": "collect_current_breakfast",
            "current_lunch": "collect_current_lunch",
            "current_dinner": "collect_current_dinner",
            "diet_preference": "collect_diet_preference",
            "cuisine_preference": "collect_cuisine_preference",
            "allergies": "collect_allergies",
            "water_intake": "collect_water_intake",
            "beverages": "collect_beverages",
            "lifestyle": "collect_lifestyle",
            "activity_level": "collect_activity_level",
            "sleep_stress": "collect_sleep_stress",
            "supplements": "collect_supplements",
            "gut_health": "collect_gut_health",
            "meal_goals": "collect_meal_goals",
            
            # Meal plan generation and review
            "meal_day1_plan_review": "handle_meal_day1_review_choice",
            "awaiting_meal_day1_changes": "collect_meal_day1_changes",
            "meal_day1_revised_review": "handle_meal_day1_revised_review",
            "meal_day1_complete": "generate_all_remaining_meal_days",
            "meal_day2_complete": "generate_meal_day3_plan",
            "meal_day3_complete": "generate_meal_day4_plan",
            "meal_day4_complete": "generate_meal_day5_plan",
            "meal_day5_complete": "generate_meal_day6_plan",
            "meal_day6_complete": "generate_meal_day7_plan",
            
            # Exercise plan collection
            "fitness_level": "collect_fitness_level",
            "activity_types": "collect_activity_types",
            "exercise_frequency": "collect_exercise_frequency",
            "exercise_intensity": "collect_exercise_intensity",
            "session_duration": "collect_session_duration",
            "sedentary_time": "collect_sedentary_time",
            "exercise_goals": "collect_exercise_goals",
            
            # Exercise plan generation and review
            "day1_plan_review": "handle_day1_review_choice",
            "awaiting_day1_changes": "collect_day1_changes",
            "day1_revised_review": "handle_day1_revised_review",
            "day1_complete": "generate_all_remaining_exercise_days",
            "day2_complete": "generate_day3_plan",
            "day3_complete": "generate_day4_plan",
            "day4_complete": "generate_day5_plan",
            "day5_complete": "generate_day6_plan",
            "day6_complete": "generate_day7_plan",
        }
        
        # Set pending_node based on current last_question
        mapped_node = question_to_node.get(current_last_question)
        if mapped_node:
            state["pending_node"] = mapped_node
            logger.info("HEALTH Q&A: Preserved state - mapped '%s' to '%s'", current_last_question, mapped_node)
    
    # Mark Q&A handled without touching data-entry fields
    state["last_question"] = "health_qna_answered"
    
    return state


def product_qna_node(state: State) -> State:
    """Node: Answer product/company questions using QnA API and return to flow."""
    user_question = state.get("user_msg", "")
    conversation_history = state.get("conversation_history", [])
    
    # Extract product name from question if possible
    product_mentioned = None
    user_msg_lower = user_question.lower()
    
    # Product names to check
    product_names = [
        'metabolically lean', 'ams', 'gut cleanse', 'gut balance', 'bye bye bloat',
        'smooth move', 'ibs rescue', 'water kefir', 'kombucha', 'fermented pickles',
        'sleep and calm', 'first defense', 'good to glow', 'pcos balance',
        'good down there', 'happy tummies', 'glycemic control', 'acidity aid', 'metabolic fiber boost',
        'fiber boost', 'happy tummy', 'metabolic fiber'
    ]
    
    # IMPROVED: Use word boundary matching to avoid false positives
    for product in product_names:
        pattern = r'\b' + re.escape(product) + r'\b'
        if re.search(pattern, user_msg_lower):
            product_mentioned = product
            break
    
    # Debug message to help track product questions
    logger.info("PRODUCT QUESTION DETECTED: '%s' - Product: %s", user_question, product_mentioned or 'Not specified')
    
    try:
        # Call the QnA API
        import requests
        qna_url = "http://localhost:8000/ask"  # Assuming QnA API runs on port 8000
        
        # Check for contextual follow-up
        is_contextual = is_contextual_product_question(user_question, conversation_history)
        
        # SMART CONTEXT EXTRACTION: Get only recent messages and extract product
        # Use the same approach as post_plan_qna_node
        recent_messages = conversation_history[-5:] if len(conversation_history) > 5 else conversation_history
        relevant_product = extract_relevant_product_from_history(recent_messages, user_question)
        
        # CRITICAL FIX: If user asks about THEIR OWN product/order, ignore history-based product context
        # and rely only on user_order from state.
        is_my_product_query = any(
            p in user_msg_lower
            for p in [
                # Direct ownership
                "my product",
                "my products",
                "my order",
                "my orders",
                "my purchase",
                "my purchases",

                # What did I buy / get
                "what did i buy",
                "what i bought",
                "what did i purchase",
                "what i purchased",
                "what have i bought",
                "what have i purchased",
                "what did i order",
                "what i ordered",

                # Which product questions
                "which product did i buy",
                "which product i bought",
                "which product did i order",
                "which product i ordered",
                "which product is mine",

                # Possession / reference
                "the product i bought",
                "the product i ordered",
                "the product i purchased",
                "my current product",
                "my latest product",
                "my last order",
                "my recent order",

                # Informal / chat-style
                "what product do i have",
                "what product i have",
                "what am i using",
                "what am i taking",
                "what supplement do i have",
                "what supplement i bought",
            ]
        )

        if state.get("user_order") and is_my_product_query:
            logger.info(
                "OVERRIDE: Detected query about user's own product. "
                "Ignoring history context '%s' to use user_order.", relevant_product
            )
            relevant_product = None
        
        # REFORMULATE QUESTION using GPT-3.5 Turbo (same as post_plan_qna_node)
        if relevant_product and is_contextual:
            reformulated_question = reformulate_with_gpt(user_question, relevant_product, recent_messages)
            logger.info("PRODUCT Q&A GPT REFORMULATED QUESTION: %s", reformulated_question)
            api_question = reformulated_question
        else:
            # For direct product questions or when no relevant product found, use original
            api_question = user_question
        
        # INTELLIGENTLY DETECT health conditions, allergies, and medications from current question and conversation history
        # This will merge existing conditions/allergies/medications with any newly mentioned ones
        # Also handles denials when user says "I don't have this condition"
        health_conditions = extract_health_conditions_intelligently(
            current_question=user_question,
            conversation_history=conversation_history,
            existing_health_conditions=state.get("health_conditions")
        )
        
        allergies = extract_allergies_intelligently(
            current_question=user_question,
            conversation_history=conversation_history,
            existing_allergies=state.get("allergies")
        )
        
        medications = extract_medications_intelligently(
            current_question=user_question,
            conversation_history=conversation_history,
            existing_medications=state.get("medications")
        )

        supplements = extract_supplements_intelligently(
            current_question=user_question,
            conversation_history=conversation_history,
            existing_supplements=state.get("supplements")
        )

        gut_health = extract_gut_health_intelligently(
            current_question=user_question,
            conversation_history=conversation_history,
            existing_gut_health=state.get("gut_health")
        )

        # Update state with newly detected/updated health conditions if they're different
        if health_conditions != state.get("health_conditions"):
            # Only update if we detected something new or removed something (avoid overwriting with empty unnecessarily)
            if health_conditions.strip() and health_conditions.strip().lower() not in ["none", "no", "nothing", "n/a", "na"]:
                state["health_conditions"] = health_conditions
                logger.info("UPDATED STATE | Health conditions updated to: %s", health_conditions)
            elif not health_conditions.strip():  # Empty string means user denied all conditions
                state["health_conditions"] = ""
                logger.info("UPDATED STATE | Health conditions cleared (user denial)")
        
        # Update state with newly detected/updated allergies if they're different
        if allergies != state.get("allergies"):
            # Only update if we detected something new or removed something
            if allergies.strip() and allergies.strip().lower() not in ["none", "no", "nothing", "n/a", "na"]:
                state["allergies"] = allergies
                logger.info("UPDATED STATE | Allergies updated to: %s", allergies)
            elif not allergies.strip():  # Empty string means user denied all allergies
                state["allergies"] = ""
                logger.info("UPDATED STATE | Allergies cleared (user denial)")
        
        # Update state with newly detected/updated medications if they're different
        if medications != state.get("medications"):
            # Only update if we detected something new or removed something
            if medications.strip() and medications.strip().lower() not in ["none", "no", "nothing", "n/a", "na"]:
                state["medications"] = medications
                logger.info("UPDATED STATE | Medications updated to: %s", medications)
            elif not medications.strip():  # Empty string means user denied all medications
                state["medications"] = ""
                logger.info("UPDATED STATE | Medications cleared (user denial)")

        # Update state with newly detected/updated supplements if they're different
        if supplements != state.get("supplements"):
            # Only update if we detected something new or removed something
            if supplements.strip() and supplements.strip().lower() not in ["none", "no", "nothing", "n/a", "na"]:
                state["supplements"] = supplements
                logger.info("UPDATED STATE | Supplements updated to: %s", supplements)
            elif not supplements.strip():  # Empty string means user denied all supplements
                state["supplements"] = ""
                logger.info("UPDATED STATE | Supplements cleared (user denial)")

        # Update state with newly detected/updated gut health if it's different
        if gut_health != state.get("gut_health"):
            # Only update if we detected something new or removed something
            if gut_health.strip() and gut_health.strip().lower() not in ["none", "no", "nothing", "n/a", "na"]:
                state["gut_health"] = gut_health
                logger.info("UPDATED STATE | Gut health updated to: %s", gut_health)
            elif not gut_health.strip():  # Empty string means user denied all gut health issues
                state["gut_health"] = ""
                logger.info("UPDATED STATE | Gut health cleared (user denial)")

        health_context_parts = []
        if health_conditions:
            if isinstance(health_conditions, (list, tuple, set)):
                health_text = ", ".join([str(h) for h in health_conditions if h])
            else:
                health_text = str(health_conditions)
            # Only add if not empty and not "none"
            if health_text.strip() and health_text.strip().lower() not in ["none", "no", "nothing", "n/a", "na"]:
                health_context_parts.append(f"Health conditions: {health_text}")
        
        if allergies:
            if isinstance(allergies, (list, tuple, set)):
                allergies_text = ", ".join([str(a) for a in allergies if a])
            else:
                allergies_text = str(allergies)
            if allergies_text.strip() and allergies_text.strip().lower() not in ["none", "no", "nothing", "n/a", "na"]:
                health_context_parts.append(f"Allergies: {allergies_text}")
        
        if medications:
            if isinstance(medications, (list, tuple, set)):
                medications_text = ", ".join([str(m) for m in medications if m])
            else:
                medications_text = str(medications)
            if medications_text.strip() and medications_text.strip().lower() not in ["none", "no", "nothing", "n/a", "na"]:
                health_context_parts.append(f"Medications: {medications_text}")

        if supplements:
            if isinstance(supplements, (list, tuple, set)):
                supplements_text = ", ".join([str(s) for s in supplements if s])
            else:
                supplements_text = str(supplements)
            if supplements_text.strip() and supplements_text.strip().lower() not in ["none", "no", "nothing", "n/a", "na"]:
                health_context_parts.append(f"Supplements: {supplements_text}")

        if gut_health:
            if isinstance(gut_health, (list, tuple, set)):
                gut_health_text = ", ".join([str(g) for g in gut_health if g])
            else:
                gut_health_text = str(gut_health)
            if gut_health_text.strip() and gut_health_text.strip().lower() not in ["none", "no", "nothing", "n/a", "na"]:
                health_context_parts.append(f"Gut health: {gut_health_text}")

        # Add User Order Context
        user_order = state.get("user_order")
        user_order_date = state.get("user_order_date")
        if user_order and str(user_order).lower() not in ["none", "no", "nil", "nothing"]:
             order_context = f"User's Purchased Product: {user_order}"
             if user_order_date:
                 order_context += f" (Ordered on {user_order_date})"
             health_context_parts.append(order_context)

        # Prepend health context so it's always considered regardless of contextual/non-contextual path
        if health_context_parts:
            api_question = "\n".join(health_context_parts) + "\n\n" + api_question

        response = requests.post(
            qna_url,
            json={
                "question": api_question,
                "model_type": "llama"  # Use optimized prompts for better responses
            },
            timeout=50
        )
        
        if response.status_code == 200:
            qna_data = response.json()
            answer = qna_data.get("answer", "I couldn't find specific information about that. Please contact our support team for detailed product information.")
            category = qna_data.get("category", "general")
            knowledge_status = qna_data.get("knowledge_status", "complete")
            health_warnings = qna_data.get("health_warnings", [])
            
            # If there are health warnings, append them to the answer
            if health_warnings:
                answer = answer + "\n\n" + "\n".join(health_warnings)
            
            # Add emojis based on category with random selection
            if category == "product":
                emoji_prefix = random.choice(["🦠", "🧬", "🧪", "🔬"])
            elif category == "shipping":
                emoji_prefix = random.choice(["📦", "🚚", "🚢", "✈️"])
            elif category == "refund":
                emoji_prefix = random.choice(["💰", "💳", "🧾", "🔄"])
            elif category == "policy":
                emoji_prefix = random.choice(["📋", "📜", "📖", "⚖️"])
            else:
                emoji_prefix = random.choice(["💚", "❤️", "💙", "💜"])
            
            formatted_answer = f"{emoji_prefix} {answer}"
            
        else:
            # Fallback response if API fails
            formatted_answer = "💚 I'd be happy to help with product information! Please contact our support team at tgb@seventurns.in or call +91 8040282085 for detailed product guidance."
            
    except Exception as e:
        logger.error("QnA API Error: %s", e)
        # Fallback response if API is unavailable
        formatted_answer = "💚 I'd love to help with product information! Please contact our support team at tgb@seventurns.in or call +91 8040282085 for detailed product guidance."
    
    # Send the answer
    send_multiple_messages(state["user_id"], formatted_answer, send_whatsapp_message)
    
    # Update conversation history with the current exchange
    if state.get("conversation_history") is None:
        state["conversation_history"] = []
    
    # Add user message to history
    state["conversation_history"].append({
        "role": "user",
        "content": user_question
    })
    
    # Add assistant response to history
    # Use relevant_product (from history) as fallback if product_mentioned (from current question) is not available
    # This ensures contextual follow-ups are properly tagged in conversation history
    product_for_history = product_mentioned or relevant_product
    content = formatted_answer
    if product_for_history:
        content = f"About {product_for_history}: {content}"
    
    state["conversation_history"].append({
        "role": "assistant",
        "content": content
    })
    
    # Keep conversation history manageable (last 20 messages)
    if len(state["conversation_history"]) > 20:
        state["conversation_history"] = state["conversation_history"][-20:]
    
    # Preserve the current state before setting product_qna_answered
    # Map the current last_question to the appropriate pending_node if not already set
    current_last_question = state.get("last_question", "")
    
    # Only update pending_node if it's not already set or if we're in a review/plan state
    if not state.get("pending_node") or current_last_question in [
        "day1_plan_review", "meal_day1_plan_review", "day1_revised_review", "meal_day1_revised_review",
        "awaiting_day1_changes", "awaiting_meal_day1_changes", "day1_complete", "meal_day1_complete",
        "day2_complete", "meal_day2_complete", "day3_complete", "meal_day3_complete",
        "day4_complete", "meal_day4_complete", "day5_complete", "meal_day5_complete",
        "day6_complete", "meal_day6_complete", "exercise_plan_complete", "meal_plan_complete"
    ]:
        # Map last_question to the appropriate node
        question_to_node = {
            # Basic info
            "age": "collect_age",
            "height": "collect_height",
            "weight": "collect_weight",
            "bmi_calculated": "calculate_bmi",
            
            # Meal plan collection
            "health_conditions": "collect_health_conditions",
            "medications": "collect_medications",
            "meal_timing_breakfast": "collect_meal_timing_breakfast",
            "meal_timing_lunch": "collect_meal_timing_lunch",
            "meal_timing_dinner": "collect_meal_timing_dinner",
            "current_breakfast": "collect_current_breakfast",
            "current_lunch": "collect_current_lunch",
            "current_dinner": "collect_current_dinner",
            "diet_preference": "collect_diet_preference",
            "cuisine_preference": "collect_cuisine_preference",
            "allergies": "collect_allergies",
            "water_intake": "collect_water_intake",
            "beverages": "collect_beverages",
            "lifestyle": "collect_lifestyle",
            "activity_level": "collect_activity_level",
            "sleep_stress": "collect_sleep_stress",
            "supplements": "collect_supplements",
            "gut_health": "collect_gut_health",
            "meal_goals": "collect_meal_goals",
            
            # Meal plan generation and review
            "meal_day1_plan_review": "handle_meal_day1_review_choice",
            "awaiting_meal_day1_changes": "collect_meal_day1_changes",
            "meal_day1_revised_review": "handle_meal_day1_revised_review",
            "meal_day1_complete": "generate_all_remaining_meal_days",
            "meal_day2_complete": "generate_meal_day3_plan",
            "meal_day3_complete": "generate_meal_day4_plan",
            "meal_day4_complete": "generate_meal_day5_plan",
            "meal_day5_complete": "generate_meal_day6_plan",
            "meal_day6_complete": "generate_meal_day7_plan",
            
            # Exercise plan collection
            "fitness_level": "collect_fitness_level",
            "activity_types": "collect_activity_types",
            "exercise_frequency": "collect_exercise_frequency",
            "exercise_intensity": "collect_exercise_intensity",
            "session_duration": "collect_session_duration",
            "sedentary_time": "collect_sedentary_time",
            "exercise_goals": "collect_exercise_goals",
            
            # Exercise plan generation and review
            "day1_plan_review": "handle_day1_review_choice",
            "awaiting_day1_changes": "collect_day1_changes",
            "day1_revised_review": "handle_day1_revised_review",
            "day1_complete": "generate_all_remaining_exercise_days",
            "day2_complete": "generate_day3_plan",
            "day3_complete": "generate_day4_plan",
            "day4_complete": "generate_day5_plan",
            "day5_complete": "generate_day6_plan",
            "day6_complete": "generate_day7_plan",
        }
        
        # Set pending_node based on current last_question
        mapped_node = question_to_node.get(current_last_question)
        if mapped_node:
            state["pending_node"] = mapped_node
            logger.info("PRODUCT Q&A: Preserved state - mapped '%s' to '%s'", current_last_question, mapped_node)
    
    # Set state to indicate product Q&A is answered
    state["last_question"] = "product_qna_answered"
    
    return state


def is_contextual_product_question(user_msg: str, conversation_history: list) -> bool:
    """Check if a question is likely about products based on recent conversation context."""
    if not conversation_history:
        return False
    
    # IMPROVED: Dynamic window size based on conversation length
    # Use larger window for longer conversations, but cap at 16 messages
    conversation_length = len(conversation_history)
    if conversation_length <= 10:
        window_size = 8
    elif conversation_length <= 20:
        window_size = 12
    else:
        window_size = 16
    
    # Look at the last few messages for product context
    recent_messages = conversation_history[-window_size:]
    recent_text = " ".join([msg.get("content", "") for msg in recent_messages]).lower()
    
    # IMPROVED: More comprehensive product names list
    product_names = [
        'metabolically lean', 'ams', 'gut cleanse', 'gut balance', 'bye bye bloat',
        'smooth move', 'ibs rescue', 'water kefir', 'kombucha', 'fermented pickles',
        'sleep and calm', 'first defense', 'good to glow', 'pcos balance',
        'good down there', 'happy tummies', 'glycemic control', 'acidity aid', 'metabolic fiber boost',
        'fiber boost', 'happy tummy', 'metabolic fiber', 'the good bug', 'products', 'product',
        'acidity aid', 'ibs dnm', 'ibs rescue d&m', 'ibs c', 'ibs d', 'ibs m', 
        'gut cleanse detox shot', 'gut cleanse shot', 'prebiotic fiber boost', 
        'smooth move fiber boost', 'constipation bundle', 'pcos bundle', 
        'metabolically lean supercharged', 'ferments', 'squat buddy', 'probiotics', 'prebiotics'
    ]
    
    # IMPROVED: Check for product mentions in the entire recent window
    product_mentioned = False
    mentioned_product = None
    product_position = -1
    
    # Find the most recent product mention within the window
    for i, msg in enumerate(recent_messages):
        content = msg.get("content", "").lower()
        for product in product_names:
            # IMPROVED: Use word boundary matching to avoid false positives
            # This prevents "bloat" from matching "bloating"
            pattern = r'\b' + re.escape(product) + r'\b'
            if re.search(pattern, content):
                product_mentioned = True
                mentioned_product = product
                product_position = i
                break
        if product_mentioned:
            break
    
    # If we found a product mention, check if the current message is a follow-up
    if product_mentioned:
        user_msg_lower = user_msg.lower()
        
        # IMPROVED: Enhanced follow-up patterns
        follow_up_patterns = [
            'how to take', 'how to consume', 'how to use', 'when to take',
            'can i take', 'can i mix', 'can i use', 'can i consume',
            'with other', 'with drinks', 'with food', 'with milk', 'with water',
            'side effects', 'dosage', 'timing', 'take it', 'use it', 'consume it',
            'mix it', 'how much', 'how often', 'is it safe', 'best time',
            'empty stomach', 'with meals', 'before eating', 'after eating',
            'how do i', 'how should i', 'when should i', 'instructions', 'direction',
            'how many', 'benefits', 'effect', 'work', 'does it', 'is it', 'can it',
            'price', 'cost', 'where', 'buy', 'purchase', 'order', 'precaustions', 'precautions', 'take it', 'use it', 'consume it',
            # IMPROVED: Additional patterns
            'what about', 'how about', 'tell me about', 'explain', 'describe',
            'is this', 'is that', 'are these', 'are those', 'will it', 'would it',
            'can i use', 'should i use', 'when can i', 'how can i', 'why should i',
            # FIXED: Time-related follow-up patterns
            'how long', 'how long should', 'how long does', 'how long to', 'how long will',
            'when will', 'when should', 'how soon', 'how quickly', 'how fast',
            'time to', 'wait to', 'see results', 'take effect', 'start working'
        ]
        
        # FIXED: Exclude general health/nutrition questions that should NOT be contextual
        general_health_patterns = [
            'meal timings', 'meal timing', 'breakfast time', 'lunch time', 'dinner time',
            'when to eat', 'eating schedule', 'meal schedule', 'food timing',
            'perfect timing', 'should i change', 'make changes', 'adjust',
            'current timings', 'current timing', 'my timings', 'my timing',
            'meal plan', 'diet plan', 'nutrition plan', 'eating plan',
            'weight loss', 'weight gain', 'fitness', 'exercise', 'workout',
            'health advice', 'nutrition advice', 'diet advice', 'lifestyle advice',
            'general health', 'overall health', 'wellness', 'healthy lifestyle',
            # CRITICAL: Meal preparation and ingredient-related patterns
            'ingredients', 'my meals', 'my meal', 'for my meals', 'for my meal',
            'grocery', 'shopping list', 'recipe', 'recipes', 'to order for',
            'what to buy', 'what to order', 'ingredients for', 'ingredients to',
            'food items', 'grocery list', 'meal prep', 'meal preparation',
            'cooking', 'prepare', 'make my meals', 'cook my meals'
        ]
        
        # Check for direct pattern matches
        direct_match = any(pattern in user_msg_lower for pattern in follow_up_patterns)
        
        # FIXED: Check if it's a general health question that should NOT be contextual
        is_general_health = any(pattern in user_msg_lower for pattern in general_health_patterns)
        
        # IMPROVED: Better pronoun detection
        pronoun_patterns = ['it', 'this', 'that', 'these', 'those', 'they', 'them', 'its', 'itself']
        has_pronoun = any(pronoun in user_msg_lower.split() for pronoun in pronoun_patterns)
        
        # Check if the product name is directly mentioned in the question
        product_in_question = mentioned_product and mentioned_product in user_msg_lower
        
        # IMPROVED: More flexible short question detection
        is_short_question = len(user_msg_lower.split()) <= 6
        
        # IMPROVED: Check if the message is likely a follow-up based on position
        # If product was mentioned recently (within last 6 messages), more likely to be follow-up
        is_recent_product_mention = product_position >= (len(recent_messages) - 6)
        
        # FIXED: Enhanced logic for contextual detection with exclusion of general health questions
        is_contextual = (
            (direct_match and not is_general_health) or 
            (has_pronoun and is_short_question and not is_general_health) or 
            product_in_question or
            (is_recent_product_mention and is_short_question and has_pronoun and not is_general_health) or
            # FIXED: Also detect longer follow-up questions with pronouns if product was mentioned recently
            (has_pronoun and is_recent_product_mention and not is_general_health)
        )
        
        # Debug logging for contextual detection
        if is_contextual:
            logger.debug("CONTEXTUAL DETECTION | Question: '%s' | Product: %s | Direct match: %s | Has pronoun: %s | Recent mention: %s | General health: %s", user_msg, mentioned_product, direct_match, has_pronoun, is_recent_product_mention, is_general_health)
        elif is_general_health:
            logger.debug("CONTEXTUAL DETECTION | Question: '%s' | Product: %s | EXCLUDED as general health question", user_msg, mentioned_product)
        
        return is_contextual
    
    return False


def extract_relevant_product_from_history(recent_messages: list, current_question: str) -> str:
    """Extract the most relevant product name from recent conversation history."""
    product_names = [
        'metabolically lean', 'metabolic fiber boost', 'ams', 'metabolically lean - probiotics',
        'advanced metabolic system', 'gut cleanse', 'gut balance', 'bye bye bloat',
        'smooth move', 'ibs rescue', 'water kefir', 'kombucha', 'fermented pickles',
        'prebiotic shots', 'sleep and calm', 'first defense', 'good to glow',
        'pcos balance', 'good down there', 'fiber boost', 'happy tummy', 'metabolic fiber',
        'happy tummies', 'glycemic control', 'gut cleanse super bundle',
        'acidity aid', 'ibs dnm', 'ibs rescue d&m', 'ibs c', 'ibs d', 'ibs m',
        'gut cleanse detox shot', 'gut cleanse shot', 'prebiotic fiber boost',
        'smooth move fiber boost', 'constipation bundle', 'pcos bundle',
        'metabolically lean supercharged', 'ferments', 'squat buddy'
    ]
    
    # FIXED: Check if current question is a general health question that should NOT extract products
    general_health_patterns = [
        'meal timings', 'meal timing', 'breakfast time', 'lunch time', 'dinner time',
        'when to eat', 'eating schedule', 'meal schedule', 'food timing',
        'perfect timing', 'should i change', 'make changes', 'adjust',
        'current timings', 'current timing', 'my timings', 'my timing',
        'meal plan', 'diet plan', 'nutrition plan', 'eating plan',
        'weight loss', 'weight gain', 'fitness', 'exercise', 'workout',
        'health advice', 'nutrition advice', 'diet advice', 'lifestyle advice',
        'general health', 'overall health', 'wellness', 'healthy lifestyle',
        # CRITICAL: Meal preparation and ingredient-related patterns
        'ingredients', 'my meals', 'my meal', 'for my meals', 'for my meal',
        'grocery', 'shopping list', 'recipe', 'recipes', 'to order for',
        'what to buy', 'what to order', 'ingredients for', 'ingredients to',
        'food items', 'grocery list', 'meal prep', 'meal preparation',
        'cooking', 'prepare', 'make my meals', 'cook my meals'
    ]
    
    current_question_lower = current_question.lower()
    
    # If it's a general health question, don't extract products from history
    if any(pattern in current_question_lower for pattern in general_health_patterns):
        logger.debug("EXTRACTED PRODUCT | Question '%s' is general health - not extracting products", current_question)
        return ""
    
    # Check current question first for direct mentions
    for product in product_names:
        if re.search(r'\b' + re.escape(product) + r'\b', current_question_lower):
            return product
    
    # If no product in current question, check recent messages (most recent first)
    for message in reversed(recent_messages):
        content = message.get('content', '').lower()
        for product in product_names:
            if re.search(r'\b' + re.escape(product) + r'\b', content):
                logger.debug("EXTRACTED PRODUCT | Found '%s' in message: '%s...'", product, content[:50])
                return product
    
    logger.debug("EXTRACTED PRODUCT | No product found for question: '%s'", current_question)
    return ""



def reformulate_with_gpt(question: str, product: str, recent_messages: list) -> str:
    """Use Bedrock LLM to reformulate follow-up questions to be self-contained."""
    try:
        from app.services.llm.bedrock_llm import BedrockLLM
        
        # Initialize Bedrock LLM client
        client = BedrockLLM(temperature=0.1, max_tokens=50)
        
        # Build minimal context from recent messages
        conversation_context = "\n".join([
            f"{msg.get('role', 'unknown')}: {msg.get('content', '')}" 
            for msg in recent_messages[-3:]  # Last 3 messages for context
        ])
        
        reformulation_prompt = f"""Your task is to create a simple, self-contained question by combining a product name with a user's follow-up question.
Do NOT change the user's original phrasing or add any new information. Just add the product name to make the question specific and clear.

IMPORTANT RULES:
1. Keep the user's original wording as much as possible
2. Only add the product name to clarify what "it" or "this" refers to
3. Make the question standalone and clear without needing context
4. Keep it concise - one sentence only
5. Don't add any explanations, just output the reformulated question

---
**Examples:**
- CURRENT PRODUCT: bye bye bloat
- FOLLOW-UP QUESTION: how do i take it?
- Reformulated Question: how do i take bye bye bloat?

- CURRENT PRODUCT: metabolically lean
- FOLLOW-UP QUESTION: what about the price
- Reformulated Question: what is the price for metabolically lean

- CURRENT PRODUCT: pcos balance
- FOLLOW-UP QUESTION: is it safe with other medicines
- Reformulated Question: is pcos balance safe with other medicines

- CURRENT PRODUCT: gut cleanse
- FOLLOW-UP QUESTION: when should i use this
- Reformulated Question: when should i use gut cleanse

- CURRENT PRODUCT: metabolic fiber boost
- FOLLOW-UP QUESTION: how long does it take to work
- Reformulated Question: how long does metabolic fiber boost take to work
---

**Now reformulate this:**
CONVERSATION CONTEXT (for reference only):
{conversation_context}

CURRENT PRODUCT: {product}
FOLLOW-UP QUESTION: {question}

Reformulated Question:"""
        
        # Use Bedrock LLM with system and user messages
        messages = [
            {"role": "system", "content": "You are a helpful assistant that reformulates follow-up questions to be self-contained by adding product names. Always respond with just the reformulated question, no explanations."},
            {"role": "user", "content": reformulation_prompt}
        ]
        
        response = client.invoke(messages)
        reformulated = response.content.strip()
        
        # Clean up the response - remove quotes if present
        reformulated = reformulated.replace('"', '').replace("'", "")
        
        # Validate that the reformulated question contains the product
        if product.lower() not in reformulated.lower():
            logger.warning("Warning: Bedrock reformulation didn't include product '%s' in: %s", product, reformulated)
            # Fallback: use simple reformulation
            return f"{question} about {product}"
        
        return reformulated
        
    except Exception as e:
        logger.error("Bedrock reformulation error: %s", e)
        # Fallback to simple rule-based reformulation
        return reformulate_followup_fallback(question, product)



def reformulate_followup_fallback(question: str, product: str) -> str:
    """Fallback rule-based reformulation if GPT fails."""
    question_lower = question.lower()
    
    # Common follow-up patterns with better handling
    if any(word in question_lower for word in ['how do i take', 'how to take', 'how should i take']):
        return f"how to take {product}"
    elif any(word in question_lower for word in ['how do i use', 'how to use', 'how should i use']):
        return f"how to use {product}"
    elif any(word in question_lower for word in ['price', 'cost', 'how much']):
        return f"what is the price of {product}"
    elif any(word in question_lower for word in ['safe', 'side effect', 'risk', 'interaction']):
        return f"is {product} safe"
    elif any(word in question_lower for word in ['work', 'effect', 'result', 'benefit']):
        return f"how does {product} work"
    elif any(word in question_lower for word in ['when', 'time', 'duration']):
        return f"when to take {product}"
    elif any(word in question_lower for word in ['how long']):
        return f"how long does {product} take to work"
    else:
        # Default: just prepend the product name or add "about product"
        if question_lower.startswith(('what', 'how', 'when', 'where', 'why', 'is', 'can', 'does')):
            return f"{question} {product}"
        else:
            return f"{question} about {product}"



def is_user_providing_information(text: str) -> bool:
    """
    STRICT CHECK: Determine if user is PROVIDING/STATING information about themselves
    vs ASKING questions or making inquiries.
    
    Returns True ONLY if user is clearly stating facts about themselves.
    Returns False if user is asking questions, making inquiries, or being vague.
    """
    if not text:
        return False
    
    text_lower = text.strip().lower()
    words = text_lower.split()
    
    # CRITICAL: If it has question indicators, it's NOT providing information
    question_indicators = [
        '?',  # Question mark is the strongest indicator
        'what', 'how', 'why', 'when', 'where', 'who', 'which', 'whom', 'whose',
        'can you', 'could you', 'would you', 'should i', 'will you', 'shall i', 'may i', 'might i',
        'do you', 'does it', 'did you', 'is it', 'are there', 'was it', 'were there',
        'tell me', 'show me', 'explain', 'help me', 'recommend',
        'can i', 'could i', 'should i', 'would i', 'will i',
        'do i', 'does', 'did', 'is there', 'are there', 'has it', 'have you',
        'more about', 'tell me about', 'know about', 'learn about', 'hear about',
        'information about', 'details about', 'info about', 'tell me more',
        'what about', 'how about', 'anything about', 'something about'
    ]
    
    # If ANY question indicator is present, user is asking, not stating
    if any(indicator in text_lower for indicator in question_indicators):
        return False
    
    # CRITICAL: Check for inquiry/request patterns
    inquiry_patterns = [
        'tell me', 'show me', 'explain', 'describe', 'help', 'advice',
        'suggest', 'recommend', 'guide', 'assist', 'provide', 'give me',
        'share', 'looking for', 'want to know', 'need to know', 'curious',
        'wondering', 'interested in', 'more info', 'more information',
        'more details', 'elaborate', 'clarify', 'specify'
    ]
    
    if any(pattern in text_lower for pattern in inquiry_patterns):
        return False
    
    # POSITIVE INDICATORS: User is stating facts about themselves
    # These patterns indicate the user is providing information
    statement_indicators = [
        'i have', 'i am', 'i\'m', 'i take', 'i use', 'i suffer from',
        'i experience', 'i get', 'i was diagnosed', 'i\'ve been diagnosed',
        'diagnosed with', 'suffering from', 'dealing with',
        'my condition', 'my health', 'my medication', 'my supplement',
        'i\'m allergic', 'allergic to', 'intolerant to', 'sensitive to',
        'i don\'t have', 'i do not have', 'i\'m not', 'i am not',
        'no health', 'no condition', 'no medication', 'no supplement', 
        'no allergy', 'none', 'not allergic'
    ]
    
    # Check if user is making a statement about themselves
    has_statement_indicator = any(indicator in text_lower for indicator in statement_indicators)
    
    # Additional check: First-person pronouns indicating self-disclosure
    first_person_patterns = ['i ', 'my ', 'me ', 'i\'m ', 'i\'ve ', 'i have ', 'i take ', 'i use ']
    has_first_person = any(text_lower.startswith(pattern) or f' {pattern}' in text_lower for pattern in first_person_patterns)
    
    # User must have BOTH statement indicators AND first-person reference to be providing info
    # OR have strong statement indicators
    if has_statement_indicator or has_first_person:
        # Double-check: make sure it's not a question disguised as a statement
        # e.g., "Should I take medication if I have diabetes?"
        if '?' in text or any(q in text_lower for q in ['should i', 'can i', 'do i', 'would i', 'could i']):
            return False
        return True
    
    # Default: if we can't clearly identify it as a statement, assume it's NOT providing info
    return False



def extract_health_conditions_intelligently(
current_question: str, 
    conversation_history: Optional[list], 
    existing_health_conditions: Optional[str]
) -> str:
    """
    Intelligently detect health conditions from current question and conversation history.
    Merges with existing health conditions from state.
    Handles denials/removals when user says "I don't have this condition".
    
    IMPROVED: Now captures diverse conditions including severity levels, frequency modifiers,
    and a wide range of medical conditions beyond common ones.
    
    STRICT GUARDRAIL: ONLY extracts if user is explicitly PROVIDING/STATING information.
    If user is asking questions or making inquiries, returns existing data unchanged.
    
    Returns: Combined health conditions string (comma-separated)
    """
    try:
        # Handle None conversation_history
        if conversation_history is None:
            conversation_history = []
        
        # STRICT GUARDRAIL: User must be PROVIDING information, not asking questions
        # This prevents false positives like "tell me more about ams" being interpreted as supplements
        if not is_user_providing_information(current_question):
            logger.info("HEALTH CONDITIONS GUARDRAIL | User is NOT providing information (asking/inquiring instead). Skipping extraction. Returning existing: %s", existing_health_conditions or '')
            return existing_health_conditions or ""
        
        # Check for denial patterns first (user saying they don't have a condition)
        current_lower = current_question.lower()
        denial_patterns = [
            "i don't have", "i do not have", "i don't have that", "i do not have that",
            "i don't have this", "i do not have this", "i don't have any",
            "i have no", "i don't suffer from", "i do not suffer from",
            "that's not correct", "that is not correct", "incorrect", "wrong",
            "i don't have", "no i don't have", "actually i don't have",
            "remove", "not true", "that's wrong", "that is wrong"
        ]
        
        is_denial = any(pattern in current_lower for pattern in denial_patterns)
        
        # If it's a denial, try to identify which condition they're denying
        if is_denial and existing_health_conditions:
            # Look at recent assistant messages to see what condition was mentioned
            recent_assistant_messages = []
            if conversation_history:
                for msg in reversed(conversation_history[-5:]):  # Check last 5 messages
                    if msg.get('role') == 'assistant':
                        recent_assistant_messages.append(msg.get('content', ''))
            
            # Use LLM to identify which condition is being denied
            denial_prompt = f"""The user is saying they don't have a health condition that was mentioned.
Identify which specific health condition(s) they are denying/removing.

EXISTING HEALTH CONDITIONS: {existing_health_conditions}
CURRENT USER MESSAGE: {current_question}
RECENT ASSISTANT MESSAGES (for context):
{chr(10).join(recent_assistant_messages[-2:]) if recent_assistant_messages else 'None'}

Return ONLY the health condition(s) they are denying (comma-separated), or "none" if you can't identify.
Examples:
•⁠  ⁠"I don't have PCOS" → PCOS
•⁠  ⁠"I don't have that condition" → identify from context
•⁠  ⁠"That's wrong, I don't have diabetes" → diabetes
•⁠  ⁠"Actually I don't have IBS" → IBS

Return only the condition name(s), nothing else:"""


            try:
                denial_response = llm.invoke(denial_prompt)
                denied_conditions = denial_response.content.strip().lower()
                
                # Clean up response
                denied_conditions = denied_conditions.replace('"', '').replace("'", "").strip()
                if denied_conditions in ["none", "no", "nothing", "n/a", "na", ""]:
                    denied_conditions = ""
                
                # Remove denied conditions from existing
                if denied_conditions:
                    existing_list = [c.strip() for c in existing_health_conditions.split(",") if c.strip()]
                    denied_list = [c.strip() for c in denied_conditions.split(",") if c.strip()]
                    
                    # Remove denied conditions (case-insensitive match)
                    remaining_conditions = []
                    for condition in existing_list:
                        condition_lower = condition.lower()
                        should_remove = False
                        for denied in denied_list:
                            if denied in condition_lower or condition_lower in denied:
                                should_remove = True
                                break
                        if not should_remove:
                            remaining_conditions.append(condition)
                    
                    result = ", ".join(remaining_conditions) if remaining_conditions else ""
                    logger.info("HEALTH CONDITIONS DENIAL | Denied: %s | Remaining: %s", denied_conditions, result)
                    return result
            except Exception as e:
                logger.error("Error processing denial: %s", e)
                # Continue with normal extraction if denial processing fails
        
        # Normal extraction flow (not a denial)
        # Collect all text to analyze
        text_to_analyze = current_question
        
        # Include recent conversation history (last 10 messages for context)
        if conversation_history:
            recent_messages = conversation_history[-10:]
            conversation_text = "\n".join([
                f"{msg.get('role', 'unknown')}: {msg.get('content', '')}" 
                for msg in recent_messages
            ])
            text_to_analyze = f"{conversation_text}\n\nCurrent question: {current_question}"
        
        # Use LLM to extract health conditions intelligently
        extraction_prompt = f"""Extract ONLY the health conditions, medical issues, or symptoms that the user EXPLICITLY STATES they have in the conversation below.

CRITICAL VALIDATION: The user must be STATING/DECLARING they have a condition, NOT asking about it.
- "I have diabetes" → VALID (user is stating)
- "tell me about diabetes" → INVALID (user is asking)
- "what is AMS" → INVALID (user is inquiring)
- "I suffer from IBS" → VALID (user is stating)

CRITICAL RULE: Do NOT infer, assume, or add conditions that are not directly stated by the user.
DO NOT add related conditions, complications, or secondary health issues.
ONLY extract what the user directly says they have.

STRICT GUIDELINES:
1. Extract ONLY what is explicitly STATED as something the user HAS:
   - "I have diabetes" → diabetes ✓
   - "occasional bloating" → occasional bloating ✓
   - "I get migraines" → migraines ✓
   - "my anxiety" → anxiety ✓
   - "tell me about diabetes" → NOTHING (this is a question, not a statement) ✗
   - "what is PCOS" → NOTHING (this is a question) ✗

2. DO NOT extract from questions or inquiries:
   - If the text contains question words (what, how, why, tell me, explain), DO NOT extract
   - If the user is asking ABOUT a condition, they are NOT stating they have it
   - Only extract when user is DECLARING/STATING they have something

3. PRESERVE QUALIFIERS AND SEVERITY as stated by the user:
   - Keep frequency modifiers: "occasional bloating", "frequent headaches", "chronic pain"
   - Keep severity levels if mentioned: "mild anxiety", "severe IBS"
   - Keep descriptors: "intermittent", "persistent"

4. Handle various phrasings of the same condition:
   - "I'm diabetic" → diabetes
   - "I have diabetes" → diabetes
   - "I was diagnosed with PCOS" → PCOS
   - "I get bloated" → bloating

5. If user says "none", "no health conditions", "I don't have anything", return empty string

6. Return ONLY a comma-separated list with conditions AS STATED by the user:
   Examples:
   - "I have diabetes and occasional bloating" → "diabetes, occasional bloating"
   - "I get migraines" → "migraines"
   - "tell me about diabetes" → "" (EMPTY - this is a question)
   - "what is IBS" → "" (EMPTY - this is a question)
   - "nothing" → ""

7. DO NOT standardize, infer, or add conditions. Be EXTREMELY strict about this!

EXISTING HEALTH CONDITIONS FROM PROFILE: {existing_health_conditions or "None"}

CONVERSATION AND CURRENT QUESTION:
{text_to_analyze}

Extract ONLY explicitly mentioned health conditions that the user STATES they have (preserving qualifiers). Return comma-separated list only, or empty string if none found:"""

        response = llm.invoke(extraction_prompt)
        extracted_conditions = response.content.strip()
        
        # Clean up the response - remove quotes, extra whitespace
        extracted_conditions = extracted_conditions.replace('"', '').replace("'", "").strip()
        
        # If LLM returned explanatory text, try to extract just the conditions
        # Look for patterns like "Health conditions: ..." or just extract comma-separated items
        if ":" in extracted_conditions:
            # Try to extract after colon
            parts = extracted_conditions.split(":", 1)
            if len(parts) > 1:
                extracted_conditions = parts[1].strip()
        
        # Remove common prefixes/suffixes that LLM might add
        prefixes_to_remove = [
            "health conditions:", "conditions:", "health issues:", 
            "the user has:", "extracted conditions:", "mentioned:",
            "health condition:", "medical conditions:"
        ]
        extracted_conditions_lower = extracted_conditions.lower()
        for prefix in prefixes_to_remove:
            if extracted_conditions_lower.startswith(prefix):
                extracted_conditions = extracted_conditions[len(prefix):].strip()
        
        # Normalize: remove empty, none, no entries
        if extracted_conditions.lower() in ["none", "no", "nothing", "n/a", "na", ""]:
            extracted_conditions = ""
        
        # Merge with existing health conditions
        existing_conditions = existing_health_conditions or ""
        existing_conditions = existing_conditions.strip()
        
        # Normalize existing conditions too
        if existing_conditions.lower() in ["none", "no", "nothing", "n/a", "na"]:
            existing_conditions = ""
        
        # If both are empty, return empty
        if not extracted_conditions and not existing_conditions:
            return ""
        
        # If only one has values, return that one
        if not extracted_conditions:
            return existing_conditions
        if not existing_conditions:
            return extracted_conditions
        
        # Merge both - combine unique conditions
        # Split by comma and clean up
        existing_list = [c.strip() for c in existing_conditions.split(",") if c.strip()]
        extracted_list = [c.strip() for c in extracted_conditions.split(",") if c.strip()]
        
        # Combine and deduplicate (case-insensitive)
        combined_conditions = existing_list.copy()
        for extracted in extracted_list:
            # Check if already exists (case-insensitive)
            # For conditions with qualifiers, do a more nuanced check
            already_exists = False
            for existing in combined_conditions:
                # Exact match (case-insensitive)
                if existing.lower() == extracted.lower():
                    already_exists = True
                    break
                # Check if it's the same base condition with different qualifiers
                # e.g., "bloating" vs "occasional bloating" - keep both for now
                # This preserves user's specific input
            
            if not already_exists:
                combined_conditions.append(extracted)
        
        # Return comma-separated string
        result = ", ".join(combined_conditions)
        logger.info("HEALTH CONDITIONS DETECTED | Existing: %s | Extracted: %s | Combined: %s", existing_conditions, extracted_conditions, result)
        return result
        
    except Exception as e:
        logger.error("Error extracting health conditions intelligently: %s", e)
        # Fallback to existing conditions only
        return existing_health_conditions or ""


def extract_allergies_intelligently(
    current_question: str, 
    conversation_history: Optional[list], 
    existing_allergies: Optional[str]
) -> str:
    """
    Intelligently detect allergies from current question and conversation history.
    Merges with existing allergies from state.
    Handles denials/removals when user says "I'm not allergic to X".
    
    IMPROVED: Now captures diverse allergies including severity levels, reaction types,
    and a wide range of allergens beyond common food allergies.

    STRICT GUARDRAIL: ONLY extracts if user is explicitly PROVIDING/STATING information.
    If user is asking questions or making inquiries, returns existing data unchanged.

    Returns: Combined allergies string (comma-separated)
    """
    try:
        # Handle None conversation_history
        if conversation_history is None:
            conversation_history = []
        
        # STRICT GUARDRAIL: User must be PROVIDING information, not asking questions
        # This prevents false positives like "tell me about dairy allergies" being interpreted as having dairy allergy
        if not is_user_providing_information(current_question):
            logger.info("ALLERGIES GUARDRAIL | User is NOT providing information (asking/inquiring instead). Skipping extraction. Returning existing: %s", existing_allergies or '')
            return existing_allergies or ""
        
        # Check for denial patterns first (user saying they're not allergic)
        current_lower = current_question.lower()
        denial_patterns = [
            "i'm not allergic", "i am not allergic", "i'm not allergic to",
            "i don't have allergies", "i do not have allergies", "i don't have any allergies",
            "no allergies", "i have no allergies", "not allergic",
            "that's not correct", "that is not correct", "incorrect", "wrong",
            "i don't have that allergy", "i do not have that allergy",
            "remove", "not true", "that's wrong", "that is wrong"
        ]
        
        is_denial = any(pattern in current_lower for pattern in denial_patterns)
        
        # If it's a denial, try to identify which allergy they're denying
        if is_denial and existing_allergies:
            # Look at recent assistant messages to see what allergy was mentioned
            recent_assistant_messages = []
            if conversation_history:
                for msg in reversed(conversation_history[-5:]):  # Check last 5 messages
                    if msg.get('role') == 'assistant':
                        recent_assistant_messages.append(msg.get('content', ''))
            
            # Use LLM to identify which allergy is being denied
            denial_prompt = f"""The user is saying they don't have an allergy that was mentioned.
Identify which specific allergy/allergies they are denying/removing.

EXISTING ALLERGIES: {existing_allergies}
CURRENT USER MESSAGE: {current_question}
RECENT ASSISTANT MESSAGES (for context):
{chr(10).join(recent_assistant_messages[-2:]) if recent_assistant_messages else 'None'}

Return ONLY the allergy/allergies they are denying (comma-separated), or "none" if you can't identify.
Examples:
- "I'm not allergic to nuts" → nuts
- "I don't have that allergy" → identify from context
- "That's wrong, I'm not allergic to dairy" → dairy
- "Actually I'm not allergic to shellfish" → shellfish

Return only the allergy name(s), nothing else:"""

            try:
                denial_response = llm.invoke(denial_prompt)
                denied_allergies = denial_response.content.strip().lower()
                
                # Clean up response
                denied_allergies = denied_allergies.replace('"', '').replace("'", "").strip()
                if denied_allergies in ["none", "no", "nothing", "n/a", "na", ""]:
                    denied_allergies = ""
                
                # Remove denied allergies from existing
                if denied_allergies:
                    existing_list = [a.strip() for a in existing_allergies.split(",") if a.strip()]
                    denied_list = [a.strip() for a in denied_allergies.split(",") if a.strip()]
                    
                    # Remove denied allergies (case-insensitive match)
                    remaining_allergies = []
                    for allergy in existing_list:
                        allergy_lower = allergy.lower()
                        should_remove = False
                        for denied in denied_list:
                            if denied in allergy_lower or allergy_lower in denied:
                                should_remove = True
                                break
                        if not should_remove:
                            remaining_allergies.append(allergy)
                    
                    result = ", ".join(remaining_allergies) if remaining_allergies else ""
                    logger.info("ALLERGIES DENIAL | Denied: %s | Remaining: %s", denied_allergies, result)
                    return result
            except Exception as e:
                logger.error("Error processing allergy denial: %s", e)
                # Continue with normal extraction if denial processing fails
        
        # Normal extraction flow (not a denial)
        # Collect all text to analyze
        text_to_analyze = current_question
        
        # Include recent conversation history (last 10 messages for context)
        if conversation_history:
            recent_messages = conversation_history[-10:]
            conversation_text = "\n".join([
                f"{msg.get('role', 'unknown')}: {msg.get('content', '')}" 
                for msg in recent_messages
            ])
            text_to_analyze = f"{conversation_text}\n\nCurrent question: {current_question}"
        
        # Use LLM to extract allergies intelligently
        extraction_prompt = f"""Extract ONLY the allergies, food intolerances, or sensitivities that the user EXPLICITLY STATES they have in the conversation below.

CRITICAL VALIDATION: The user must be STATING/DECLARING they have an allergy, NOT asking about it.
- "I'm allergic to peanuts" → VALID (user is stating)
- "tell me about peanut allergies" → INVALID (user is asking)
- "what are dairy allergies" → INVALID (user is inquiring)
- "I have lactose intolerance" → VALID (user is stating)

CRITICAL RULE: Do NOT infer, assume, or add allergies that are not directly stated by the user.
DO NOT add related allergies, cross-contaminations, or potential allergens.
ONLY extract what the user directly says they are allergic/intolerant to.

STRICT GUIDELINES:
1. Extract ONLY what is explicitly STATED as something the user HAS:
   - "I'm allergic to peanuts" → peanuts ✓
   - "I'm lactose intolerant" → lactose intolerance ✓
   - "I have a shellfish allergy" → shellfish allergy ✓
   - "sensitive to gluten" → gluten sensitivity ✓
   - "tell me about dairy allergies" → NOTHING (this is a question) ✗
   - "what is gluten intolerance" → NOTHING (this is a question) ✗

2. DO NOT extract from questions or inquiries:
   - If the text contains question words (what, how, why, tell me, explain), DO NOT extract
   - If the user is asking ABOUT an allergy, they are NOT stating they have it
   - Only extract when user is DECLARING/STATING they have an allergy

3. PRESERVE QUALIFIERS AND SEVERITY as stated by the user:
   - Keep severity: "severe peanut allergy", "mild dairy intolerance"
   - Keep reaction types if mentioned: "contact allergy", "hives from strawberries"
   - Keep descriptors: "seasonal", "anaphylactic", "life-threatening"

4. Handle various phrasings of the same allergy:
   - "I'm allergic to peanuts" → peanuts (or peanut allergy)
   - "I have a nut allergy" → nut allergy
   - "I'm lactose intolerant" → lactose intolerance
   - "eggs make me sick" → eggs (or egg allergy)

5. If user says "none", "no allergies", "I don't have any", return empty string

6. Return ONLY a comma-separated list with allergies AS STATED by the user:
   Examples:
   - "I'm allergic to dairy and shellfish" → "dairy, shellfish"
   - "tell me about nut allergies" → "" (EMPTY - this is a question)
   - "what is lactose intolerance" → "" (EMPTY - this is a question)
   - If user says "I have a severe peanut allergy" → "severe peanut allergy"
   - If user says "lactose intolerance" → "lactose intolerance"
   - If user says "nothing" → ""

7. DO NOT standardize, infer, or add allergies. Be strict about this!

EXISTING ALLERGIES FROM PROFILE: {existing_allergies or "None"}

CONVERSATION AND CURRENT QUESTION:
{text_to_analyze}

Extract ONLY explicitly mentioned allergies/intolerances (preserving qualifiers). Return comma-separated list only, or empty string if none found:"""

        response = llm.invoke(extraction_prompt)
        extracted_allergies = response.content.strip()
        
        # Clean up the response - remove quotes, extra whitespace
        extracted_allergies = extracted_allergies.replace('"', '').replace("'", "").strip()
        
        # If LLM returned explanatory text, try to extract just the allergies
        if ":" in extracted_allergies:
            parts = extracted_allergies.split(":", 1)
            if len(parts) > 1:
                extracted_allergies = parts[1].strip()
        
        # Remove common prefixes/suffixes that LLM might add
        prefixes_to_remove = [
            "allergies:", "allergy:", "allergic to:", 
            "the user has:", "extracted allergies:", "mentioned:",
            "food allergies:", "allergens:", "intolerances:"
        ]
        extracted_allergies_lower = extracted_allergies.lower()
        for prefix in prefixes_to_remove:
            if extracted_allergies_lower.startswith(prefix):
                extracted_allergies = extracted_allergies[len(prefix):].strip()
        
        # Normalize: remove empty, none, no entries
        if extracted_allergies.lower() in ["none", "no", "nothing", "n/a", "na", ""]:
            extracted_allergies = ""
        
        # Merge with existing allergies
        existing_allergies_list = existing_allergies or ""
        existing_allergies_list = existing_allergies_list.strip()
        
        # Normalize existing allergies too
        if existing_allergies_list.lower() in ["none", "no", "nothing", "n/a", "na"]:
            existing_allergies_list = ""
        
        # If both are empty, return empty
        if not extracted_allergies and not existing_allergies_list:
            return ""
        
        # If only one has values, return that one
        if not extracted_allergies:
            return existing_allergies_list
        if not existing_allergies_list:
            return extracted_allergies
        
        # Merge both - combine unique allergies
        # Split by comma and clean up
        existing_list = [a.strip() for a in existing_allergies_list.split(",") if a.strip()]
        extracted_list = [a.strip() for a in extracted_allergies.split(",") if a.strip()]
        
        # Combine and deduplicate (case-insensitive)
        combined_allergies = existing_list.copy()
        for extracted in extracted_list:
            # Check if already exists (case-insensitive)
            # For allergies with qualifiers, do a more nuanced check
            already_exists = False
            for existing in combined_allergies:
                # Exact match (case-insensitive)
                if existing.lower() == extracted.lower():
                    already_exists = True
                    break
                # Check if it's the same base allergen with different qualifiers
                # e.g., "peanut allergy" vs "severe peanut allergy" - keep both for now
                # This preserves user's specific input
            
            if not already_exists:
                combined_allergies.append(extracted)
        
        # Return comma-separated string
        result = ", ".join(combined_allergies)
        logger.info("ALLERGIES DETECTED | Existing: %s | Extracted: %s | Combined: %s", existing_allergies_list, extracted_allergies, result)
        return result
        
    except Exception as e:
        logger.error("Error extracting allergies intelligently: %s", e)
        # Fallback to existing allergies only
        return existing_allergies or ""



def extract_medications_intelligently(
    current_question: str, 
    conversation_history: Optional[list], 
    existing_medications: Optional[str]
) -> str:
    """
    Intelligently detect medications from current question and conversation history.
    Merges with existing medications from state.
    Handles denials/removals when user says "I don't take that medication".
    
    IMPROVED: Now captures diverse medications including dosage, frequency modifiers,
    and a wide range of medications beyond common ones.

    STRICT GUARDRAIL: ONLY extracts if user is explicitly PROVIDING/STATING information.
    If user is asking questions or making inquiries, returns existing data unchanged.
    
    Returns: Combined medications string (comma-separated)
    """
    try:
        # Handle None conversation_history
        if conversation_history is None:
            conversation_history = []
        
        # STRICT GUARDRAIL: User must be PROVIDING information, not asking questions
        # This prevents false positives like "tell me about metformin" being interpreted as taking metformin
        if not is_user_providing_information(current_question):
            logger.info("MEDICATIONS GUARDRAIL | User is NOT providing information (asking/inquiring instead). Skipping extraction. Returning existing: %s", existing_medications or '')
            return existing_medications or ""
        
        # Check for denial patterns first (user saying they don't take a medication)
        current_lower = current_question.lower()
        denial_patterns = [
            "i don't take", "i do not take", "i don't take that", "i do not take that",
            "i don't take this", "i do not take this", "i don't take any",
            "i take no", "i don't use", "i do not use", "i'm not on", "i am not on",
            "that's not correct", "that is not correct", "incorrect", "wrong",
            "i don't have", "no i don't take", "actually i don't take",
            "remove", "not true", "that's wrong", "that is wrong"
        ]
        
        is_denial = any(pattern in current_lower for pattern in denial_patterns)
        
        # If it's a denial, try to identify which medication they're denying
        if is_denial and existing_medications:
            # Look at recent assistant messages to see what medication was mentioned
            recent_assistant_messages = []
            if conversation_history:
                for msg in reversed(conversation_history[-5:]):  # Check last 5 messages
                    if msg.get('role') == 'assistant':
                        recent_assistant_messages.append(msg.get('content', ''))
            
            # Use LLM to identify which medication is being denied
            denial_prompt = f"""The user is saying they don't take a medication that was mentioned.
Identify which specific medication(s) they are denying/removing.

EXISTING MEDICATIONS: {existing_medications}
CURRENT USER MESSAGE: {current_question}
RECENT ASSISTANT MESSAGES (for context):
{chr(10).join(recent_assistant_messages[-2:]) if recent_assistant_messages else 'None'}

Return ONLY the medication(s) they are denying (comma-separated), or "none" if you can't identify.
Examples:
- "I don't take metformin" → metformin
- "I don't take that medication" → identify from context
- "That's wrong, I don't take insulin" → insulin
- "Actually I don't take birth control" → birth control

Return only the medication name(s), nothing else:"""

            try:
                denial_response = llm.invoke(denial_prompt)
                denied_medications = denial_response.content.strip().lower()
                
                # Clean up response
                denied_medications = denied_medications.replace('"', '').replace("'", "").strip()
                if denied_medications in ["none", "no", "nothing", "n/a", "na", ""]:
                    denied_medications = ""
                
                # Remove denied medications from existing
                if denied_medications:
                    existing_list = [m.strip() for m in existing_medications.split(",") if m.strip()]
                    denied_list = [m.strip() for m in denied_medications.split(",") if m.strip()]
                    
                    # Remove denied medications (case-insensitive match)
                    remaining_medications = []
                    for medication in existing_list:
                        medication_lower = medication.lower()
                        should_remove = False
                        for denied in denied_list:
                            if denied in medication_lower or medication_lower in denied:
                                should_remove = True
                                break
                        if not should_remove:
                            remaining_medications.append(medication)
                    
                    result = ", ".join(remaining_medications) if remaining_medications else ""
                    logger.info("MEDICATIONS DENIAL | Denied: %s | Remaining: %s", denied_medications, result)
                    return result
            except Exception as e:
                logger.error("Error processing medication denial: %s", e)
                # Continue with normal extraction if denial processing fails
        
        # Normal extraction flow (not a denial)
        # Collect all text to analyze
        text_to_analyze = current_question
        
        # Include recent conversation history (last 10 messages for context)
        if conversation_history:
            recent_messages = conversation_history[-10:]
            conversation_text = "\n".join([
                f"{msg.get('role', 'unknown')}: {msg.get('content', '')}" 
                for msg in recent_messages
            ])
            text_to_analyze = f"{conversation_text}\n\nCurrent question: {current_question}"
        
        # Use LLM to extract medications intelligently
        extraction_prompt = f"""Extract ONLY the medications or drugs that the user EXPLICITLY STATES they take in the conversation below.

CRITICAL VALIDATION: The user must be STATING/DECLARING they take a medication, NOT asking about it.
- "I take metformin" → VALID (user is stating)
- "tell me about metformin" → INVALID (user is asking)
- "what is insulin" → INVALID (user is inquiring)
- "I'm on birth control" → VALID (user is stating)

CRITICAL RULE: Do NOT infer, assume, or add medications that are not directly stated by the user.
DO NOT add related medications, alternatives, or potential medications.
ONLY extract what the user directly says they take or are on.

STRICT GUIDELINES:
1. Extract ONLY what is explicitly STATED as something the user TAKES:
   - "I take metformin" → metformin ✓
   - "I'm on birth control pills" → birth control pills ✓
   - "I take insulin daily" → insulin daily ✓
   - "my medications include levothyroxine" → levothyroxine ✓
   - "tell me about metformin" → NOTHING (this is a question) ✗
   - "what is insulin" → NOTHING (this is a question) ✗

2. DO NOT extract from questions or inquiries:
   - If the text contains question words (what, how, why, tell me, explain), DO NOT extract
   - If the user is asking ABOUT a medication, they are NOT stating they take it
   - Only extract when user is DECLARING/STATING they take something

3. PRESERVE DOSAGE AND FREQUENCY as stated by the user:
   - Keep dosage: "metformin 500mg", "insulin 20 units"
   - Keep frequency: "daily", "twice a day", "once a week"
   - Keep timing if mentioned: "morning", "before meals", "at night"
   - Keep descriptors: "as needed", "prescribed"

4. Handle various phrasings of the same medication:
   - "I take metformin" → metformin
   - "I'm on metformin" → metformin
   - "I use insulin" → insulin
   - "my doctor prescribed levothyroxine" → levothyroxine

5. If user says "none", "no medications", "I don't take anything", return empty string

6. Return ONLY a comma-separated list with medications AS STATED by the user (or equivalent):
   Examples:
   - If user says "I take metformin and birth control" → "metformin, birth control"
   - If user says "I'm on insulin 20 units daily" → "insulin 20 units daily"
   - If user says "metformin 500mg twice a day" → "metformin 500mg twice a day"
   - If user says "nothing" → ""

7. DO NOT standardize, infer, or add medications. Be strict about this!

EXISTING MEDICATIONS FROM PROFILE: {existing_medications or "None"}

CONVERSATION AND CURRENT QUESTION:
{text_to_analyze}

Extract ONLY explicitly mentioned medications/supplements (preserving dosage and frequency). Return comma-separated list only, or empty string if none found:"""

        response = llm.invoke(extraction_prompt)
        extracted_medications = response.content.strip()
        
        # Clean up the response - remove quotes, extra whitespace
        extracted_medications = extracted_medications.replace('"', '').replace("'", "").strip()
        
        # If LLM returned explanatory text, try to extract just the medications
        if ":" in extracted_medications:
            parts = extracted_medications.split(":", 1)
            if len(parts) > 1:
                extracted_medications = parts[1].strip()
        
        # Remove common prefixes/suffixes that LLM might add
        prefixes_to_remove = [
            "medications:", "medication:", "drugs:", "supplements:", 
            "the user takes:", "extracted medications:", "mentioned:",
            "prescribed medications:", "current medications:", "meds:"
        ]
        extracted_medications_lower = extracted_medications.lower()
        for prefix in prefixes_to_remove:
            if extracted_medications_lower.startswith(prefix):
                extracted_medications = extracted_medications[len(prefix):].strip()
        
        # Normalize: remove empty, none, no entries
        if extracted_medications.lower() in ["none", "no", "nothing", "n/a", "na", ""]:
            extracted_medications = ""
        
        # Merge with existing medications
        existing_medications_list = existing_medications or ""
        existing_medications_list = existing_medications_list.strip()
        
        # Normalize existing medications too
        if existing_medications_list.lower() in ["none", "no", "nothing", "n/a", "na"]:
            existing_medications_list = ""
        
        # If both are empty, return empty
        if not extracted_medications and not existing_medications_list:
            return ""
        
        # If only one has values, return that one
        if not extracted_medications:
            return existing_medications_list
        if not existing_medications_list:
            return extracted_medications
        
        # Merge both - combine unique medications
        # Split by comma and clean up
        existing_list = [m.strip() for m in existing_medications_list.split(",") if m.strip()]
        extracted_list = [m.strip() for m in extracted_medications.split(",") if m.strip()]
        
        # Combine and deduplicate (case-insensitive)
        combined_medications = existing_list.copy()
        for extracted in extracted_list:
            # Check if already exists (case-insensitive)
            # For medications with dosage/frequency, do a more nuanced check
            already_exists = False
            for existing in combined_medications:
                # Exact match (case-insensitive)
                if existing.lower() == extracted.lower():
                    already_exists = True
                    break
                # Check if it's the same base medication with different dosage/frequency
                # e.g., "metformin" vs "metformin 500mg" - keep both for now
                # This preserves user's specific input
        
            if not already_exists:
                combined_medications.append(extracted)
        
        # Return comma-separated string
        result = ", ".join(combined_medications)
        logger.info("MEDICATIONS DETECTED | Existing: %s | Extracted: %s | Combined: %s", existing_medications_list, extracted_medications, result)
        return result
        
    except Exception as e:
        logger.error("Error extracting medications intelligently: %s", e)
        # Fallback to existing medications only
        return existing_medications or ""



def extract_supplements_intelligently(
    current_question: str,
    conversation_history: Optional[list],
    existing_supplements: Optional[str]
) -> str:
    """
    Intelligently detect supplements from current question and conversation history.
    Merges with existing supplements from state.
    Handles denials/removals when user says "I don't take that supplement".

    STRICT GUARDRAIL: ONLY extracts if user is explicitly PROVIDING/STATING information.
    If user is asking questions or making inquiries, returns existing data unchanged.

    Returns: Combined supplements string (comma-separated)
    """
    try:
        # Handle None conversation_history
        if conversation_history is None:
            conversation_history = []
        
        # STRICT GUARDRAIL: User must be PROVIDING information, not asking questions
        # This prevents false positives like "tell me more about ams" being interpreted as taking AMS
        if not is_user_providing_information(current_question):
            logger.info("SUPPLEMENTS GUARDRAIL | User is NOT providing information (asking/inquiring instead). Skipping extraction. Returning existing: %s", existing_supplements or '')
            return existing_supplements or ""

        # Check for denial patterns first (user saying they don't take a supplement)
        current_lower = current_question.lower()
        denial_patterns = [
            "i don't take", "i do not take", "i don't take that", "i do not take that",
            "i don't take this", "i do not take this", "i don't take any",
            "i take no", "i don't use", "i do not use", "i'm not on", "i am not on",
            "that's not correct", "that is not correct", "incorrect", "wrong",
            "i don't have", "no i don't take", "actually i don't take",
            "remove", "not true", "that's wrong", "that is wrong"
        ]

        is_denial = any(pattern in current_lower for pattern in denial_patterns)

        # If it's a denial, try to identify which supplement they're denying
        if is_denial and existing_supplements:
            # Look at recent assistant messages to see what supplement was mentioned
            recent_assistant_messages = []
            if conversation_history:
                for msg in reversed(conversation_history[-5:]):  # Check last 5 messages
                    if msg.get('role') == 'assistant':
                        recent_assistant_messages.append(msg.get('content', ''))

            # Use LLM to identify which supplement is being denied
            denial_prompt = f"""The user is saying they don't take a supplement that was mentioned.
Identify which specific supplement(s) they are denying/removing.

EXISTING SUPPLEMENTS: {existing_supplements}
CURRENT USER MESSAGE: {current_question}
RECENT ASSISTANT MESSAGES (for context):
{chr(10).join(recent_assistant_messages[-2:]) if recent_assistant_messages else 'None'}

Return ONLY the supplement(s) they are denying (comma-separated), or "none" if you can't identify.
Examples:
- "I don't take vitamin D" → vitamin D
- "I don't take that supplement" → identify from context
- "That's wrong, I don't take omega-3" → omega-3
- "Actually I don't take probiotics" → probiotics

Return only the supplement name(s), nothing else:"""

            try:
                denial_response = llm.invoke(denial_prompt)
                denied_supplements = denial_response.content.strip().lower()

                # Clean up response
                denied_supplements = denied_supplements.replace('"', '').replace("'", "").strip()
                if denied_supplements in ["none", "no", "nothing", "n/a", "na", ""]:
                    denied_supplements = ""

                # Remove denied supplements from existing
                if denied_supplements:
                    existing_list = [s.strip() for s in existing_supplements.split(",") if s.strip()]
                    denied_list = [s.strip() for s in denied_supplements.split(",") if s.strip()]

                    # Remove denied supplements (case-insensitive match)
                    remaining_supplements = []
                    for supplement in existing_list:
                        supplement_lower = supplement.lower()
                        should_remove = False
                        for denied in denied_list:
                            if denied in supplement_lower or supplement_lower in denied:
                                should_remove = True
                                break
                        if not should_remove:
                            remaining_supplements.append(supplement)

                    result = ", ".join(remaining_supplements) if remaining_supplements else ""
                    logger.info("SUPPLEMENTS DENIAL | Denied: %s | Remaining: %s", denied_supplements, result)
                    return result
            except Exception as e:
                logger.error("Error processing supplement denial: %s", e)
                # Continue with normal extraction if denial processing fails

        # Normal extraction flow (not a denial)
        # Collect all text to analyze
        text_to_analyze = current_question

        # Include recent conversation history (last 10 messages for context)
        if conversation_history:
            recent_messages = conversation_history[-10:]
            conversation_text = "\n".join([
                f"{msg.get('role', 'unknown')}: {msg.get('content', '')}"
                for msg in recent_messages
            ])
            text_to_analyze = f"{conversation_text}\n\nCurrent question: {current_question}"

        # Use LLM to extract supplements intelligently
        extraction_prompt = f"""Extract ONLY the supplements or vitamins that the user EXPLICITLY STATES they take in the conversation below.

CRITICAL VALIDATION: The user must be STATING/DECLARING they take a supplement, NOT asking about it.
- "I take vitamin D" → VALID (user is stating)
- "tell me more about AMS" → INVALID (user is asking)
- "what is omega-3" → INVALID (user is inquiring)
- "I'm on probiotics" → VALID (user is stating)

CRITICAL RULE: Do NOT infer, assume, or add supplements that are not directly stated by the user.
DO NOT add related supplements or alternatives.
ONLY extract what the user directly says they take.

STRICT GUIDELINES:
1. Extract ONLY what is explicitly STATED as something the user TAKES:
   - "I take vitamin D" → vitamin D ✓
   - "I use omega-3 supplements" → omega-3 ✓
   - "I'm on probiotics" → probiotics ✓
   - "my supplements include magnesium" → magnesium ✓
   - "tell me more about AMS" → NOTHING (this is a question) ✗
   - "what is vitamin D" → NOTHING (this is a question) ✗
   - "tell me about probiotics" → NOTHING (this is a question) ✗

2. DO NOT extract from questions or inquiries:
   - If the text contains question words (what, how, why, tell me, explain, more about), DO NOT extract
   - If the user is asking ABOUT a supplement, they are NOT stating they take it
   - Only extract when user is DECLARING/STATING they take something
   - "tell me more about X" is ALWAYS a question, NEVER extract from it

3. PRESERVE DOSAGE AND FREQUENCY as stated by the user:
   - Keep dosage: "vitamin D 2000 IU", "omega-3 1000mg"
   - Keep frequency: "daily", "twice a day", "once a week"
   - Keep timing if mentioned: "morning", "before meals", "at night"

4. Handle various phrasings of the same supplement:
   - "I take vitamin D" → vitamin D
   - "I'm on probiotics" → probiotics
   - "I use fish oil" → fish oil
   - "my doctor recommended magnesium" → magnesium

5. If user says "none", "no supplements", "I don't take anything", return empty string

6. Return ONLY a comma-separated list with supplements AS STATED by the user:
   Examples:
   - "I take vitamin D and probiotics" → "vitamin D, probiotics"
   - "I take omega-3 1000mg daily" → "omega-3 1000mg daily"
   - "tell me more about AMS" → "" (EMPTY - this is a question)
   - "what is probiotics" → "" (EMPTY - this is a question)
   - "nothing" → ""

7. DO NOT standardize, infer, or add supplements. Be strict about this!

EXISTING SUPPLEMENTS FROM PROFILE: {existing_supplements or "None"}

CONVERSATION AND CURRENT QUESTION:
{text_to_analyze}

Extract ONLY explicitly mentioned supplements (preserving dosage and frequency). Return comma-separated list only, or empty string if none found:"""

        response = llm.invoke(extraction_prompt)
        extracted_supplements = response.content.strip()

        # Clean up the response - remove quotes, extra whitespace
        extracted_supplements = extracted_supplements.replace('"', '').replace("'", "").strip()

        # If LLM returned explanatory text, try to extract just the supplements
        if ":" in extracted_supplements:
            parts = extracted_supplements.split(":", 1)
            if len(parts) > 1:
                extracted_supplements = parts[1].strip()

        # Remove common prefixes/suffixes that LLM might add
        prefixes_to_remove = [
            "supplements:", "supplement:", "vitamins:", "vitamin:",
            "the user takes:", "extracted supplements:", "mentioned:",
            "current supplements:", "taken supplements:"
        ]
        extracted_supplements_lower = extracted_supplements.lower()
        for prefix in prefixes_to_remove:
            if extracted_supplements_lower.startswith(prefix):
                extracted_supplements = extracted_supplements[len(prefix):].strip()

        # Normalize: remove empty, none, no entries
        if extracted_supplements.lower() in ["none", "no", "nothing", "n/a", "na", ""]:
            extracted_supplements = ""

        # Merge with existing supplements
        existing_supplements_list = existing_supplements or ""
        existing_supplements_list = existing_supplements_list.strip()

        # Normalize existing supplements too
        if existing_supplements_list.lower() in ["none", "no", "nothing", "n/a", "na"]:
            existing_supplements_list = ""

        # If both are empty, return empty
        if not extracted_supplements and not existing_supplements_list:
            return ""

        # If only one has values, return that one
        if not extracted_supplements:
            return existing_supplements_list
        if not existing_supplements_list:
            return extracted_supplements

        # Merge both - combine unique supplements
        existing_list = [s.strip() for s in existing_supplements_list.split(",") if s.strip()]
        extracted_list = [s.strip() for s in extracted_supplements.split(",") if s.strip()]

        # Combine and deduplicate (case-insensitive)
        combined_supplements = existing_list.copy()
        for extracted in extracted_list:
            # Check if already exists (case-insensitive)
            already_exists = False
            for existing in combined_supplements:
                if existing.lower() == extracted.lower():
                    already_exists = True
                    break

            if not already_exists:
                combined_supplements.append(extracted)

        # Return comma-separated string
        result = ", ".join(combined_supplements)
        logger.info("SUPPLEMENTS DETECTED | Existing: %s | Extracted: %s | Combined: %s", existing_supplements_list, extracted_supplements, result)
        return result

    except Exception as e:
        logger.error("Error extracting supplements intelligently: %s", e)
        # Fallback to existing supplements only
        return existing_supplements or ""



def extract_gut_health_intelligently(
    current_question: str,
    conversation_history: Optional[list],
    existing_gut_health: Optional[str]
) -> str:
    """
    Intelligently detect gut health information from current question and conversation history.
    Merges with existing gut health information from state.
    Handles denials/removals when user says "That's not correct".

    STRICT GUARDRAIL: ONLY extracts if user is explicitly PROVIDING/STATING information.
    If user is asking questions or making inquiries, returns existing data unchanged.

    Returns: Combined gut health information string
    """
    try:
        # Handle None conversation_history
        if conversation_history is None:
            conversation_history = []
        
        # STRICT GUARDRAIL: User must be PROVIDING information, not asking questions
        # This prevents false positives like "tell me about bloating" being interpreted as having bloating
        if not is_user_providing_information(current_question):
            logger.info("GUT HEALTH GUARDRAIL | User is NOT providing information (asking/inquiring instead). Skipping extraction. Returning existing: %s", existing_gut_health or '')
            return existing_gut_health or ""

        # Check for denial patterns first
        current_lower = current_question.lower()
        denial_patterns = [
            "that's not correct", "that is not correct", "incorrect", "wrong",
            "i don't have", "i do not have", "i have no", "no i don't",
            "actually", "remove", "not true", "that's wrong", "that is wrong"
        ]

        is_denial = any(pattern in current_lower for pattern in denial_patterns)

        # If it's a denial, try to identify what they're denying
        if is_denial and existing_gut_health:
            # Look at recent assistant messages to see what was mentioned
            recent_assistant_messages = []
            if conversation_history:
                for msg in reversed(conversation_history[-5:]):  # Check last 5 messages
                    if msg.get('role') == 'assistant':
                        recent_assistant_messages.append(msg.get('content', ''))

            # Use LLM to identify what's being denied
            denial_prompt = f"""The user is saying information about gut health is not correct.
Identify which specific gut health issue(s) or information they are denying/removing.

EXISTING GUT HEALTH INFO: {existing_gut_health}
CURRENT USER MESSAGE: {current_question}
RECENT ASSISTANT MESSAGES (for context):
{chr(10).join(recent_assistant_messages[-2:]) if recent_assistant_messages else 'None'}

Return ONLY the gut health issue(s) they are denying (comma-separated), or "none" if you can't identify.
Examples:
- "That's wrong, I don't have IBS" → IBS
- "I don't have leaky gut" → leaky gut
- "Actually I don't have constipation issues" → constipation

Return only the condition name(s), nothing else:"""

            try:
                denial_response = llm.invoke(denial_prompt)
                denied_gut_health = denial_response.content.strip().lower()

                # Clean up response
                denied_gut_health = denied_gut_health.replace('"', '').replace("'", "").strip()
                if denied_gut_health in ["none", "no", "nothing", "n/a", "na", ""]:
                    denied_gut_health = ""

                # Remove denied items from existing
                if denied_gut_health:
                    existing_list = [g.strip() for g in existing_gut_health.split(",") if g.strip()]
                    denied_list = [g.strip() for g in denied_gut_health.split(",") if g.strip()]

                    # Remove denied items (case-insensitive match)
                    remaining_gut_health = []
                    for item in existing_list:
                        item_lower = item.lower()
                        should_remove = False
                        for denied in denied_list:
                            if denied in item_lower or item_lower in denied:
                                should_remove = True
                                break
                        if not should_remove:
                            remaining_gut_health.append(item)

                    result = ", ".join(remaining_gut_health) if remaining_gut_health else ""
                    logger.info("GUT HEALTH DENIAL | Denied: %s | Remaining: %s", denied_gut_health, result)
                    return result
            except Exception as e:
                logger.error("Error processing gut health denial: %s", e)
                # Continue with normal extraction if denial processing fails

        # Normal extraction flow (not a denial)
        # Collect all text to analyze
        text_to_analyze = current_question

        # Include recent conversation history (last 10 messages for context)
        if conversation_history:
            recent_messages = conversation_history[-10:]
            conversation_text = "\n".join([
                f"{msg.get('role', 'unknown')}: {msg.get('content', '')}"
                for msg in recent_messages
            ])
            text_to_analyze = f"{conversation_text}\n\nCurrent question: {current_question}"

        # Use LLM to extract gut health information intelligently
        extraction_prompt = f"""Extract ONLY the gut health issues, digestive conditions, or microbiome-related information that the user EXPLICITLY STATES they have in the conversation below.

CRITICAL VALIDATION: The user must be STATING/DECLARING they have a gut health issue, NOT asking about it.
- "I have IBS" → VALID (user is stating)
- "tell me about bloating" → INVALID (user is asking)
- "what is digestion" → INVALID (user is inquiring)
- "I suffer from constipation" → VALID (user is stating)

CRITICAL RULE: Do NOT infer, assume, or add gut health issues that are not directly stated by the user.
DO NOT add related conditions or potential issues.
ONLY extract what the user directly says they have or experience.

STRICT GUIDELINES:
1. Extract ONLY what is explicitly STATED as something the user HAS/EXPERIENCES:
   - "I have IBS" → IBS ✓
   - "I suffer from bloating" → bloating ✓
   - "I have leaky gut" → leaky gut ✓
   - "My digestion is poor" → poor digestion ✓
   - "tell me about bloating" → NOTHING (this is a question) ✗
   - "what is digestion" → NOTHING (this is a question) ✗
   - "tell me more about IBS" → NOTHING (this is a question) ✗

2. DO NOT extract from questions or inquiries:
   - If the text contains question words (what, how, why, tell me, explain, more about), DO NOT extract
   - If the user is asking ABOUT a gut health issue, they are NOT stating they have it
   - Only extract when user is DECLARING/STATING they have/experience something
   - "tell me more about X" is ALWAYS a question, NEVER extract from it

3. PRESERVE DESCRIPTORS AND SEVERITY as stated by the user:
   - Keep severity: "severe IBS", "mild bloating"
   - Keep frequency: "occasional constipation", "chronic diarrhea"
   - Keep descriptors: "food-related", "stress-related"

4. Handle various phrasings of the same condition:
   - "I have IBS" → IBS
   - "I suffer from bloating" → bloating
   - "My digestion is poor" → poor digestion
   - "I experience food sensitivities" → food sensitivities

5. If user says "none", "no issues", "I don't have any", return empty string

6. Return ONLY a comma-separated list with gut health info AS STATED by the user:
   Examples:
   - If user says "I have IBS and bloating" → "IBS, bloating"
   - If user says "I suffer from chronic constipation" → "chronic constipation"
   - If user says "nothing" → ""

7. DO NOT standardize, infer, or add conditions. Be strict about this!

EXISTING GUT HEALTH INFO FROM PROFILE: {existing_gut_health or "None"}

CONVERSATION AND CURRENT QUESTION:
{text_to_analyze}

Extract ONLY explicitly mentioned gut health issues/conditions (preserving severity and descriptors). Return comma-separated list only, or empty string if none found:"""

        response = llm.invoke(extraction_prompt)
        extracted_gut_health = response.content.strip()

        # Clean up the response - remove quotes, extra whitespace
        extracted_gut_health = extracted_gut_health.replace('"', '').replace("'", "").strip()

        # If LLM returned explanatory text, try to extract just the gut health info
        if ":" in extracted_gut_health:
            parts = extracted_gut_health.split(":", 1)
            if len(parts) > 1:
                extracted_gut_health = parts[1].strip()

        # Remove common prefixes/suffixes that LLM might add
        prefixes_to_remove = [
            "gut health issues:", "gut health:", "digestive issues:", "conditions:",
            "the user has:", "extracted gut health:", "mentioned:",
            "digestive conditions:", "microbiome issues:"
        ]
        extracted_gut_health_lower = extracted_gut_health.lower()
        for prefix in prefixes_to_remove:
            if extracted_gut_health_lower.startswith(prefix):
                extracted_gut_health = extracted_gut_health[len(prefix):].strip()

        # Normalize: remove empty, none, no entries
        if extracted_gut_health.lower() in ["none", "no", "nothing", "n/a", "na", ""]:
            extracted_gut_health = ""

        # Merge with existing gut health info
        existing_gut_health_list = existing_gut_health or ""
        existing_gut_health_list = existing_gut_health_list.strip()

        # Normalize existing gut health info too
        if existing_gut_health_list.lower() in ["none", "no", "nothing", "n/a", "na"]:
            existing_gut_health_list = ""

        # If both are empty, return empty
        if not extracted_gut_health and not existing_gut_health_list:
            return ""

        # If only one has values, return that one
        if not extracted_gut_health:
            return existing_gut_health_list
        if not existing_gut_health_list:
            return extracted_gut_health

        # Merge both - combine unique items
        existing_list = [g.strip() for g in existing_gut_health_list.split(",") if g.strip()]
        extracted_list = [g.strip() for g in extracted_gut_health.split(",") if g.strip()]

        # Combine and deduplicate (case-insensitive)
        combined_gut_health = existing_list.copy()
        for extracted in extracted_list:
            # Check if already exists (case-insensitive)
            already_exists = False
            for existing in combined_gut_health:
                if existing.lower() == extracted.lower():
                    already_exists = True
                    break

            if not already_exists:
                combined_gut_health.append(extracted)

        # Return comma-separated string
        result = ", ".join(combined_gut_health)
        logger.info("GUT HEALTH DETECTED | Existing: %s | Extracted: %s | Combined: %s", existing_gut_health_list, extracted_gut_health, result)
        return result

    except Exception as e:
        logger.error("Error extracting gut health intelligently: %s", e)
        # Fallback to existing gut health info only
        return existing_gut_health or ""
        

def is_meal_edit_request(user_msg: str) -> bool:
    """
    Detect if user wants to edit their meal plan.
    Returns True if meal edit intent is detected.
    """
    if not user_msg:
        return False
    user_msg_lower = user_msg.lower()
    # IMPORTANT: Exclude exercise-related requests first
    exercise_exclusion_keywords = [
        "exercise", "workout", "training", "fitness", "gym", "physical activity"
    ]
    if any(keyword in user_msg_lower for keyword in exercise_exclusion_keywords):
        return False  # This is an exercise edit, not meal edit
    # Meal-related keywords
    meal_keywords = [
        # Core meal terms
        "meal", "diet", "food", "breakfast", "lunch", "dinner", "snack", "brunch",
        "eating", "nutrition", "meal plan", "diet plan", "menu", "recipe",
        # Food-related actions
        "cook", "prepare", "eat", "consume", "feed", "nourish",
        # Diet types and approaches
        "keto", "vegan", "vegetarian", "paleo", "mediterranean", "carnivore",
        "intermittent fasting", "calorie", "macro", "protein", "carb",
        # Meal-related nouns
        "dish", "cuisine", "supper", "appetizer", "entree", "dessert",
        "portion", "serving", "ration", "fare", "feast",
        # Health/nutrition terms
        "nutrition plan", "eating plan", "dietary", "nourishment", "sustenance",
        "meal prep", "food plan", "daily meals", "weekly meals"
    ]
    # Edit-related keywords
    edit_keywords = [
        # Direct edit terms
        "edit", "change", "modify", "update", "revise", "adjust",
        "alter", "replace", "swap", "switch", "redo", "regenerate",
        # Transformation verbs
        "customize", "personalize", "adapt", "tailor", "tweak", "refine",
        "improve", "enhance", "transform", "redesign", "rework", "rewrite",
        # Removal/addition terms
        "remove", "delete", "add", "include", "exclude", "substitute",
        "swap out", "take out", "put in", "exchange", "trade",
        # Preference expressions
        "different", "another", "new", "fresh", "alternative", "varied"
    ]
    # Check for combinations of meal + edit keywords
    has_meal_keyword = any(keyword in user_msg_lower for keyword in meal_keywords)
    has_edit_keyword = any(keyword in user_msg_lower for keyword in edit_keywords)
    # Common phrases that indicate meal edit intent
    meal_edit_phrases = [
        # Direct edit requests
        "edit my meal", "change my meal", "modify my meal",
        "edit meal plan", "change meal plan", "modify meal plan",
        "edit my diet", "change my diet", "modify my diet",
        "edit the meal", "change the meal", "modify the meal",
        # Want/need expressions
        "want to edit", "want to change", "want to modify",
        "need to edit", "need to change", "need to modify",
        "would like to edit", "would like to change", "would like to modify",
        "wish to edit", "wish to change", "wish to modify",
        # Permission/ability questions
        "can i edit", "can i change", "can i modify",
        "could i edit", "could i change", "could i modify",
        "may i edit", "may i change", "may i modify",
        "how do i edit", "how to edit", "how can i change",
        # Combined phrases
        "i want to edit my meal", "i want to change my diet", "i want to modify my diet",
        "i want to edit my diet", "i want to change my meal", "i want to modify my meal",
        "i want to edit my meal plan", "i want to change my diet plan", "i want to modify my diet plan",
        "i want to edit my diet plan", "i want to change my meal plan", "i want to modify my meal plan",
        # Creation requests
        "make my meal plan", "create my meal plan", "generate my meal plan",
        "build my meal plan", "design my meal plan", "set up my meal plan",
        "make me a meal plan", "create me a meal plan", "give me a meal plan",
        "make a meal plan", "create a meal plan", "plan my meals",
        # Adjustment phrases
        "adjust my meal", "customize my meal", "personalize my diet",
        "tailor my meal plan", "adapt my diet", "refine my meals",
        "update my nutrition", "revise my eating plan", "redo my meal plan",
        # Substitution phrases
        "replace my meal", "swap my meal", "substitute my meal",
        "switch my diet", "exchange my meals", "different meal plan",
        "another meal plan", "new meal plan", "alternative diet"
    ]
    has_meal_edit_phrase = any(phrase in user_msg_lower for phrase in meal_edit_phrases)
    return has_meal_edit_phrase or (has_meal_keyword and has_edit_keyword)

def is_exercise_edit_request(user_msg: str) -> bool:
    """
    Detect if user wants to edit their exercise plan.
    Returns True if exercise edit intent is detected.
    """
    if not user_msg:
        return False
    user_msg_lower = user_msg.lower()
    # Exercise-related keywords
    exercise_keywords = [
        # Core exercise terms
        "exercise", "workout", "training", "fitness", "gym", "physical activity",
        "cardio", "strength", "yoga", "pilates", "running", "jogging",
        "cycling", "swimming", "walking", "hiking", "sports",
        # Exercise-related nouns
        "routine", "regimen", "program", "session", "rep", "set",
        "circuit", "interval", "hiit", "crossfit", "bodyweight",
        # Fitness goals
        "muscle", "endurance", "stamina", "flexibility", "mobility",
        "conditioning", "athletic", "performance"
    ]
    # Edit-related keywords
    edit_keywords = [
        "edit", "change", "modify", "update", "revise", "adjust",
        "alter", "replace", "swap", "switch", "redo", "regenerate",
        "customize", "personalize", "adapt", "tailor", "tweak", "refine",
        "improve", "enhance", "transform", "redesign", "rework", "rewrite",
        "remove", "delete", "add", "include", "exclude", "substitute",
        "different", "another", "new", "fresh", "alternative", "varied"
    ]
    # Check for combinations of exercise + edit keywords
    has_exercise_keyword = any(keyword in user_msg_lower for keyword in exercise_keywords)
    has_edit_keyword = any(keyword in user_msg_lower for keyword in edit_keywords)
    # Common phrases that indicate exercise edit intent
    exercise_edit_phrases = [
        # Direct edit requests
        "edit my exercise", "change my exercise", "modify my exercise",
        "edit exercise plan", "change exercise plan", "modify exercise plan",
        "edit my workout", "change my workout", "modify my workout",
        "edit workout plan", "change workout plan", "modify workout plan",
        "edit the exercise", "change the exercise", "modify the exercise",
        "edit my training", "change my training", "modify my training",
        "edit my fitness", "change my fitness", "modify my fitness",
        # Want/need expressions
        "want to edit", "want to change", "want to modify",
        "need to edit", "need to change", "need to modify",
        "would like to edit", "would like to change", "would like to modify",
        "wish to edit", "wish to change", "wish to modify",
        # Permission/ability questions
        "can i edit", "can i change", "can i modify",
        "could i edit", "could i change", "could i modify",
        "may i edit", "may i change", "may i modify",
        "how do i edit", "how to edit", "how can i change",
        # Combined phrases
        "i want to edit my exercise", "i want to change my workout", "i want to modify my workout",
        "i want to edit my workout", "i want to change my exercise", "i want to modify my exercise",
        "i want to edit my fitness", "i want to change my training", "i want to modify my training",
        "i want to edit my training", "i want to change my fitness", "i want to modify my fitness",
        "i want to edit my exercise plan", "i want to change my workout plan", "i want to modify my workout plan",
        "i want to edit my workout plan", "i want to change my exercise plan", "i want to modify my exercise plan",
        "i want to edit my fitness plan", "i want to change my training plan", "i want to modify my training plan",
        "i want to edit my training plan", "i want to change my fitness plan", "i want to modify my fitness plan",
        # Creation requests
        "make my workout plan", "create my workout plan", "generate my workout plan",
        "make my exercise plan", "create my exercise plan", "generate my exercise plan",
        "make my training plan", "create my training plan", "generate my training plan",
        "make my fitness plan", "create my fitness plan", "generate my fitness plan",
        "build my workout", "design my workout", "set up my exercise routine",
        "make me a workout", "create me an exercise plan", "give me a training plan",
        "plan my workouts", "plan my exercises", "schedule my training",
        # Adjustment phrases
        "adjust my workout", "customize my exercise", "personalize my training",
        "tailor my workout plan", "adapt my fitness", "refine my exercises",
        "update my training", "revise my workout", "redo my exercise plan",
        "tweak my routine", "improve my workout", "enhance my training",
        # Substitution phrases
        "replace my workout", "swap my exercise", "substitute my training",
        "switch my workout", "exchange my exercises", "different workout plan",
        "another workout plan", "new exercise plan", "alternative training",
        "varied workout", "fresh routine", "different exercises"
    ]
    has_exercise_edit_phrase = any(phrase in user_msg_lower for phrase in exercise_edit_phrases)
    return has_exercise_edit_phrase or (has_exercise_keyword and has_edit_keyword)

def handle_meal_day_selection_for_edit(state: State) -> State:
    """Handle day selection for meal plan editing from post-plan Q&A."""
    from app.services.whatsapp.client import send_whatsapp_message
    import re
    
    user_msg = state.get("user_msg", "").strip()
    
    # Try to extract day number from ID first (if present in message)
    match = re.search(r'edit_meal_day(\d)', user_msg.lower())
    if match:
        day_num = int(match.group(1))
    else:
        # Fallback to extracting from text (e.g. "Day 3")
        day_num = extract_day_number(user_msg)
        
    if day_num:
        state["edit_day_number"] = day_num
        
        send_whatsapp_message(
            state["user_id"],
            f"Got it! 📝 What changes would you like to make to your Day {day_num} meal plan?\n\n"
            f"For example:\n"
            f"- \"Add more protein\"\n"
            f"- \"Make it vegetarian\"\n"
            f"- \"Replace rice with quinoa\"\n"
            f"- \"Reduce calories\""
        )
        
        state[f"meal_day{day_num}_change_request"] = ""
        state["last_question"] = f"awaiting_meal_day{day_num}_edit_changes"
        state["pending_node"] = "collect_meal_day_edit_changes"
    else:
        send_whatsapp_message(
            state["user_id"],
            "I didn't catch which day you want to edit. Please select a day from the list."
        )
        state["last_question"] = "select_meal_day_to_edit"
    
    return state



def handle_exercise_day_selection_for_edit(state: State) -> State:
    """Handle day selection for exercise plan editing from post-plan Q&A."""
    from app.services.whatsapp.client import send_whatsapp_message
    import re
    
    user_msg = state.get("user_msg", "").strip()
    
    # Try to extract day number from ID first (if present in message)
    match = re.search(r'edit_exercise_day(\d)', user_msg.lower())
    if match:
        day_num = int(match.group(1))
    else:
        # Fallback to extracting from text (e.g. "Day 3")
        day_num = extract_day_number(user_msg)
        
    if day_num:
        state["edit_day_number"] = day_num
        
        send_whatsapp_message(
            state["user_id"],
            f"Got it! 💪 What changes would you like to make to your Day {day_num} exercise plan?\n\n"
            f"For example:\n"
            f"- \"Make it easier\"\n"
            f"- \"Add more cardio\"\n"
            f"- \"Replace running with cycling\"\n"
            f"- \"Shorter workout duration\""
        )
        
        state[f"day{day_num}_change_request"] = ""  # Note: exercise uses dayX_change_request
        state["last_question"] = f"awaiting_exercise_day{day_num}_edit_changes"
        state["pending_node"] = "collect_exercise_day_edit_changes"
    else:
        send_whatsapp_message(
            state["user_id"],
            "I didn't catch which day you want to edit. Please select a day from the list."
        )
        state["last_question"] = "select_exercise_day_to_edit"
    
    return state



def collect_meal_day_edit_changes(state: State) -> State:
    """Collect user's requested changes for any meal plan day and regenerate."""
    from app.services.whatsapp.client import send_whatsapp_message
    from app.services.prompts.general.meal_plan_template import build_meal_plan_prompt, build_disclaimers, _remove_llm_disclaimers
    from app.services.whatsapp.messages import remove_markdown
    from app.services.llm.bedrock_llm import ChatBedRockLLM
    llm = ChatBedRockLLM()
    import re
    
    user_msg = state.get("user_msg", "").strip()
    day_num = state.get("edit_day_number")
    
    # Fallback: Extract day number from last_question if not in state
    # last_question format: "awaiting_meal_day3_edit_changes"
    if not day_num:
        last_q = state.get("last_question", "")
        match = re.search(r'awaiting_meal_day(\d)_edit_changes', last_q)
        if match:
            day_num = int(match.group(1))
            state["edit_day_number"] = day_num  # Store for consistency
    
    if not user_msg or not day_num:
        send_whatsapp_message(
            state["user_id"],
            f"Please tell me what changes you'd like to make to your Day {day_num if day_num else ''} meal plan."
        )
        return state
    
    # Filter out acknowledgments
    acknowledgments = ["ok", "okay", "yes", "yeah", "sure", "fine", "good", "alright", "k", "kk", "👍", "✓", "✔️"]
    if user_msg.lower() in acknowledgments:
        return state
    
    # Store the change request
    state[f"meal_day{day_num}_change_request"] = user_msg
    
    # Get the existing plan
    old_plan = state.get(f"meal_day{day_num}_plan", "")
    
    # Store old plan for reference (History Tracking)
    history_key = f"old_meal_day{day_num}_plans"
    if not state.get(history_key):
        state[history_key] = []
    state[history_key].append(old_plan)
    
    # Acknowledge and start regenerating
    send_whatsapp_message(
        state["user_id"],
        f"Got it! 🔄 Regenerating your Day {day_num} meal plan with: {user_msg}\n\n⏳ One moment..."
    )
    
    # Build revision prompt
    prompt = build_meal_plan_prompt(
        state=state,
        day_number=day_num,
        previous_meals=None,
        day1_plan=None,
        change_request=user_msg,
        is_revision=True
    )
    
    revision_context = f"""
═══════════════════════════════════════════════════════════════
🔄 REVISION MODE - DAY {day_num} REGENERATION
═══════════════════════════════════════════════════════════════

ORIGINAL DAY {day_num} PLAN THAT USER WANTS TO CHANGE:
{old_plan}

USER'S REQUESTED CHANGES:
{user_msg}

REVISION INSTRUCTIONS:
1. Incorporate the user's requested changes
2. Maintain the EXACT format from the template
3. Keep the same level of detail as the original plan
4. Ensure all required sections are present (snacks, gut health, etc.)
5. Keep the warm, supportive tone

"""
    
    full_prompt = revision_context + prompt
    
    # Generate revised plan
    response = llm.invoke(full_prompt)
    revised_plan = response.content.strip()
    
    # Clean up
    revised_plan = _remove_llm_disclaimers(revised_plan)
    disclaimers = build_disclaimers(state)
    if disclaimers:
        revised_plan = revised_plan.rstrip() + disclaimers
    revised_plan = remove_markdown(revised_plan)
    
    # Update state
    state[f"meal_day{day_num}_plan"] = revised_plan
    
    # Save to dedicated collection with old plans, change request, and user context
    from app.services.crm.sessions import save_meal_plan, extract_ams_meal_user_context
    meal_plan_data = {
        f"meal_day{day_num}_plan": revised_plan,
        f"old_meal_day{day_num}_plans": state.get(f"old_meal_day{day_num}_plans", []),
        f"meal_day{day_num}_change_request": user_msg,
        "user_context": extract_ams_meal_user_context(state)
    }
    save_meal_plan(state["user_id"], meal_plan_data)
    
    # Send to user
    send_whatsapp_message(state["user_id"], revised_plan)
    send_whatsapp_message(
        state["user_id"],
        f"✅ Your Day {day_num} meal plan has been updated! You can continue asking questions or request more changes anytime. 💚"
    )
    
    # Return to post-plan Q&A
    state["last_question"] = "post_plan_qna"
    state["current_agent"] = "post_plan_qna"
    state["pending_node"] = None
    state["edit_mode"] = None
    state["edit_day_number"] = None
    
    return state



def collect_exercise_day_edit_changes(state: State) -> State:
    """Collect user's requested changes for any exercise plan day and regenerate."""
    from app.services.whatsapp.client import send_whatsapp_message
    from app.services.whatsapp.messages import remove_markdown
    from app.services.llm.bedrock_llm import ChatBedRockLLM
    llm = ChatBedRockLLM()
    import re
    
    user_msg = state.get("user_msg", "").strip()
    day_num = state.get("edit_day_number")
    
    # Fallback: Extract day number from last_question if not in state
    # last_question format: "awaiting_exercise_day3_edit_changes"
    if not day_num:
        last_q = state.get("last_question", "")
        match = re.search(r'awaiting_exercise_day(\d)_edit_changes', last_q)
        if match:
            day_num = int(match.group(1))
            state["edit_day_number"] = day_num  # Store for consistency
    
    if not user_msg or not day_num:
        send_whatsapp_message(
            state["user_id"],
            f"Please tell me what changes you'd like to make to your Day {day_num if day_num else ''} exercise plan."
        )
        return state
    
    # Filter out acknowledgments
    acknowledgments = ["ok", "okay", "yes", "yeah", "sure", "fine", "good", "alright", "k", "kk", "👍", "✓", "✔️"]
    if user_msg.lower() in acknowledgments:
        return state
    
    # Store the change request
    state[f"day{day_num}_change_request"] = user_msg
    
    # Get the existing plan
    old_plan = state.get(f"day{day_num}_plan", "")
    
    # Store old plan for reference (History Tracking)
    history_key = f"old_day{day_num}_plans"
    if not state.get(history_key):
        state[history_key] = []
    state[history_key].append(old_plan)
    
    # Acknowledge and start regenerating
    send_whatsapp_message(
        state["user_id"],
        f"Got it! 🔄 Regenerating your Day {day_num} exercise plan with: {user_msg}\n\n⏳ One moment..."
    )
    
    # Build revision prompt
    day_themes = {
        1: "Full Body Activation",
        2: "Cardio & Endurance",
        3: "Core Stability",
        4: "Mobility & Stretching",
        5: "Upper Body Strength",
        6: "Lower Body Power",
        7: "Active Recovery"
    }
    
    theme = day_themes.get(day_num, "Workout")
    
    prompt = f"""
You are a professional fitness coach. The user has requested changes to their Day {day_num} exercise plan.

ORIGINAL DAY {day_num} PLAN:
{old_plan}

USER'S REQUESTED CHANGES:
{user_msg}

USER PROFILE:
- Fitness Level: {state.get('fitness_level', 'Not specified')}
- Activity Types: {state.get('activity_types', 'Not specified')}
- Exercise Goals: {state.get('exercise_goals', 'Not specified')}
- Exercise Frequency: {state.get('exercise_frequency', 'Not specified')}
- Exercise Intensity: {state.get('exercise_intensity', 'Not specified')}
- Session Duration: {state.get('session_duration', 'Not specified')}

Create a REVISED Day {day_num} workout plan that incorporates the user's requested changes while maintaining the overall structure and effectiveness of the workout.

Format the plan as:
**Day {day_num}: {theme}** 🔥

[Revised workout details here - exercises, sets, reps, duration, etc.]

**💡 Tips:**
[Helpful tips for Day {day_num}]

Keep it concise, practical, and well-structured.
"""
    
    # Generate revised plan
    response = llm.invoke(prompt)
    revised_plan = response.content.strip()
    revised_plan = remove_markdown(revised_plan)
    
    # Update state
    state[f"day{day_num}_plan"] = revised_plan
    
    # Save to dedicated collection with old plans, change request, and user context
    from app.services.crm.sessions import save_exercise_plan, extract_exercise_plan_user_context
    exercise_plan_data = {
        f"day{day_num}_plan": revised_plan,
        f"old_day{day_num}_plans": state.get(f"old_day{day_num}_plans", []),
        f"day{day_num}_change_request": user_msg,
        "user_context": extract_exercise_plan_user_context(state)
    }
    save_exercise_plan(state["user_id"], exercise_plan_data)
    
    # Send to user
    send_whatsapp_message(state["user_id"], revised_plan)
    send_whatsapp_message(
        state["user_id"],
        f"✅ Your Day {day_num} exercise plan has been updated! You can continue asking questions or request more changes anytime. 💪"
    )
    
    # Return to post-plan Q&A
    state["last_question"] = "post_plan_qna"
    state["current_agent"] = "post_plan_qna"
    state["pending_node"] = None
    state["edit_mode"] = None
    state["edit_day_number"] = None
    
    return state


def post_plan_qna_node(state: State) -> State:
    """Node: Unified Q&A handler for both health and product questions after plan completion."""
    user_question = state.get("user_msg", "")
    conversation_history = state.get("conversation_history", [])
    
    # Skip processing if this is a system/dummy message (e.g., from SNAP flow)
    if not user_question or user_question.strip() in ["[IMAGE_RECEIVED]", ""]:
        logger.info("Skipping post_plan_qna processing for system message")
        state["last_question"] = "post_plan_qna"
        return state
    
    # Import guardrails for gut coach connection detection
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__)))
    from app.services.rag.emergency_detection import EmergencyDetector
    from app.services.rag.medical_guardrails import MedicalGuardrails
    
    # Initialize guardrails
    medical_guardrails = MedicalGuardrails()
    emergency_detector = EmergencyDetector()

    # Detect intent (and store for analytics/debugging)
    detected_intent = detect_user_intent(user_question, state)
    state["detected_intent"] = detected_intent
    
    # Build optimized context using new modular system
    user_context = build_optimized_context(
        state=state,
        user_question=user_question,
        llm_client=llm,
        intent=detected_intent,
        include_plans=True,
        max_recent_messages=6
    )
    # print(f"USER CONTEXT: {user_context}")

    # Only process if there's actually a user question
    # This prevents automatic responses when transitioning from exercise plan completion
    if not user_question or not user_question.strip():
        # Just set the state without sending any message
        state["last_question"] = "post_plan_qna"
        state["current_agent"] = "post_plan_qna"
        return state

    # CHECK FOR PLAN EDIT REQUESTS (before product/health routing)
    # This allows users to edit their meal or exercise plans from the post-plan Q&A phase
    if is_meal_edit_request(user_question):
        logger.info("MEAL EDIT REQUEST DETECTED: %s", user_question)
        day_num = extract_day_number(user_question)
        logger.info("DAY NUMBER EXTRACTED: %s", day_num)
        return handle_meal_edit_request(state, day_num)
    
    if is_exercise_edit_request(user_question):
        logger.info("EXERCISE EDIT REQUEST DETECTED: %s", user_question)
        day_num = extract_day_number(user_question)
        logger.info("DAY NUMBER EXTRACTED: %s", day_num)
        return handle_exercise_edit_request(state, day_num)

    # Determine if it's a product question
    # 1) Direct product mention short-circuit
    user_msg_lower = user_question.lower()
    direct_product_names = [
        'metabolically lean', 'metabolic fiber boost', 'ams', 'metabolically lean - probiotics',
        'advanced metabolic system', 'gut cleanse', 'gut balance', 'bye bye bloat',
        'smooth move', 'ibs rescue', 'water kefir', 'kombucha', 'fermented pickles',
        'prebiotic shots', 'sleep and calm', 'first defense', 'good to glow',
        'pcos balance', 'good down there', 'fiber boost', 'happy tummy', 'metabolic fiber',
        'happy tummies', 'glycemic control', 'gut cleanse super bundle',
        'acidity aid', 'ibs dnm', 'ibs rescue d&m', 'ibs c', 'ibs d', 'ibs m',
        'gut cleanse detox shot', 'gut cleanse shot', 'prebiotic fiber boost',
        'smooth move fiber boost', 'constipation bundle', 'pcos bundle',
        'metabolically lean supercharged', 'ferments', 'squat buddy', 'probiotics', 'prebiotics'
    ]
    # IMPROVED: Use word boundary matching to avoid false positives
    mentioned_product = next((p for p in direct_product_names if re.search(r'\b' + re.escape(p) + r'\b', user_msg_lower)), None)

    # 2) Heuristic classifier + contextual follow-up
    from app.services.prompts.general.health_product_detection import is_product_question
    is_product = bool(mentioned_product) or is_product_question(user_question)
    is_contextual_product = is_contextual_product_question(user_question, conversation_history)

    # Debug to trace routing decisions
    try:
        logger.debug("QNA ROUTING | product_mentioned=%s (%s) | is_product=%s | is_contextual_product=%s", bool(mentioned_product), mentioned_product or '-', is_product, is_contextual_product)
    except Exception:
        pass
    
    if is_product or is_contextual_product:
        # Handle product question using QnA API
        try:
            import requests
            qna_url = "http://localhost:8000/ask"  # Assuming QnA API runs on port 8000

            # IMPROVED: Use the robust is_contextual_product_question function
            # For contextual questions, provide more context to the API

            # SMART CONTEXT EXTRACTION: Get only recent messages and extract product
            recent_messages = conversation_history[-5:] if len(conversation_history) > 5 else conversation_history
            relevant_product = extract_relevant_product_from_history(recent_messages, user_question)

            # CRITICAL FIX: If user asks about THEIR OWN product/order, ignore history-based product context
            # and rely only on user_order from state.
            is_my_product_query = any(
                p in user_msg_lower
                for p in [
                    # Direct ownership
                    "my product",
                    "my products",
                    "my order",
                    "my orders",
                    "my purchase",
                    "my purchases",

                    # What did I buy / get
                    "what did i buy",
                    "what i bought",
                    "what did i purchase",
                    "what i purchased",
                    "what have i bought",
                    "what have i purchased",
                    "what did i order",
                    "what i ordered",

                    # Which product questions
                    "which product did i buy",
                    "which product i bought",
                    "which product did i order",
                    "which product i ordered",
                    "which product is mine",

                    # Possession / reference
                    "the product i bought",
                    "the product i ordered",
                    "the product i purchased",
                    "my current product",
                    "my latest product",
                    "my last order",
                    "my recent order",

                    # Informal / chat-style
                    "what product do i have",
                    "what product i have",
                    "what am i using",
                    "what am i taking",
                    "what supplement do i have",
                    "what supplement i bought",
                ]
            )

            if state.get("user_order") and is_my_product_query:
                logger.info(
                    "OVERRIDE: Detected query about user's own product. "
                    "Ignoring history context '%s' to use user_order.", relevant_product
                )
                relevant_product = None


            # if is_product or (is_contextual_product and conversation_history):
            #     # Use the improved dynamic window sizing and product detection
            #     # The is_contextual_product_question function already handles:
            #     # - Dynamic window sizing (8-16 messages based on conversation length)
            #     # - Better product mention tracking
            #     # - Enhanced follow-up pattern detection

            #     # Build context from conversation history using the same robust approach
            #     # as the improved is_contextual_product_question function
            #     conversation_length = len(conversation_history)
            #     if conversation_length <= 10:
            #         window_size = 8
            #     elif conversation_length <= 20:
            #         window_size = 12
            #     else:
            #         window_size = 16

            #     recent_messages = conversation_history[-window_size:]
            #     context_str = "\n".join([f"{msg.get('role', 'unknown')}: {msg.get('content', '')}" for msg in recent_messages])
            #     enhanced_question = f"Context: {context_str}\n\nQuestion: {user_question}"

            #     print(f"POST-PLAN CONTEXTUAL PRODUCT QUESTION: Enhancing with context (window: {window_size})")
            #     # Add user context (profile + plans) for better grounding
            #     if user_context:
            #         context_question = f"{enhanced_question}\n\nUser Context:\n{user_context}"
            #     else:
            #         context_question = enhanced_question
            # else:
            #     # Even for direct product questions, include user context if available
            #     context_question = user_question if not user_context else f"{user_question}\n\nUser Context:\n{user_context}"

            # response = requests.post(
            #     qna_url,
            #     json={"question": user_question},
            #     timeout=20
            # )

            # REFORMULATE QUESTION using GPT-3.5 Turbo
            if relevant_product and is_contextual_product:
                reformulated_question = reformulate_with_gpt(user_question, relevant_product, recent_messages)
                logger.debug("GPT REFORMULATED QUESTION: %s", reformulated_question)
                final_question = reformulated_question
            else:
                # For direct product questions or when no relevant product found, use original
                final_question = user_question

            # INTELLIGENTLY DETECT health conditions, allergies, and medications from current question and conversation history
            # This will merge existing conditions/allergies/medications with any newly mentioned ones
            # Also handles denials when user says "I don't have this condition"
            health_conditions = extract_health_conditions_intelligently(
                current_question=user_question,
                conversation_history=conversation_history,
                existing_health_conditions=state.get("health_conditions")
            )
            
            allergies = extract_allergies_intelligently(
                current_question=user_question,
                conversation_history=conversation_history,
                existing_allergies=state.get("allergies")
            )
            
            medications = extract_medications_intelligently(
                current_question=user_question,
                conversation_history=conversation_history,
                existing_medications=state.get("medications")
            )

            supplements = extract_supplements_intelligently(
                current_question=user_question,
                conversation_history=conversation_history,
                existing_supplements=state.get("supplements")
            )

            gut_health = extract_gut_health_intelligently(
                current_question=user_question,
                conversation_history=conversation_history,
                existing_gut_health=state.get("gut_health")
            )

            # Update state with newly detected/updated health conditions if they're different
            if health_conditions != state.get("health_conditions"):
                # Only update if we detected something new or removed something (avoid overwriting with empty unnecessarily)
                if health_conditions.strip() and health_conditions.strip().lower() not in ["none", "no", "nothing", "n/a", "na"]:
                    state["health_conditions"] = health_conditions
                    logger.info("UPDATED STATE | Health conditions updated to: %s", health_conditions)
                elif not health_conditions.strip():  # Empty string means user denied all conditions
                    state["health_conditions"] = ""
                    logger.info("UPDATED STATE | Health conditions cleared (user denial)")
            
            # Update state with newly detected/updated allergies if they're different
            if allergies != state.get("allergies"):
                # Only update if we detected something new or removed something
                if allergies.strip() and allergies.strip().lower() not in ["none", "no", "nothing", "n/a", "na"]:
                    state["allergies"] = allergies
                    logger.info("UPDATED STATE | Allergies updated to: %s", allergies)
                elif not allergies.strip():  # Empty string means user denied all allergies
                    state["allergies"] = ""
                    logger.info("UPDATED STATE | Allergies cleared (user denial)")
            
            # Update state with newly detected/updated medications if they're different
            if medications != state.get("medications"):
                # Only update if we detected something new or removed something
                if medications.strip() and medications.strip().lower() not in ["none", "no", "nothing", "n/a", "na"]:
                    state["medications"] = medications
                    logger.info("UPDATED STATE | Medications updated to: %s", medications)
                elif not medications.strip():  # Empty string means user denied all medications
                    state["medications"] = ""
                    logger.info("UPDATED STATE | Medications cleared (user denial)")

            # Update state with newly detected/updated supplements if they're different
            if supplements != state.get("supplements"):
                # Only update if we detected something new or removed something
                if supplements.strip() and supplements.strip().lower() not in ["none", "no", "nothing", "n/a", "na"]:
                    state["supplements"] = supplements
                    logger.info("UPDATED STATE | Supplements updated to: %s", supplements)
                elif not supplements.strip():  # Empty string means user denied all supplements
                    state["supplements"] = ""
                    logger.info("UPDATED STATE | Supplements cleared (user denial)")

            # Update state with newly detected/updated gut health if it's different
            if gut_health != state.get("gut_health"):
                # Only update if we detected something new or removed something
                if gut_health.strip() and gut_health.strip().lower() not in ["none", "no", "nothing", "n/a", "na"]:
                    state["gut_health"] = gut_health
                    logger.info("UPDATED STATE | Gut health updated to: %s", gut_health)
                elif not gut_health.strip():  # Empty string means user denied all gut health issues
                    state["gut_health"] = ""
                    logger.info("UPDATED STATE | Gut health cleared (user denial)")

            health_context_parts = []
            if health_conditions:
                if isinstance(health_conditions, (list, tuple, set)):
                    health_text = ", ".join([str(h) for h in health_conditions if h])
                else:
                    health_text = str(health_conditions)
                # Only add if not empty and not "none"
                if health_text.strip() and health_text.strip().lower() not in ["none", "no", "nothing", "n/a", "na"]:
                    health_context_parts.append(f"Health conditions: {health_text}")
            
            if allergies:
                if isinstance(allergies, (list, tuple, set)):
                    allergies_text = ", ".join([str(a) for a in allergies if a])
                else:
                    allergies_text = str(allergies)
                if allergies_text.strip() and allergies_text.strip().lower() not in ["none", "no", "nothing", "n/a", "na"]:
                    health_context_parts.append(f"Allergies: {allergies_text}")
            
            if medications:
                if isinstance(medications, (list, tuple, set)):
                    medications_text = ", ".join([str(m) for m in medications if m])
                else:
                    medications_text = str(medications)
                if medications_text.strip() and medications_text.strip().lower() not in ["none", "no", "nothing", "n/a", "na"]:
                    health_context_parts.append(f"Medications: {medications_text}")

            if supplements:
                if isinstance(supplements, (list, tuple, set)):
                    supplements_text = ", ".join([str(s) for s in supplements if s])
                else:
                    supplements_text = str(supplements)
                if supplements_text.strip() and supplements_text.strip().lower() not in ["none", "no", "nothing", "n/a", "na"]:
                    health_context_parts.append(f"Supplements: {supplements_text}")

            if gut_health:
                if isinstance(gut_health, (list, tuple, set)):
                    gut_health_text = ", ".join([str(g) for g in gut_health if g])
                else:
                    gut_health_text = str(gut_health)
                if gut_health_text.strip() and gut_health_text.strip().lower() not in ["none", "no", "nothing", "n/a", "na"]:
                    health_context_parts.append(f"Gut health: {gut_health_text}")

            # Add User Order Context
            user_order = state.get("user_order")
            user_order_date = state.get("user_order_date")
            if user_order and str(user_order).lower() not in ["none", "no", "nil", "nothing"]:
                 order_context = f"User's Purchased Product: {user_order}"
                 if user_order_date:
                     order_context += f" (Ordered on {user_order_date})"
                 health_context_parts.append(order_context)

            # Prepend health context so it's always considered regardless of contextual/non-contextual path
            if health_context_parts:
                final_question = "\n".join(health_context_parts) + "\n\n" + final_question

            response = requests.post(
                qna_url, 
                json={
                    "question": final_question,
                    "model_type": "llama"  # Use optimized prompts for better responses
                }, 
                timeout=50
            )

            if response.status_code == 200:
                qna_data = response.json()
                answer = qna_data.get("answer", "")
                category = qna_data.get("category", "general")
                knowledge_status = qna_data.get("knowledge_status", "complete")
                health_warnings = qna_data.get("health_warnings", [])
                
                # If there are health warnings, append them to the answer
                if health_warnings and answer:
                    answer = answer + "\n\n" + "\n".join(health_warnings)

                # Check if we got a meaningful answer
                if answer and answer.strip() and len(answer.strip()) > 20:
                    # Add emojis based on category with random selection
                    if category == "product":
                        emoji_prefix = random.choice(["🦠", "🧬", "🧪", "🔬"])
                    elif category == "shipping":
                        emoji_prefix = random.choice(["📦", "🚚", "🚢", "✈️"])
                    elif category == "refund":
                        emoji_prefix = random.choice(["💰", "💳", "🧾", "🔄"])
                    elif category == "policy":
                        emoji_prefix = random.choice(["📋", "📜", "📖", "⚖️"])
                    else:
                        emoji_prefix = random.choice(["💚", "❤️", "💙", "💜"])

                    formatted_answer = f"{emoji_prefix} {answer}"
                else:
                    # If API didn't have a good answer, provide a helpful fallback
                    if is_contextual_product:
                        # For contextual questions, be more specific about the limitation
                        formatted_answer = "💚 For specific usage questions like this, I'd recommend contacting our support team at [tgb@seventurns.in](mailto:tgb@seventurns.in) or call 8369744934. They can provide detailed guidance based on your individual needs!"
                    else:
                        # For direct product questions, use standard fallback
                        formatted_answer = "💚 I'd be happy to help with more specific product information! Please contact our support team at [tgb@seventurns.in](mailto:tgb@seventurns.in) or call 8369744934 for detailed guidance."

            else:
                # Fallback response if API fails
                formatted_answer = "💚 I'd be happy to help with product information! Please contact our support team at [tgb@seventurns.in](mailto:tgb@seventurns.in) or call 8369744934 for detailed product guidance."

        except Exception as e:
            logger.error("QnA API Error: %s", e)
            # Fallback response if API is unavailable
            formatted_answer = "💚 I'd love to help with product information! Please contact our support team at [tgb@seventurns.in](mailto:tgb@seventurns.in) or call 8369744934 for detailed product guidance."

        send_multiple_messages(state["user_id"], formatted_answer, send_whatsapp_message)

        # Store product conversation in history
        # IMPROVED: Use the same product detection logic as is_product_question
        # Extract product name from question if possible
        product_mentioned = None
        user_msg_lower = user_question.lower()

        # Use the same specific product names as the improved is_product_question function
        specific_product_names = [
            'metabolically lean', 'metabolic fiber boost', 'ams', 'metabolically lean - probiotics',
            'advanced metabolic system', 'gut cleanse', 'gut balance', 'bye bye bloat',
            'smooth move', 'ibs rescue', 'water kefir', 'kombucha', 'fermented pickles',
            'prebiotic shots', 'sleep and calm', 'first defense', 'good to glow',
            'pcos balance', 'good down there', 'fiber boost', 'happy tummy', 'metabolic fiber',
            'happy tummies', 'glycemic control', 'gut cleanse super bundle',
            'acidity aid', 'ibs dnm', 'ibs rescue d&m', 'ibs c', 'ibs d', 'ibs m',
            'gut cleanse detox shot', 'gut cleanse shot', 'prebiotic fiber boost',
            'smooth move fiber boost', 'constipation bundle', 'pcos bundle',
            'metabolically lean supercharged', 'ferments', 'squat buddy'
        ]

        # Check for specific TGB product mentions
        # IMPROVED: Use word boundary matching to avoid false positives
        for product in specific_product_names:
            pattern = r'\b' + re.escape(product) + r'\b'
            if re.search(pattern, user_msg_lower):
                product_mentioned = product
                break

        # Store the actual product name and question for better context
        # Use relevant_product (from history) as fallback if product_mentioned (from current question) is not available
        # This ensures contextual follow-ups are properly tagged in conversation history
        product_for_history = product_mentioned or relevant_product
        content = formatted_answer if 'formatted_answer' in locals() else "Product information"
        if product_for_history:
            content = f"About {product_for_history}: {content}"

        # Update conversation history
        if state.get("conversation_history") is None:
            state["conversation_history"] = []

        state["conversation_history"].append({
            "role": "user",
            "content": user_question
        })
        
        state["conversation_history"].append({
            "role": "assistant",
            "content": content
        })

    else:
        # Default to health question handling using LLM
        # No need to check is_health_question - if it's not a product question, treat it as health
        
        # =====================================================
        # GUARDRAIL CHECK 1: Emergency Detection (CTAS)
        # =====================================================
        is_emergency, ctas_level, emergency_category, emergency_response = \
            emergency_detector.detect_emergency(user_question)
        
        if is_emergency:
            # Send emergency response immediately
            send_multiple_messages(state["user_id"], emergency_response, send_whatsapp_message)
            
            # Log to conversation history
            if state.get("conversation_history") is None:
                state["conversation_history"] = []
            state["conversation_history"].append({"role": "user", "content": user_question})
            state["conversation_history"].append({"role": "assistant", "content": emergency_response})
            
            # Keep conversation history manageable
            if len(state["conversation_history"]) > 20:
                state["conversation_history"] = state["conversation_history"][-20:]
            
            state["post_plan_qna_answered"] = True
            return state
        
        # =====================================================
        # GUARDRAIL CHECK 2: Medical Guardrails (including Gut Coach Connection)
        # =====================================================
        # Build health context from state
        health_context = {
            "health_conditions": state.get("health_conditions", ""),
            "allergies": state.get("allergies", ""),
            "medications": state.get("medications", ""),
            "supplements": state.get("supplements", ""),
            "gut_health": state.get("gut_health", "")
        }
        
        guardrail_triggered, guardrail_type, guardrail_response = \
            medical_guardrails.check_guardrails(user_question, health_context)
        
        if guardrail_triggered:
            # Send guardrail response immediately
            send_multiple_messages(state["user_id"], guardrail_response, send_whatsapp_message)
            
            # Log to conversation history
            if state.get("conversation_history") is None:
                state["conversation_history"] = []
            state["conversation_history"].append({"role": "user", "content": user_question})
            state["conversation_history"].append({"role": "assistant", "content": guardrail_response})
            
            # Keep conversation history manageable
            if len(state["conversation_history"]) > 20:
                state["conversation_history"] = state["conversation_history"][-20:]
            
            state["post_plan_qna_answered"] = True
            return state
        
        # Build conversation history context if available
        conversation_context = ""
        if conversation_history:
            recent_messages = conversation_history[-8:]  # Use last 8 messages for context
            conversation_context = "\n\nRECENT CONVERSATION HISTORY:\n" + "\n".join([
                f"{msg.get('role', 'unknown')}: {msg.get('content', '')}" 
                for msg in recent_messages
            ])

        template = load_prompt("agent/post_plan_qna_node.md")
        prompt = template.format(
            user_context=user_context,
            user_question=user_question,
            user_name=state.get("user_name", ""),
            conversation_context=conversation_context,
            user_order=state.get("user_order", "None"),
            user_order_date=state.get("user_order_date", "")
        )

        response = llm.invoke(prompt)
        answer = response.content.strip()
        send_multiple_messages(state["user_id"], answer, send_whatsapp_message)

        # Update conversation history with health exchange
        if state.get("conversation_history") is None:
            state["conversation_history"] = []

        state["conversation_history"].append({
            "role": "user",
            "content": user_question
        })
        
        state["conversation_history"].append({
            "role": "assistant",
            "content": answer
        })

    # Keep conversation history manageable (last 20 messages)
    if len(state["conversation_history"]) > 20:
        state["conversation_history"] = state["conversation_history"][-20:]

    # Stay in post-plan Q&A state
    state["last_question"] = "post_plan_qna"
    state["current_agent"] = "post_plan_qna"

    return state



def resume_from_qna_node(state: State) -> State:
    """Node: Resume the conversation flow after health or product Q&A."""
    # Random transition messages to make it feel more natural
    transition_messages = [
        "💚 Let's pick up where we left off...",
        "🌟 Now, back to your personalized plan...",
        "✨ Great! Let's continue with your wellness journey...",
        "💫 Perfect! Now let's get back to creating your plan...",
        "🌸 Awesome! Let's continue where we paused...",
        "💝 Thanks for that question! Now, back to your plan...",
        "🌿 Got it! Let's resume building your wellness plan...",
        "💖 Hope that helped! Now, let's continue...",
        "🌺 Wonderful! Let's get back to your personalized journey...",
        "✨ That's sorted! Now, back to crafting your plan...",
        "💚 Perfect! Let's continue with the next step...",
        "🌟 Great question! Now, let's pick up where we were..."
    ]
    
    random_message = random.choice(transition_messages)
    send_whatsapp_message(state["user_id"], random_message)
    
    # Clear pending_node if both plans are completed
    if state.get("meal_plan_sent") and state.get("exercise_plan_sent"):
        state["pending_node"] = None
    # Make sure we have a pending node only if we're still in plan generation
    elif not state.get("pending_node"):
        # Default to height if we're coming from age
        if state.get("age") and not state.get("height"):
            state["pending_node"] = "collect_height"
        else:
            # Use the current last_question as a fallback
            current_question = state.get("last_question", "").replace("_answered", "")
            if current_question in ["health_qna", "product_qna"]:
                # If we don't have a valid pending node, go to age as fallback
                state["pending_node"] = "collect_age"
    
    # Set the appropriate last_question for resumption
    if state.get("last_question") == "health_qna_answered":
        state["last_question"] = "resuming_from_health_qna"
    elif state.get("last_question") == "product_qna_answered":
        state["last_question"] = "resuming_from_product_qna"
    
    return state


# --- Plan Edit Functions ---

def handle_meal_edit_request(state: State, day_num: Optional[int] = None) -> State:
    """
    Handle meal plan edit request from post-plan Q&A.
    Routes user to meal plan edit flow.
    """
    from app.services.whatsapp.client import send_whatsapp_message, _send_whatsapp_list
    
    user_id = state.get("user_id")
    
    if day_num:
        # User specified a day - ask for changes
        send_whatsapp_message(
            user_id,
            f"Got it! 📝 What changes would you like to make to your Day {day_num} meal plan?\\n\\n"
            f"For example:\\n"
            f"- \"Add more protein\"\\n"
            f"- \"Make it vegetarian\"\\n"
            f"- \"Replace rice with quinoa\"\\n"
            f"- \"Reduce calories\""
        )
        state["edit_mode"] = "meal"
        state["edit_day_number"] = day_num
        state[f"meal_day{day_num}_change_request"] = ""  # Will be filled when user responds
        state["last_question"] = f"awaiting_meal_day{day_num}_edit_changes"
        state["pending_node"] = f"collect_meal_day_edit_changes"
    else:
        # No day specified - ask which day to edit
        sections = [
            {
                "title": "📅 Select Day to Edit",
                "rows": [
                    {"id": f"edit_meal_day{i}", "title": f"Day {i}", "description": f"Edit Day {i} meal plan"}
                    for i in range(1, 8)
                ]
            }
        ]
        
        _send_whatsapp_list(
            user_id=user_id,
            body_text="Which day's meal plan would you like to edit?",
            button_text="Select Day 📅",
            sections=sections,
            header_text="Edit Meal Plan"
        )
        state["edit_mode"] = "meal"
        state["last_question"] = "select_meal_day_to_edit"
        state["pending_node"] = "handle_meal_day_selection_for_edit"
    
    return state


def handle_exercise_edit_request(state: State, day_num: Optional[int] = None) -> State:
    """
    Handle exercise plan edit request from post-plan Q&A.
    Routes user to exercise plan edit flow.
    """
    from app.services.whatsapp.client import send_whatsapp_message, _send_whatsapp_list
    
    user_id = state.get("user_id")
    
    if day_num:
        # User specified a day - ask for changes
        send_whatsapp_message(
            user_id,
            f"Got it! 💪 What changes would you like to make to your Day {day_num} exercise plan?\\n\\n"
            f"For example:\\n"
            f"- \"Make it easier\"\\n"
            f"- \"Add more cardio\"\\n"
            f"- \"Replace running with cycling\"\\n"
            f"- \"Shorter workout duration\""
        )
        state["edit_mode"] = "exercise"
        state["edit_day_number"] = day_num
        state[f"day{day_num}_change_request"] = ""  # Will be filled when user responds
        state["last_question"] = f"awaiting_exercise_day{day_num}_edit_changes"
        state["pending_node"] = f"collect_exercise_day_edit_changes"
    else:
        # No day specified - ask which day to edit
        sections = [
            {
                "title": "📅 Select Day to Edit",
                "rows": [
                    {"id": f"edit_exercise_day{i}", "title": f"Day {i}", "description": f"Edit Day {i} exercise plan"}
                    for i in range(1, 8)
                ]
            }
        ]
        
        _send_whatsapp_list(
            user_id=user_id,
            body_text="Which day's exercise plan would you like to edit?",
            button_text="Select Day 📅",
            sections=sections,
            header_text="Edit Exercise Plan"
        )
        state["edit_mode"] = "exercise"
        state["last_question"] = "select_exercise_day_to_edit"
        state["pending_node"] = "handle_exercise_day_selection_for_edit"
    
    return state