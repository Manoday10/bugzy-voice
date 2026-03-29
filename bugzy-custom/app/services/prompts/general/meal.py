"""
Meal Plan Generation Module

This module handles all meal plan generation functionality including:
- Individual day meal plan generation
- Complete 7-day meal plan generation
- Meal plan splitting utilities
"""

import time
import re
import logging
from typing import Dict

from app.services.llm.bedrock_llm import ChatBedRockLLM

logger = logging.getLogger(__name__)
from app.services.prompts.general.meal_plan_template import (
    build_meal_plan_prompt,
    build_disclaimers,
    get_day_themes,
    _remove_llm_disclaimers,
    _extract_meals_from_plan,
)
from app.services.whatsapp.messages import remove_markdown
from app.services.whatsapp.client import send_whatsapp_message

# Initialize LLM
llm = ChatBedRockLLM()


def generate_meal_plan_tool(state: dict) -> str:
    """
    Generate a personalized meal plan for Day 1.
    Uses the unified template for consistent formatting.
    """
    # Build the prompt using unified template
    prompt = build_meal_plan_prompt(
        state=state,
        day_number=1,
        previous_meals=None,
        day1_plan=None,
        change_request=None,
        is_revision=False
    )
    
    # Generate using LLM
    response = llm.invoke(prompt)
    plan_text = response.content.strip()
    
    # Clean up any accidental disclaimers from LLM (we add our own)
    plan_text = _remove_llm_disclaimers(plan_text)
    
    # Add our standardized disclaimers
    disclaimers = build_disclaimers(state)
    if disclaimers:
        plan_text = plan_text.rstrip() + disclaimers
    
    # Remove markdown formatting for WhatsApp
    final_plan = remove_markdown(plan_text)
    
    # Store Day 1 plan in state for reference by Days 2-7
    state["meal_day1_plan"] = final_plan
    
    return final_plan


def generate_day_meal_plan(state: dict, day_number: int, previous_meals: dict = None) -> str:
    """
    Generate a personalized meal plan for a specific day (1-7).
    Uses the unified template for consistent formatting.
    
    Args:
        state: User state dictionary
        day_number: Which day to generate (1-7)
        previous_meals: Dict tracking meals from previous days for variety
    
    Returns:
        Formatted meal plan string
    """
    # Initialize previous_meals if not provided
    if previous_meals is None:
        previous_meals = {
            'breakfasts': [],
            'lunches': [],
            'dinners': [],
            'snacks': []
        }
    
    # For Day 1, use the dedicated function
    if day_number == 1:
        return generate_meal_plan_tool(state)
    
    # Get Day 1 plan for structural reference
    day1_plan = state.get('meal_day1_plan', '')
    
    # If Day 1 doesn't exist, we need to generate it first
    if not day1_plan:
        logger.info("⚠️ Day 1 plan not found. Generating Day 1 first...")
        day1_plan = generate_meal_plan_tool(state)
        _extract_meals_from_plan(day1_plan, previous_meals)
    
    # Build the prompt using unified template
    prompt = build_meal_plan_prompt(
        state=state,
        day_number=day_number,
        previous_meals=previous_meals,
        day1_plan=day1_plan,
        change_request=None,
        is_revision=False
    )
    
    # Generate using LLM
    response = llm.invoke(prompt)
    plan_text = response.content.strip()
    
    # Clean up any accidental disclaimers from LLM
    plan_text = _remove_llm_disclaimers(plan_text)
    
    # Add our standardized disclaimers
    disclaimers = build_disclaimers(state)
    if disclaimers:
        plan_text = plan_text.rstrip() + disclaimers
    
    # Remove markdown formatting for WhatsApp
    final_plan = remove_markdown(plan_text)
    
    # Extract meals for variety tracking
    _extract_meals_from_plan(final_plan, previous_meals)
    
    return final_plan


def generate_complete_7day_meal_plan(state: dict) -> dict:
    """
    Generate a complete 7-day meal plan (Days 2-7, assuming Day 1 exists).
    Uses the unified template for consistent formatting across all days.
    
    Returns:
        Dictionary with keys: 'meal_day2', 'meal_day3', ..., 'meal_day7', 'disclaimers'
    """
    # Get Day 1 plan for context and structural reference
    day1_plan = state.get('meal_day1_plan', '')
    
    # If Day 1 doesn't exist, generate it first
    if not day1_plan:
        logger.info("⚠️ Day 1 plan not found. Generating Day 1 first...")
        day1_plan = generate_meal_plan_tool(state)
    
    # Track meals for variety
    previous_meals = {
        'breakfasts': [],
        'lunches': [],
        'dinners': [],
        'snacks': []
    }
    
    # Extract meals from Day 1
    _extract_meals_from_plan(day1_plan, previous_meals)
    
    # Extract user's change request if it exists (to maintain consistency across all days)
    user_change_request = state.get('meal_day1_change_request', None)
    
    # Store generated plans
    individual_days = {}
    
    # Generate Days 2-7
    for day_num in range(2, 8):
        try:
            logger.info("🔄 Generating Day %s meal plan...", day_num)
            
            # Build prompt using unified template with Day 1 reference AND user's change request
            prompt = build_meal_plan_prompt(
                state=state,
                day_number=day_num,
                previous_meals=previous_meals,
                day1_plan=day1_plan,
                change_request=user_change_request,  # Pass the change request to maintain consistency
                is_revision=False
            )
            
            # Generate using LLM
            response = llm.invoke(prompt)
            plan_text = response.content.strip()
            
            # Clean up any accidental disclaimers from LLM
            plan_text = _remove_llm_disclaimers(plan_text)
            
            # Remove markdown for WhatsApp
            cleaned_plan = remove_markdown(plan_text)
            
            # Extract meals from this day for next iteration
            _extract_meals_from_plan(cleaned_plan, previous_meals)
            
            # Store the plan (WITHOUT disclaimers - added once at end)
            individual_days[f'meal_day{day_num}'] = cleaned_plan
            
            logger.info("✅ Generated Day %s meal plan", day_num)
            logger.info("   Tracked meals so far: %s breakfasts, %s lunches, %s dinners",
                        len(previous_meals['breakfasts']), len(previous_meals['lunches']), len(previous_meals['dinners']))
            
        except Exception as e:
            logger.error("⚠️ Error generating Day %s meal plan: %s", day_num, e)
            themes = get_day_themes()
            fallback_msg = (
                f"*Day {day_num}: {themes.get(day_num, 'Meal Plan')}* 🍽️\n\n"
                f"⚠️ Unable to generate plan for this day. Please try again."
            )
            individual_days[f'meal_day{day_num}'] = fallback_msg
    
    # Add disclaimers as separate entry (sent once at the end)
    disclaimers = build_disclaimers(state)
    if disclaimers:
        individual_days['disclaimers'] = disclaimers.strip()
    
    return individual_days


def split_7day_meal_plan(complete_plan: str, user_id: str = None, state: dict = None) -> dict:
    """
    Split the generated 7-day meal plan (Days 2-7) into individual day plans.
    
    Returns a dictionary with keys: 'day2', 'day3', 'day4', 'day5', 'day6', 'day7'
    """
    days = {}
    
    # Extract disclaimers from the end of the complete plan (if present)
    disclaimer_patterns = [
        r'⚠️\s*\*Health Condition Notice:.*?(?=\n\n💊|\n\n🌿|$)',
        r'💊\s*\*Supplement Disclaimer:.*?(?=\n\n🌿|$)',
        r'🌿\s*\*Gut Health Note:.*?(?=$)'
    ]
    
    disclaimers = []
    for pattern in disclaimer_patterns:
        match = re.search(pattern, complete_plan, re.DOTALL)
        if match:
            disclaimers.append(match.group(0).strip())
    
    # Remove disclaimers from the complete plan before splitting
    plan_without_disclaimers = complete_plan
    for disclaimer in disclaimers:
        plan_without_disclaimers = plan_without_disclaimers.replace(disclaimer, '')
    plan_without_disclaimers = plan_without_disclaimers.strip()
    
    # More robust pattern to match various day formats
    day_pattern = r'[\*]*Day\s*(\d)[\:\*]'
    
    # Find all day markers
    day_matches = list(re.finditer(day_pattern, plan_without_disclaimers, re.IGNORECASE))
    
    if not day_matches:
        # Fallback: try splitting by "---" separator
        parts = plan_without_disclaimers.split('---')
        if len(parts) >= 6:
            for i, part in enumerate(parts[:6], start=2):
                days[f'day{i}'] = part.strip()
        else:
            # If can't split, return the whole plan for each day
            logger.warning("⚠️ Warning: Could not split meal plan by days. Using full plan for all days.")
            for day_num in range(2, 8):
                days[f'day{day_num}'] = plan_without_disclaimers
        return days
    
    # Extract content for each day
    for i, match in enumerate(day_matches):
        day_num = int(match.group(1))
        start_pos = match.start()
        
        # Find the end position (start of next day or end of string)
        if i < len(day_matches) - 1:
            end_pos = day_matches[i + 1].start()
        else:
            end_pos = len(plan_without_disclaimers)
        
        # Extract the day content
        day_content = plan_without_disclaimers[start_pos:end_pos].strip()
        
        # Remove trailing separator if present
        if day_content.endswith('---'):
            day_content = day_content[:-3].strip()
        
        # Add disclaimers to each individual day
        if disclaimers:
            day_content = day_content + "\n\n" + "\n\n".join(disclaimers)
        
        days[f'day{day_num}'] = day_content
    
    # Fill in any missing days with a message
    for day_num in range(2, 8):
        if f'day{day_num}' not in days:
            days[f'day{day_num}'] = f"Day {day_num} plan not found in generated content."
            logger.warning("⚠️ Warning: Day %s meal plan not found in split.", day_num)
    
    # If user_id provided, send each day as a single message (no further splitting)
    if user_id:
        for day_num in range(2, 8):
            day_key = f'day{day_num}'
            day_text = days.get(day_key, f"Day {day_num} plan not found in generated content.")
            send_whatsapp_message(user_id, day_text)
            time.sleep(0.5)
    
    return days