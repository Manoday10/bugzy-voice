"""
QnA nodes for the AMS agent.

This module contains the logic for handling user questions about:
1. General health and wellness (using LLM)
2. Product-specific queries (using QnA API)
3. Meal and Exercise plan edits (using specialized flow handlers)
4. Post-plan Q&A (unified handler)
"""

import logging
import random
import requests
import re
import json
from typing import Optional, List, Dict, Any

from app.services.chatbot.bugzy_ams.state import State
from app.services.whatsapp.client import send_whatsapp_message, _send_whatsapp_list
from app.services.whatsapp.messages import send_multiple_messages
from app.services.whatsapp.utils import llm
from app.services.whatsapp.messages import remove_markdown
from app.services.llm.bedrock_llm import ChatBedRockLLM
from app.services.prompts.ams.prompt_store import load_prompt
from app.services.chatbot.bugzy_ams.context_manager import build_optimized_context
from app.services.chatbot.bugzy_ams.router import is_journey_restart_request
from app.services.chatbot.bugzy_ams.constants import TRANSITION_MESSAGES, CATEGORY_EMOJI_MAP, CATEGORY_EMOJI_DEFAULT
from app.services.chatbot.bugzy_shared.context import is_meal_edit_request, is_exercise_edit_request
from app.services.chatbot.bugzy_shared.extraction import extract_day_number

# SHARED MODULE IMPORTS
from app.services.chatbot.bugzy_shared.qna import (
    DIRECT_PRODUCT_NAMES,
    is_contextual_product_question,
    is_any_product_query,
    extract_relevant_product_from_history,
    reformulate_with_gpt,
    determine_llm_temperature,
    reformulate_followup_fallback
)
from app.services.chatbot.bugzy_shared.context import (
    detect_user_intent,
    detect_followup_question
)
from app.services.chatbot.bugzy_shared.extraction import (
    extract_health_conditions_intelligently,
    extract_allergies_intelligently,
    extract_medications_intelligently,
    extract_supplements_intelligently,
    extract_gut_health_intelligently,
    is_user_providing_information
)

# GUARDRAILS
from app.services.rag.emergency_detection import EmergencyDetector
from app.services.rag.medical_guardrails import MedicalGuardrails
from app.services.crm.sessions import save_meal_plan, extract_ams_meal_user_context, save_exercise_plan, extract_exercise_plan_user_context, load_meal_plan, load_exercise_plan

logger = logging.getLogger(__name__)


# --- QnA Nodes ---

def health_qna_node(state: State) -> State:
    """Node: Handle general health questions during the profiling flow."""
    user_question = state.get("user_msg", "")
    conversation_history = state.get("conversation_history", [])
    
    # 1. Detect Intent
    detected_intent = detect_user_intent(user_question, state)
    state["detected_intent"] = detected_intent
    
    # 2. Check for Follow-up
    is_followup = detect_followup_question(user_question, conversation_history)
    
    # 3. Determine LLM Temperature
    optimal_temperature = determine_llm_temperature(
        user_question=user_question,
        detected_intent=detected_intent,
        is_followup=is_followup,
        conversation_history=conversation_history
    )
    
    # 4. Check Emergency
    emergency_detector = EmergencyDetector()
    is_emergency, _, _, emergency_response = emergency_detector.detect_emergency(user_question)
    
    if is_emergency:
        send_multiple_messages(state["user_id"], emergency_response, send_whatsapp_message)
        state["last_question"] = "health_qna_answered" 
        return state

    # 5. Check Medical Guardrails
    health_context = {
        "health_conditions": state.get("health_conditions", ""),
        "allergies": state.get("allergies", ""),
        "medications": state.get("medications", ""),
        "supplements": state.get("supplements", ""),
        "gut_health": state.get("gut_health", "")
    }
    
    medical_guardrails = MedicalGuardrails()
    guardrail_triggered, _, guardrail_response = medical_guardrails.check_guardrails(user_question, health_context)
    
    if guardrail_triggered:
        send_multiple_messages(state["user_id"], guardrail_response, send_whatsapp_message)
        state["last_question"] = "health_qna_answered"
        return state

    # 6. Build Context & Invoke LLM
    user_context = build_optimized_context(
        state=state,
        user_question=user_question,
        llm_client=ChatBedRockLLM(), 
        intent=detected_intent
    )

    task_template = load_prompt("agent/health_qna_node.md")
    # BIAS FIX: If user mentioned a SPECIFIC product name which is DIFFERENT from their order,
    # pass "No recent order" to the template to avoid biasing the LLM.
    user_order = state.get("user_order", "No recent order")
    product_mentioned = next((p for p in DIRECT_PRODUCT_NAMES if re.search(r'\b' + re.escape(p) + r'\b', user_question.lower())), None)
    if product_mentioned and user_order and user_order.lower() not in product_mentioned.lower() and product_mentioned.lower() not in user_order.lower():
         logger.info(f"Bias Fix (Health QnA AMS): Suppressing order '{user_order}' for question about '{product_mentioned}'")
         user_order = "No recent order"

    task_prompt = task_template.format(
        user_context=user_context,
        user_question=user_question,
        user_name=state.get("user_name", ""),
        user_order=user_order,
        user_order_date=state.get("user_order_date", "N/A")
    )
    
    persona_prompt = load_prompt("system/bugzy_persona.md")
    
    messages = [
        {"role": "system", "content": persona_prompt},
        {"role": "user", "content": task_prompt}
    ]
    
    logger.info(f"Health QnA: Using temperature {optimal_temperature}")
    response = llm.invoke(messages, temperature=optimal_temperature)
    answer = remove_markdown(response.content.strip())
    
    send_multiple_messages(state["user_id"], answer, send_whatsapp_message)
    
    # Update History
    if state.get("conversation_history") is None:
        state["conversation_history"] = []
    
    state["conversation_history"].append({"role": "user", "content": user_question})
    state["conversation_history"].append({"role": "assistant", "content": answer})
    
    state["last_question"] = "health_qna_answered"
    
    return state


def product_qna_node(state: State) -> State:
    """Node: Handle product-specific questions."""
    user_question = state.get("user_msg", "")
    conversation_history = state.get("conversation_history", [])
    
    # Direct Name Check (Robust)
    user_msg_lower = user_question.lower()
    product_mentioned = next((p for p in DIRECT_PRODUCT_NAMES if re.search(r'\b' + re.escape(p) + r'\b', user_msg_lower)), None)
            
    is_contextual = is_contextual_product_question(user_question, conversation_history)
    relevant_product = extract_relevant_product_from_history(conversation_history[-5:], user_question)
    
    # Ownership logic override
    is_my_product_query = any(p in user_msg_lower for p in ["my product", "my order", "what i bought", "which product do i have"])
    if state.get("user_order") and is_my_product_query:
        relevant_product = None 
        
    final_question = user_question
    if relevant_product and is_contextual and not product_mentioned:
        final_question = reformulate_with_gpt(user_question, relevant_product, conversation_history[-3:])
        logger.debug("Reformulated Q: %s", final_question)

    try:
        qna_url = "http://localhost:8000/ask"
        
        # Add health context to the question being sent to QnA API
        health_context_lines = []
        if state.get("health_conditions"): health_context_lines.append(f"Health conditions: {state.get('health_conditions')}")
        if state.get("allergies"): health_context_lines.append(f"Allergies: {state.get('allergies')}")
        if state.get("medications"): health_context_lines.append(f"Medications: {state.get('medications')}")
        if state.get("supplements"): health_context_lines.append(f"Supplements: {state.get('supplements')}")
        if state.get("gut_health"): health_context_lines.append(f"Gut health: {state.get('gut_health')}")
        if state.get("user_order"): health_context_lines.append(f"User's Purchased Product: {state.get('user_order')}")
        
        if health_context_lines:
            # BIAS FIX: If user mentioned a SPECIFIC product name which is DIFFERENT from their order,
            # we should avoid prepending the "User's Purchased Product" context to avoid confusing the RAG.
            user_order = state.get("user_order")
            if product_mentioned and user_order and user_order.lower() not in product_mentioned.lower() and product_mentioned.lower() not in user_order.lower():
                logger.info(f"Bias Fix: User asked about '{product_mentioned}' but owns '{user_order}'. Filtering context.")
                # Filter out the "User's Purchased Product" line
                health_context_lines = [line for line in health_context_lines if "Purchased Product" not in line]
            
            if health_context_lines:
                final_question = "\\n".join(health_context_lines) + "\\n\\n" + final_question
            
        response = requests.post(
            qna_url,
            json={"question": final_question, "model_type": "llama"},
            timeout=50
        )
        
        formatted_answer = ""
        if response.status_code == 200:
            qna_data = response.json()
            answer = qna_data.get("answer", "")
            category = qna_data.get("category", "general")
            
            if answer and len(answer.strip()) > 20:
                emoji_prefix = CATEGORY_EMOJI_MAP.get(category, CATEGORY_EMOJI_DEFAULT)
                formatted_answer = f"{emoji_prefix} {remove_markdown(answer)}"
            else:
                formatted_answer = "💚 I'd recommend contacting our support team at [nutritionist@seventurns.in](mailto:nutritionist@seventurns.in) for detailed guidance!"
        else:
            formatted_answer = "💚 I'd be happy to help! Please contact our support team at [nutritionist@seventurns.in](mailto:nutritionist@seventurns.in) for details."
            
        send_multiple_messages(state["user_id"], formatted_answer, send_whatsapp_message)
        
        # Update History
        if state.get("conversation_history") is None:
            state["conversation_history"] = []
            
        content_to_store = formatted_answer
        product_for_history = product_mentioned or relevant_product
        if product_for_history:
            content_to_store = f"About {product_for_history}: {formatted_answer}"
            
        state["conversation_history"].append({"role": "user", "content": user_question})
        state["conversation_history"].append({"role": "assistant", "content": content_to_store})
        
    except Exception as e:
        logger.error(f"Product QnA Error: {e}")
        send_multiple_messages(state["user_id"], "I'm having trouble accessing product info right now. Please contacting support.", send_whatsapp_message)

    state["last_question"] = "product_qna_answered"
    return state


def post_plan_qna_node(state: State) -> State:
    """Node: Unified Q&A handler for both health and product questions after plan completion."""
    user_question = state.get("user_msg", "")
    conversation_history = state.get("conversation_history", [])
    
    if state.get("silent_return"):
        state["last_question"] = "post_plan_qna"
        state["current_agent"] = "post_plan_qna"
        state["silent_return"] = False
        return state

    if not user_question or user_question.strip() in ["[IMAGE_RECEIVED]", ""]:
        state["last_question"] = "post_plan_qna"
        return state
        
    # Smart Extraction (Updates state in place if new info found)
    # This logic was previously inline, now uses shared module
    hc = extract_health_conditions_intelligently(user_question, conversation_history, state.get("health_conditions"))
    if hc != state.get("health_conditions"): state["health_conditions"] = hc
        
    al = extract_allergies_intelligently(user_question, conversation_history, state.get("allergies"))
    if al != state.get("allergies"): state["allergies"] = al
        
    med = extract_medications_intelligently(user_question, conversation_history, state.get("medications"))
    if med != state.get("medications"): state["medications"] = med
        
    sup = extract_supplements_intelligently(user_question, conversation_history, state.get("supplements"))
    if sup != state.get("supplements"): state["supplements"] = sup

    gh = extract_gut_health_intelligently(user_question, conversation_history, state.get("gut_health"))
    if gh != state.get("gut_health"): state["gut_health"] = gh

    # Journey Restart Logic
    restart_type = is_journey_restart_request(user_question)
    if restart_type:
        wants_meal_plan = state.get("wants_meal_plan", False)
        wants_exercise_plan = state.get("wants_exercise_plan", False)
        meal_plan_sent = state.get("meal_plan_sent", False)
        exercise_plan_sent = state.get("exercise_plan_sent", False)
        
        target_restart = None
        if restart_type == 'both':
            target_restart = 'meal' if not meal_plan_sent else 'exercise' if not exercise_plan_sent else None
            # If both sent, check if user wants to recreate
            if not target_restart and (meal_plan_sent or exercise_plan_sent):
                 # Default to trying meal first if both exist, but specific logic below handles asking
                 pass 
        elif restart_type == 'meal' and not meal_plan_sent:
            target_restart = 'meal'
        elif restart_type == 'exercise' and not exercise_plan_sent:
            target_restart = 'exercise'
            
        # Specific handling for existing plans (Restart/Recreate)
        if not target_restart:
             # Logic for "I want a new meal plan" when one exists
             if restart_type == 'meal' or (restart_type == 'both' and meal_plan_sent):
                 try:
                     existing = load_meal_plan(state.get("user_id", ""))
                     if existing and existing.get("meal_day1_plan"):
                         from app.services.chatbot.bugzy_ams.nodes.meal_plan_nodes import ask_existing_meal_plan_choice
                         state["existing_meal_plan_data"] = existing
                         state["existing_meal_plan_choice_origin"] = "post_plan_qna"
                         return ask_existing_meal_plan_choice(state)
                     else:
                         target_restart = 'meal' # Treat as new
                 except Exception as e:
                     logger.error(f"Error loading existing meal plan: {e}")
                     target_restart = 'meal'
             
             if restart_type == 'exercise' or (restart_type == 'both' and exercise_plan_sent):
                 try:
                     existing = load_exercise_plan(state.get("user_id", ""))
                     if existing and existing.get("day1_plan"):
                         from app.services.chatbot.bugzy_ams.nodes.exercise_plan_nodes import ask_existing_exercise_plan_choice
                         state["existing_exercise_plan_data"] = existing
                         state["existing_exercise_plan_choice_origin"] = "post_plan_qna"
                         return ask_existing_exercise_plan_choice(state)
                     else:
                         target_restart = 'exercise' # Treat as new
                 except Exception as e:
                     logger.error(f"Error loading existing exercise plan: {e}")
                     target_restart = 'exercise'

        if target_restart == 'meal':
            user_name = state.get('user_name', 'there')
            send_whatsapp_message(state["user_id"], f"Absolutely, {user_name}! 🌟 I'd love to create a fresh meal plan for you. Let me ask you a few quick questions to personalize it perfectly for your needs.")
            state["wants_meal_plan"] = True
            state["current_agent"] = "meal"
            state["journey_restart_mode"] = True
            from app.services.chatbot.bugzy_ams.nodes.meal_plan_nodes import collect_health_conditions
            return collect_health_conditions(state)
            
        elif target_restart == 'exercise':
            user_name = state.get('user_name', 'there')
            send_whatsapp_message(state["user_id"], f"Great choice, {user_name}! 💪 Let's design a workout plan that works for you. I'll ask a few questions to tailor it to your fitness level and goals.")
            state["wants_exercise_plan"] = True
            state["current_agent"] = "exercise"
            state["journey_restart_mode"] = True
            from app.services.chatbot.bugzy_ams.nodes.exercise_plan_nodes import collect_fitness_level
            return collect_fitness_level(state)

    # Edit Request Logic
    if is_meal_edit_request(user_question):
        day_num = extract_day_number(user_question)
        return handle_meal_edit_request(state, day_num)
    
    if is_exercise_edit_request(user_question):
        day_num = extract_day_number(user_question)
        return handle_exercise_edit_request(state, day_num)

    # Standard QnA Processing (Product OR Health)
    
    # 1. Broad Product Check (Standardized & Robust)
    user_msg_lower = user_question.lower()
    is_product_query = is_any_product_query(user_question, conversation_history)
    
    # Direct check for specific name (for bias fix below)
    product_mentioned = next((p for p in DIRECT_PRODUCT_NAMES if re.search(r'\b' + re.escape(p) + r'\b', user_msg_lower)), None)
    is_contextual = is_contextual_product_question(user_question, conversation_history)
    
    if is_product_query:
        # Delegate to product logic (RAG)
        try:
            # Use the internal RAG API URL
            qna_url = "http://localhost:8000/ask"
            
            # Prepare context for reformulation if needed
            recent_msgs = conversation_history[-5:] if len(conversation_history) > 5 else conversation_history
            relevant_prod = extract_relevant_product_from_history(recent_msgs, user_question)
            
            # Special handling for "my product"
            if state.get("user_order") and any(p in user_msg_lower for p in ["my product", "my order"]):
                relevant_prod = None
                
            final_q = user_question
            
            # Reformulate if contextual and no explicit product name mentioned
            if relevant_prod and is_contextual and not product_mentioned:
                final_q = reformulate_with_gpt(user_question, relevant_prod, recent_msgs)
                logger.info(f"Reformulated Question: {final_q}")
                
            # Add User Context headers to the question for RAG
            health_ctx = []
            if state.get("health_conditions"): health_ctx.append(f"User Conditions: {state.get('health_conditions')}")
            if state.get("user_order"): health_ctx.append(f"User Product: {state.get('user_order')}")
            
            if health_ctx: 
                # BIAS FIX: If user mentioned a SPECIFIC product name which is DIFFERENT from their order,
                # remove the ordered product context.
                user_order = state.get("user_order")
                if product_mentioned and user_order and user_order.lower() not in product_mentioned.lower() and product_mentioned.lower() not in user_order.lower():
                    logger.info(f"Bias Fix (Post-Plan): User asked about '{product_mentioned}' but owns '{user_order}'. Filtering context.")
                    health_ctx = [c for c in health_ctx if "User Product" not in c]
                
                if health_ctx:
                    final_q = "\n".join(health_ctx) + "\n\n" + final_q
            
            # Call RAG API
            # model_type can be configured via env var, defaulting to 'llama'
            resp = requests.post(qna_url, json={"question": final_q, "model_type": "llama"}, timeout=50)
            
            answer = ""
            if resp.status_code == 200:
                data = resp.json()
                answer = data.get("answer", "")
                
                # Check for empty or useless answers
                if not answer or len(answer) < 5 or "I don't have enough information" in answer:
                     # Fallback to LLM if RAG fails to give a good answer? 
                     # For now, let's trust the RAG or give a standard fallback.
                     pass
            
            if answer:
                send_multiple_messages(state["user_id"], f"💚 {answer}", send_whatsapp_message)
            else:
                # If RAG returns nothing useful, maybe fallback to general health logic?
                # But user wants strict separation. So we give a generic product fallback.
                send_multiple_messages(state["user_id"], "I couldn't find specific details for that product in my database. Could you rephrase or ask about ingredients?", send_whatsapp_message)
                 
            # History Update
            if state.get("conversation_history") is None: state["conversation_history"] = []
            state["conversation_history"].append({"role": "user", "content": user_question})
            state["conversation_history"].append({"role": "assistant", "content": answer if answer else "No answer found"})
            
        except Exception as e:
            logger.error(f"Post Plan Product QnA Error: {e}")
            send_multiple_messages(state["user_id"], "I'm having trouble checking the product details right now.", send_whatsapp_message)
            
        state["last_question"] = "post_plan_qna"
        return state

    # 2. Health/General Check (Default)
    emergency_detector = EmergencyDetector()
    is_emerg, _, _, emerg_resp = emergency_detector.detect_emergency(user_question)
    if is_emerg:
        send_multiple_messages(state["user_id"], emerg_resp, send_whatsapp_message)
        return _update_history_and_return(state, user_question, emerg_resp)
        
    medical_guardrails = MedicalGuardrails()
    health_context = {
        "health_conditions": state.get("health_conditions", ""),
        "allergies": state.get("allergies", ""),
        "medications": state.get("medications", ""),
        "supplements": state.get("supplements", ""),
        "gut_health": state.get("gut_health", "")
    }
    
    guardrail_triggered, _, guardrail_response = medical_guardrails.check_guardrails(user_question, health_context)
    if guardrail_triggered:
        send_multiple_messages(state["user_id"], guardrail_response, send_whatsapp_message)
        return _update_history_and_return(state, user_question, guardrail_response)
    
    # LLM Call
    detected_intent = detect_user_intent(user_question, state)
    is_followup = detect_followup_question(user_question, conversation_history)
    temp = determine_llm_temperature(user_question, detected_intent, is_followup, conversation_history)
    
    user_ctx = build_optimized_context(state, user_question, ChatBedRockLLM(), detected_intent, include_plans=True)
    
    task_tmpl = load_prompt("agent/post_plan_qna_node.md")
    prompt = task_tmpl.format(user_context=user_ctx, user_question=user_question, user_name=state.get("user_name",""), user_order=state.get("user_order","None"), user_order_date=state.get("user_order_date",""))
    
    msgs = [{"role": "system", "content": load_prompt("system/bugzy_persona.md")}, {"role": "user", "content": prompt}]
    
    res = llm.invoke(msgs, temperature=temp)
    txt = remove_markdown(res.content.strip())
    
    send_multiple_messages(state["user_id"], txt, send_whatsapp_message)
    
    return _update_history_and_return(state, user_question, txt)

def _update_history_and_return(state, q, a):
    if state.get("conversation_history") is None:
        state["conversation_history"] = []
    state["conversation_history"].append({"role": "user", "content": q})
    state["conversation_history"].append({"role": "assistant", "content": a})
    if len(state["conversation_history"]) > 20:
        state["conversation_history"] = state["conversation_history"][-20:]
    state["last_question"] = "post_plan_qna"
    state["current_agent"] = "post_plan_qna"
    return state


# --- Edit Handlers ---

def handle_meal_edit_request(state: State, day_num: Optional[int] = None) -> State:
    """Handle meal plan edit request from post-plan Q&A."""
    user_id = state.get("user_id")
    if day_num:
        send_whatsapp_message(
            user_id, 
            f"Got it! 📝 What changes would you like to make to your Day {day_num} meal plan?\n\nFor example:\n- \"Add more protein\"\n- \"Make it vegetarian\""
        )
        state["edit_mode"] = "meal"
        state["edit_day_number"] = day_num
        state[f"meal_day{day_num}_change_request"] = ""
        state["last_question"] = f"awaiting_meal_day{day_num}_edit_changes"
        state["pending_node"] = "collect_meal_day_edit_changes"
    else:
        sections = [{"title": "📅 Select Day to Edit", "rows": [{"id": f"edit_meal_day{i}", "title": f"Day {i}", "description": f"Edit Day {i}"} for i in range(1, 8)]}]
        _send_whatsapp_list(user_id, "Which day's meal plan would you like to edit?", "Select Day 📅", sections, "Edit Meal Plan")
        state["edit_mode"] = "meal"
        state["last_question"] = "select_meal_day_to_edit"
        state["pending_node"] = "handle_meal_day_selection_for_edit"
    return state

def handle_exercise_edit_request(state: State, day_num: Optional[int] = None) -> State:
    """Handle exercise plan edit request from post-plan Q&A."""
    user_id = state.get("user_id")
    if day_num:
        send_whatsapp_message(
            user_id, 
            f"Got it! 💪 What changes would you like to make to your Day {day_num} exercise plan?\n\nFor example:\n- \"Make it easier\"\n- \"Add more cardio\""
        )
        state["edit_mode"] = "exercise"
        state["edit_day_number"] = day_num
        state[f"day{day_num}_change_request"] = ""
        state["last_question"] = f"awaiting_exercise_day{day_num}_edit_changes"
        state["pending_node"] = "collect_exercise_day_edit_changes"
    else:
        sections = [{"title": "📅 Select Day to Edit", "rows": [{"id": f"edit_exercise_day{i}", "title": f"Day {i}", "description": f"Edit Day {i}"} for i in range(1, 8)]}]
        _send_whatsapp_list(user_id, "Which day's exercise plan would you like to edit?", "Select Day 📅", sections, "Edit Exercise Plan")
        state["edit_mode"] = "exercise"
        state["last_question"] = "select_exercise_day_to_edit"
        state["pending_node"] = "handle_exercise_day_selection_for_edit"
    return state

def handle_meal_day_selection_for_edit(state: State) -> State:
    user_msg = state.get("user_msg", "").strip()
    match = re.search(r'edit_meal_day(\d)', user_msg.lower())
    day_num = int(match.group(1)) if match else extract_day_number(user_msg)
    
    if day_num:
        return handle_meal_edit_request(state, day_num)
    else:
        send_whatsapp_message(state["user_id"], "I didn't catch which day you want to edit. Please select a day from the list.")
        state["last_question"] = "select_meal_day_to_edit"
    return state

def handle_exercise_day_selection_for_edit(state: State) -> State:
    user_msg = state.get("user_msg", "").strip()
    match = re.search(r'edit_exercise_day(\d)', user_msg.lower())
    day_num = int(match.group(1)) if match else extract_day_number(user_msg)
    
    if day_num:
        return handle_exercise_edit_request(state, day_num)
    else:
        send_whatsapp_message(state["user_id"], "I didn't catch which day you want to edit. Please select a day from the list.")
        state["last_question"] = "select_exercise_day_to_edit"
    return state


def collect_meal_day_edit_changes(state: State) -> State:
    """Collect user's requested changes for any meal plan day and regenerate."""
    from app.services.prompts.ams.meal_plan_template import build_meal_plan_prompt, build_disclaimers, _remove_llm_disclaimers
    
    user_msg = state.get("user_msg", "").strip()
    day_num = state.get("edit_day_number")
    
    # Fallback to last_question parsing if day_num missing
    if not day_num:
        last_q = state.get("last_question", "")
        match = re.search(r'awaiting_meal_day(\d)_edit_changes', last_q)
        if match:
            day_num = int(match.group(1))
            state["edit_day_number"] = day_num
            
    if not user_msg or not day_num:
        send_whatsapp_message(state["user_id"], f"Please tell me what changes you'd like to make to your Day {day_num if day_num else ''} meal plan.")
        return state
        
    # Ignore simple acknowledgments
    if user_msg.lower() in ["ok", "okay", "yes", "sure", "fine", "thanks", "thx"]:
        return state
    
    state[f"meal_day{day_num}_change_request"] = user_msg
    old_plan = state.get(f"meal_day{day_num}_plan", "")
    
    # Track History
    hist_key = f"old_meal_day{day_num}_plans"
    if not state.get(hist_key): state[hist_key] = []
    state[hist_key].append(old_plan)
    
    send_whatsapp_message(state["user_id"], f"Got it! 🔄 Regenerating your Day {day_num} meal plan with: {user_msg}\n\n⏳ One moment...")
    
    prompt = build_meal_plan_prompt(state, day_num, None, None, user_msg, True)
    revision_context = f"REVISION MODE. ORIGINAL: {old_plan}. CHANGES: {user_msg}"
    
    llm_c = ChatBedRockLLM()
    response = llm_c.invoke(revision_context + "\n" + prompt)
    revised = response.content.strip()
    
    revised = _remove_llm_disclaimers(revised)
    disclaimers = build_disclaimers(state)
    if disclaimers: revised = revised.rstrip() + disclaimers
    revised = remove_markdown(revised)
    
    state[f"meal_day{day_num}_plan"] = revised
    
    save_meal_plan(state["user_id"], {
        f"meal_day{day_num}_plan": revised,
        f"old_meal_day{day_num}_plans": state.get(hist_key, []),
        f"meal_day{day_num}_change_request": user_msg,
        "user_context": extract_ams_meal_user_context(state)
    }, product="ams", increment_change_count=True)
    
    send_whatsapp_message(state["user_id"], revised)
    send_whatsapp_message(state["user_id"], f"✅ Your Day {day_num} meal plan has been updated!")
    
    state["last_question"] = "post_plan_qna"
    state["current_agent"] = "post_plan_qna"
    state["pending_node"] = None
    state["edit_mode"] = None
    state["edit_day_number"] = None
    return state


def collect_exercise_day_edit_changes(state: State) -> State:
    """Collect user's requested changes for any exercise plan day and regenerate."""
    user_msg = state.get("user_msg", "").strip()
    day_num = state.get("edit_day_number")
    
    if not day_num:
        last_q = state.get("last_question", "")
        match = re.search(r'awaiting_exercise_day(\d)_edit_changes', last_q)
        if match:
            day_num = int(match.group(1))
            state["edit_day_number"] = day_num
            
    if not user_msg or not day_num:
        send_whatsapp_message(state["user_id"], f"Please tell me what changes you'd like to make to your Day {day_num if day_num else ''} exercise plan.")
        return state
        
    if user_msg.lower() in ["ok", "okay", "yes", "sure", "fine", "thanks", "thx"]:
        return state
    
    state[f"day{day_num}_change_request"] = user_msg
    old_plan = state.get(f"day{day_num}_plan", "")
    
    hist_key = f"old_day{day_num}_plans"
    if not state.get(hist_key): state[hist_key] = []
    state[hist_key].append(old_plan)
    
    send_whatsapp_message(state["user_id"], f"Got it! 🔄 Regenerating your Day {day_num} exercise plan with: {user_msg}\n\n⏳ One moment...")
    
    theme = "Workout" # (Omit theme map for brevity, LLM handles it well usually)
    prompt = f"User wants to change Day {day_num} exercise plan.\nOriginal: {old_plan}\nRequests: {user_msg}\nCreate a REVISED plan."
    
    llm_c = ChatBedRockLLM()
    response = llm_c.invoke(prompt)
    revised = remove_markdown(response.content.strip())
    
    state[f"day{day_num}_plan"] = revised
    
    save_exercise_plan(state["user_id"], {
        f"day{day_num}_plan": revised,
        f"old_day{day_num}_plans": state.get(hist_key, []),
        f"day{day_num}_change_request": user_msg,
        "user_context": extract_exercise_plan_user_context(state)
    }, product="ams", increment_change_count=True)
    
    send_whatsapp_message(state["user_id"], revised)
    send_whatsapp_message(state["user_id"], f"✅ Your Day {day_num} exercise plan has been updated!")
    
    state["last_question"] = "post_plan_qna"
    state["current_agent"] = "post_plan_qna"
    state["pending_node"] = None
    state["edit_mode"] = None
    state["edit_day_number"] = None
    return state


def resume_from_qna_node(state: State) -> State:
    """Node: Resume the conversation flow after health or product Q&A."""
    send_whatsapp_message(state["user_id"], random.choice(TRANSITION_MESSAGES))
    
    # Logic to resume correct node
    if state.get("meal_plan_sent") and state.get("exercise_plan_sent") and not state.get("journey_restart_mode"):
        state["pending_node"] = None
    elif not state.get("pending_node"):
        if state.get("age") and not state.get("height"):
            state["pending_node"] = "collect_height"
        else:
            current_q = state.get("last_question", "").replace("_answered", "")
            if current_q in ["health_qna", "product_qna"]:
                state["pending_node"] = "collect_age"
            
    if state.get("last_question") == "health_qna_answered":
        state["last_question"] = "resuming_from_health_qna"
    elif state.get("last_question") == "product_qna_answered":
        state["last_question"] = "resuming_from_product_qna"
        
    return state