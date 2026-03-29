import re
from datetime import datetime, time, timedelta

"""
Unified Meal Plan Template Module
All meal plan generation functions should use this template to ensure consistent formatting.
"""

# The exact template format that MUST be followed for every day
MEAL_PLAN_TEMPLATE = """
*Day {day_number}: {day_theme}* 🍽️

🌅 *BREAKFAST ({breakfast_timing}):*
{breakfast_content}

{mid_morning_snack_section}

🌤️ *LUNCH ({lunch_timing}):*
{lunch_content}

{evening_snack_section}

🌙 *DINNER ({dinner_timing}):*
{dinner_content}

💧 *HYDRATION:*
{hydration_content}

{supplement_section}

{gut_health_section}

💚 *TODAY'S TIP:*
{daily_tip}
"""

# Snack section templates (only include when gaps > 5-6 hours)
MID_MORNING_SNACK_TEMPLATE = """🍎 *MID-MORNING SNACK (10:00-11:00 AM):*
{snack_content}
"""

EVENING_SNACK_TEMPLATE = """🥜 *EVENING SNACK (4:00-5:00 PM):*
{snack_content}
"""

# Supplement section template
SUPPLEMENT_SECTION_TEMPLATE = """💊 *SUPPLEMENT SCHEDULE:*
{supplement_content}
"""

# Gut health section template
GUT_HEALTH_SECTION_TEMPLATE = """🌿 *GUT HEALTH BOOST:*
{gut_health_content}
"""


def parse_time_string(time_str: str) -> time:
    """
    Parse various time string formats to datetime.time object.
    Handles formats like: "7:00 AM", "7 AM", "7:00", "morning", etc.
    """
    time_str = str(time_str).strip().upper()
    
    # Handle general terms
    general_times = {
        'MORNING': time(8, 0),
        'EARLY MORNING': time(7, 0),
        'AFTERNOON': time(13, 0),
        'EVENING': time(19, 0),
        'NIGHT': time(20, 0),
        'LATE EVENING': time(21, 0)
    }
    
    if time_str in general_times:
        return general_times[time_str]
    
    # Try to parse time formats
    patterns = [
        r'(\d{1,2}):(\d{2})\s*(AM|PM)',
        r'(\d{1,2})\s*(AM|PM)',
        r'(\d{1,2}):(\d{2})',
        r'(\d{1,2})'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, time_str)
        if match:
            try:
                groups = match.groups()
                hour = int(groups[0])
                minute = int(groups[1]) if len(groups) > 1 and groups[1] and groups[1].isdigit() else 0
                
                # Handle AM/PM
                if len(groups) >= 2 and groups[-1] in ['AM', 'PM']:
                    if groups[-1] == 'PM' and hour < 12:
                        hour += 12
                    elif groups[-1] == 'AM' and hour == 12:
                        hour = 0
                
                # Handle special case 24:00 -> 00:00
                if hour == 24 and minute == 0:
                    hour = 0
                
                return time(hour, minute)
            except ValueError:
                continue
    
    # Default fallback
    return time(8, 0)


def calculate_time_gap_hours(time1: time, time2: time) -> float:
    """Calculate the gap in hours between two times."""
    dt1 = datetime.combine(datetime.today(), time1)
    dt2 = datetime.combine(datetime.today(), time2)
    
    # Handle times crossing midnight
    if dt2 < dt1:
        dt2 += timedelta(days=1)
    
    delta = dt2 - dt1
    return delta.total_seconds() / 3600


def should_include_snacks(state: dict) -> dict:
    """
    Determine whether to include mid-morning and evening snacks based on meal timings.
    Returns dict with 'mid_morning_snack' and 'evening_snack' boolean flags.
    """
    meal_timings = state.get('meal_timings', {})
    
    breakfast_str = meal_timings.get('breakfast', 'morning')
    lunch_str = meal_timings.get('lunch', 'afternoon')
    dinner_str = meal_timings.get('dinner', 'evening')
    
    breakfast_time = parse_time_string(breakfast_str)
    lunch_time = parse_time_string(lunch_str)
    dinner_time = parse_time_string(dinner_str)
    
    breakfast_lunch_gap = calculate_time_gap_hours(breakfast_time, lunch_time)
    lunch_dinner_gap = calculate_time_gap_hours(lunch_time, dinner_time)
    
    return {
        'mid_morning_snack': breakfast_lunch_gap >= 5,
        'evening_snack': lunch_dinner_gap >= 5,
        'breakfast_lunch_gap': breakfast_lunch_gap,
        'lunch_dinner_gap': lunch_dinner_gap
    }


def get_exact_format_instructions():
    """
    Returns the exact format instructions that MUST be included in every meal plan prompt.
    This ensures consistent output across all days.
    """
    return """
═══════════════════════════════════════════════════════════════
📋 MANDATORY OUTPUT FORMAT - FOLLOW THIS EXACTLY
═══════════════════════════════════════════════════════════════

You MUST output the meal plan in THIS EXACT FORMAT. Do not deviate.
Use asterisks (*) for bold headers. Do not use markdown (**).

---BEGIN EXACT TEMPLATE---

*Day {N}: {Theme}* 🍽️

🌅 *BREAKFAST ({timing}):*
[Meal name with portions]
- [Detail 1]
- [Detail 2 if needed]

🍎 *MID-MORNING SNACK (10:00-11:00 AM):*  ← ONLY if breakfast-lunch gap > 5-6 hours
[Snack with portions]
- [Detail]

🌤️ *LUNCH ({timing}):*
[Meal name with portions]
- [Detail 1]
- [Detail 2 if needed]

🥜 *EVENING SNACK (4:00-5:00 PM):*  ← ONLY if lunch-dinner gap > 5-6 hours
[Snack with portions]
- [Detail]

🌙 *DINNER ({timing}):*
[Meal name with portions]
- [Detail 1]
- [Detail 2 if needed]

💧 *HYDRATION:*
[Water and beverage recommendations]

💊 *SUPPLEMENT SCHEDULE:*  ← ONLY if user takes supplements
• ⏰ [Supplement]: [timing]
  🎯 Why: [reason]
  🍽️ With: [food pairing]
  ⚠️ Avoid: [foods to avoid]

🌿 *GUT HEALTH BOOST:*  ← ONLY if user has gut issues
[1-2 gut health tips]

💚 *TODAY'S TIP:*
[1-2 actionable tips for the day]

---END EXACT TEMPLATE---

CRITICAL FORMATTING RULES:
1. Use *asterisks* for headers (not **double asterisks**)
2. Each section header MUST have the emoji BEFORE the asterisk
3. Timings go in parentheses after the meal type
4. Use bullet points (-) for meal details, not numbered lists
5. Keep consistent spacing - one blank line between sections
6. Do NOT add any "⚠️ THIS SECTION IS MANDATORY" warnings in output
7. Do NOT add disclaimers in the output (they are added separately)
"""


def get_day_themes():
    """Returns themed names for each day to add variety."""
    return {
        1: "Fresh Start",
        2: "Gentle Healing",
        3: "Energy & Balance",
        4: "Nourishment Focus",
        5: "Strength & Recovery",
        6: "Harmony & Renewal",
        7: "Complete Wellness"
    }


def build_user_profile_context(state: dict) -> str:
    """
    Builds the user profile context string from state.
    This ensures consistent profile formatting across all functions.
    """
    return f"""
USER PROFILE:
• Name: {state.get('user_name', 'Friend')}
• Age: {state.get('age', 'not provided')}, BMI: {state.get('bmi', 'not calculated')}
• Health conditions: {state.get('health_conditions', 'None')}
• Current medications: {state.get('medications', 'None')}
• Current meals: Breakfast: {state.get('current_breakfast', 'Not provided')}, Lunch: {state.get('current_lunch', 'Not provided')}, Dinner: {state.get('current_dinner', 'Not provided')}
• Meal timings: Breakfast at {state.get('meal_timings', {}).get('breakfast', 'morning')}, Lunch at {state.get('meal_timings', {}).get('lunch', 'afternoon')}, Dinner at {state.get('meal_timings', {}).get('dinner', 'evening')}
• Diet preference: {state.get('diet_preference', 'Not provided')}
• Cuisine preference: {state.get('cuisine_preference', 'Not provided')}
• Allergies/intolerances: {state.get('allergies', 'None')}
• Water intake: {state.get('water_intake', 'Not provided')}
• Beverages: {state.get('beverages', 'Not provided')}
• Lifestyle: {state.get('lifestyle', 'Not provided')}
• Activity level: {state.get('activity_level', 'Not provided')}
• Sleep/stress: {state.get('sleep_stress', 'Not provided')}
• Supplements: {state.get('supplements', 'None')}
• Gut health: {state.get('gut_health', 'No issues reported')}
• Goals: {state.get('meal_goals', 'Not provided')}
"""


def get_timing_guidelines() -> str:
    """Returns the meal timing guidelines section."""
    return """
MEAL TIMING GUIDELINES:
• Healthy breakfast: 6:00 AM – 10:00 AM (optimal: 7–9 AM)
• Healthy lunch: 12:00 PM – 3:00 PM (optimal: 12–2 PM)
• Healthy dinner: 6:00 PM – 9:00 PM (optimal: 6–8 PM)
• Avoid eating 2–3 hours before bedtime

TIMING ADJUSTMENT RULES:
If any user timing is unhealthy (e.g., 2 AM dinner), adjust to healthy range.
Show the ADJUSTED timing in your output.

SNACK INCLUSION RULES:
• Breakfast-lunch gap > 5-6 hours → Include MID-MORNING SNACK section
• Lunch-dinner gap > 5-6 hours → Include EVENING SNACK section
• Lunch-dinner gap > 7 hours → Include MORE SUBSTANTIAL evening snack
"""


def get_gut_health_instructions(gut_health: str, has_gut_issues: bool) -> str:
    """Returns gut health specific instructions if applicable."""
    if not has_gut_issues:
        return ""
    
    return f"""
🔴 GUT HEALTH REQUIREMENTS (User reported: {gut_health}):

EVERY MEAL MUST INCLUDE:
- At least ONE probiotic food (yogurt, kefir, buttermilk, curd, fermented foods)
- At least ONE prebiotic food (bananas, oats, garlic, onions, whole grains)
- Anti-inflammatory ingredients (turmeric, ginger, green leafy vegetables)

AVOID THESE GUT IRRITANTS:
- Raw vegetables (use COOKED only)
- Brown rice (use white rice or well-cooked options)
- Heavy, fried, or processed foods
- Excessive spices or chilies
- Raw salads

FOR SNACKS: Use gut-friendly options like curd with fruit, banana with almond butter, probiotic smoothies

YOU MUST INCLUDE the "🌿 *GUT HEALTH BOOST:*" section in your output.
"""


def get_supplement_instructions(supplements: str, has_supplements: bool) -> str:
    """Returns supplement specific instructions if applicable."""
    if not has_supplements:
        return ""
    
    return f"""
💊 SUPPLEMENT REQUIREMENTS (User takes: {supplements}):

YOU MUST INCLUDE the "💊 *SUPPLEMENT SCHEDULE:*" section in your output.

For EACH supplement, specify:
• ⏰ Best time to take
• 🎯 Why that timing
• 🍽️ Food pairings for absorption
• ⚠️ Foods to avoid nearby

Common timing guidelines:
- Multivitamins: With breakfast
- Vitamin D: With largest meal (healthy fats)
- Iron: Empty stomach or with vitamin C, avoid tea/coffee
- Probiotics: Before breakfast or bedtime (empty stomach)
- Omega-3: With meals
- B-Complex: Morning with breakfast
- Magnesium: Evening
"""


def get_day1_structure_instructions(day1_plan: str, snack_analysis: dict) -> str:
    """
    Returns instructions to follow Day 1's structure strictly for Days 2-7.
    """
    if not day1_plan:
        return ""
    
    mid_morning_included = "MID-MORNING SNACK" in day1_plan
    evening_included = "EVENING SNACK" in day1_plan
    
    return f"""
═══════════════════════════════════════════════════════════════
🔴 CRITICAL: FOLLOW DAY 1 STRUCTURE EXACTLY
═══════════════════════════════════════════════════════════════

DAY 1 HAD THE FOLLOWING STRUCTURE - YOU MUST MATCH IT:

✓ Breakfast section: YES
✓ Mid-morning snack: {'YES - MUST INCLUDE' if mid_morning_included else 'NO - DO NOT INCLUDE'}
✓ Lunch section: YES
✓ Evening snack: {'YES - MUST INCLUDE' if evening_included else 'NO - DO NOT INCLUDE'}
✓ Dinner section: YES
✓ Hydration section: YES
✓ Gut Health Boost section: {'YES' if 'GUT HEALTH BOOST' in day1_plan else 'NO'}
✓ Supplement Schedule: {'YES' if 'SUPPLEMENT SCHEDULE' in day1_plan else 'NO'}
✓ Today's Tip: YES

SNACK ANALYSIS:
- Breakfast-lunch gap: {snack_analysis.get('breakfast_lunch_gap', 0):.1f} hours
- Lunch-dinner gap: {snack_analysis.get('lunch_dinner_gap', 0):.1f} hours
- Mid-morning snack required: {'YES' if snack_analysis.get('mid_morning_snack') else 'NO'}
- Evening snack required: {'YES' if snack_analysis.get('evening_snack') else 'NO'}

🚨 MANDATORY REQUIREMENTS:
1. If Day 1 had mid-morning snack → ALL days 2-7 MUST have it
2. If Day 1 had evening snack → ALL days 2-7 MUST have it
3. Use SAME level of detail as Day 1 (ingredient specifics, portions, preparation notes)
4. Match Day 1's formatting style exactly (bullet points, spacing, emoji placement)
5. Keep meal descriptions as detailed as Day 1

REFERENCE DAY 1 PLAN STRUCTURE:
{day1_plan[:500]}...
[Use this as your structural template]
"""


def build_meal_plan_prompt(
    state: dict,
    day_number: int,
    previous_meals: dict = None,
    day1_plan: str = None,
    change_request: str = None,
    is_revision: bool = False
) -> str:
    """
    Builds a complete, consistent prompt for meal plan generation.
    
    Args:
        state: User state dictionary
        day_number: Which day (1-7)
        previous_meals: Dict tracking previous days' meals for variety
        day1_plan: Day 1 plan text (for Days 2-7 reference)
        change_request: User's change request (for revisions)
        is_revision: Whether this is a revision of an existing plan
    
    Returns:
        Complete prompt string
    """
    # Detect conditions
    health_conditions = (state.get('health_conditions') or 'None').strip().lower()
    has_health_issues = health_conditions not in ['none', 'nil', 'no', 'nothing', '']
    
    supplements = (state.get('supplements') or 'None').strip()
    has_supplements = supplements.lower() not in ['none', 'nil', 'no', 'nothing', '']
    
    gut_health = (state.get('gut_health') or 'No issues reported').strip().lower()
    has_gut_issues = gut_health not in ['no issues reported', 'none', 'nil', 'no', 'nothing', 'good', 'healthy', '']
    
    # Analyze snack requirements
    snack_analysis = should_include_snacks(state)
    
    # Get day theme
    themes = get_day_themes()
    day_theme = themes.get(day_number, "Wellness Day")
    
    # Build the prompt
    prompt_parts = []
    
    # Role
    prompt_parts.append("""
You are Bugzy (Gut Intelligent Assistant), a supportive nutrition coach.
Your task is to create a meal plan that EXACTLY follows the template format below.
""")
    
    # Revision context if applicable
    if is_revision and change_request:
        prompt_parts.append(f"""
REVISION REQUEST:
The user wants changes to their Day {day_number} plan.
User's requested changes: {change_request}

Please incorporate these changes while maintaining the exact format.
""")
    elif change_request and not is_revision:
        # For Days 2-7: Include user's Day 1 change request to maintain consistency
        prompt_parts.append(f"""
USER'S DAY 1 FEEDBACK (Apply to all subsequent days):
The user made the following request when reviewing Day 1:
"{change_request}"

Please ensure ALL days respect this feedback and maintain consistency.
""")
    
    # User profile
    prompt_parts.append(build_user_profile_context(state))
    
    # User's meal timings
    prompt_parts.append(f"""
USER'S PROVIDED TIMINGS:
- Breakfast: {state.get('meal_timings', {}).get('breakfast', 'morning')}
- Lunch: {state.get('meal_timings', {}).get('lunch', 'afternoon')}
- Dinner: {state.get('meal_timings', {}).get('dinner', 'evening')}
""")
    
    # Timing guidelines
    prompt_parts.append(get_timing_guidelines())
    
    # Gut health instructions
    prompt_parts.append(get_gut_health_instructions(gut_health, has_gut_issues))
    
    # Supplement instructions
    prompt_parts.append(get_supplement_instructions(supplements, has_supplements))
    
    # Day 1 structure instructions (for Days 2-7)
    if day_number > 1 and day1_plan:
        prompt_parts.append(get_day1_structure_instructions(day1_plan, snack_analysis))
    
    # Variety requirement for Days 2-7
    if day_number > 1 and previous_meals:
        prompt_parts.append(f"""
VARIETY REQUIREMENT - DO NOT REPEAT THESE MEALS:
- Previous breakfasts: {', '.join(previous_meals.get('breakfasts', [])) or 'None yet'}
- Previous lunches: {', '.join(previous_meals.get('lunches', [])) or 'None yet'}
- Previous dinners: {', '.join(previous_meals.get('dinners', [])) or 'None yet'}

Create COMPLETELY DIFFERENT meals for Day {day_number}.
""")
    
    # THE EXACT FORMAT INSTRUCTIONS (MOST IMPORTANT)
    prompt_parts.append(get_exact_format_instructions())
    
    # Explicit snack inclusion instructions
    if snack_analysis.get('mid_morning_snack') or snack_analysis.get('evening_snack'):
        snack_requirements = []
        if snack_analysis.get('mid_morning_snack'):
            snack_requirements.append("🍎 *MID-MORNING SNACK (10:00-11:00 AM):* section")
        if snack_analysis.get('evening_snack'):
            snack_requirements.append("🥜 *EVENING SNACK (4:00-5:00 PM):* section")
        
        prompt_parts.append(f"""
🔴 SNACK SECTIONS REQUIRED:
Based on meal timing gaps, you MUST include:
{chr(10).join('- ' + req for req in snack_requirements)}

These are NOT optional. The meal gaps require these snacks.
""")
    
    # Final generation instruction
    required_sections = []
    if snack_analysis.get('mid_morning_snack'):
        required_sections.append("🍎 *MID-MORNING SNACK*")
    if snack_analysis.get('evening_snack'):
        required_sections.append("🥜 *EVENING SNACK*")
    if has_supplements:
        required_sections.append("💊 *SUPPLEMENT SCHEDULE*")
    if has_gut_issues:
        required_sections.append("🌿 *GUT HEALTH BOOST*")
    
    required_text = ", ".join(required_sections) if required_sections else "all standard sections"
    
    prompt_parts.append(f"""
═══════════════════════════════════════════════════════════════
NOW GENERATE Day {day_number}: {day_theme}
═══════════════════════════════════════════════════════════════

CHECKLIST BEFORE OUTPUTTING:
✓ Format matches template EXACTLY
✓ Using *asterisks* not **double asterisks**
✓ Emojis are BEFORE the asterisks (e.g., 🌅 *BREAKFAST*)
✓ Timings in parentheses
✓ Required sections included: {required_text}
✓ No disclaimers in output
✓ No "MANDATORY" warnings in output
✓ Warm, supportive tone
✓ Same detail level as Day 1 (if Day 2-7)

Generate the complete meal plan for *Day {day_number}: {day_theme}* now:
""")
    
    return "\n".join(prompt_parts)


def build_disclaimers(state: dict) -> str:
    """
    Builds the disclaimer text to be appended AFTER the meal plan.
    This is separate from the plan itself.
    """
    health_conditions = (state.get('health_conditions') or 'None').strip().lower()
    has_health_issues = health_conditions not in ['none', 'nil', 'no', 'nothing', '']
    
    supplements = (state.get('supplements') or 'None').strip()
    has_supplements = supplements.lower() not in ['none', 'nil', 'no', 'nothing', '']
    
    gut_health = (state.get('gut_health') or 'No issues reported').strip().lower()
    has_gut_issues = gut_health not in ['no issues reported', 'none', 'nil', 'no', 'nothing', 'good', 'healthy', '']
    
    disclaimers = []
    
    if has_health_issues:
        disclaimers.append(
            f"⚠️ *Health Condition Notice:* Since you mentioned *{health_conditions}*, "
            f"this meal plan is for informational purposes only. Please consult your healthcare provider "
            f"or a registered dietitian before making any dietary changes."
        )
    
    if has_supplements:
        disclaimers.append(
            f"💊 *Supplement Disclaimer:* The supplement timing suggestions are general guidelines. "
            f"Always follow your healthcare provider's specific instructions for your supplements, "
            f"especially if you're taking medications."
        )
    
    if has_gut_issues:
        disclaimers.append(
            f"🌿 *Gut Health Note:* While this plan includes gut-friendly recommendations, "
            f"if you have persistent digestive issues, please consult a gastroenterologist "
            f"or registered dietitian for personalized care."
        )
    
    if disclaimers:
        return "\n\n" + "\n\n".join(disclaimers)
    return ""


# ═══════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def _remove_llm_disclaimers(plan_text: str) -> str:
    """
    Remove any disclaimers and template markers that the LLM might have generated.
    We add our own standardized disclaimers separately.
    """
    # First, remove template markers that should not appear in output
    template_markers = [
        r'---BEGIN EXACT TEMPLATE---\s*',
        r'\s*---END EXACT TEMPLATE---',
        r'═══════════════════════════════════════════════════════════════\s*',
        r'📋 MANDATORY OUTPUT FORMAT - FOLLOW THIS EXACTLY\s*',
        r'CRITICAL FORMATTING RULES:.*?(?=\*Day|\Z)',
        r'CHECKLIST BEFORE OUTPUTTING:.*?(?=\*Day|\Z)',
        r'🔴 CRITICAL:.*?(?=\*Day|\Z)',
        r'SNACK ANALYSIS:.*?(?=\*Day|\Z)',
    ]
    
    for pattern in template_markers:
        plan_text = re.sub(pattern, '', plan_text, flags=re.DOTALL | re.IGNORECASE)
    
    # Patterns that match ONLY disclaimer sections (not content sections)
    disclaimer_patterns = [
        # Health Condition Notice disclaimers
        r'⚠️\s*\*?Health Condition Notice\*?:.*?(?=\n\n[⚠️💊🌿]|\n\n---|\Z)',
        # Supplement Disclaimer (NOT Supplement Schedule)
        r'💊\s*\*?Supplement Disclaimer\*?:.*?(?=\n\n[⚠️💊🌿]|\n\n---|\Z)',
        # Gut Health Note (NOT Gut Health Boost)
        r'🌿\s*\*?Gut Health Note\*?:.*?(?=\n\n[⚠️💊🌿]|\n\n---|\Z)',
    ]
    
    for pattern in disclaimer_patterns:
        plan_text = re.sub(pattern, '', plan_text, flags=re.DOTALL | re.IGNORECASE)
    
    return plan_text.strip()


def _extract_meals_from_plan(plan_text: str, previous_meals: dict) -> None:
    """
    Extract meal names from a plan to track for variety in subsequent days.
    Updates the previous_meals dict in place.
    """
    # Patterns to extract meal names
    patterns = {
        'breakfasts': r'BREAKFAST[^)]*\):\s*\*?\s*\n\s*([^\n-*]+)',
        'lunches': r'LUNCH[^)]*\):\s*\*?\s*\n\s*([^\n-*]+)',
        'dinners': r'DINNER[^)]*\):\s*\*?\s*\n\s*([^\n-*]+)',
    }
    
    for meal_type, pattern in patterns.items():
        match = re.search(pattern, plan_text, re.IGNORECASE)
        if match:
            meal_name = match.group(1).strip()
            # Clean up the meal name
            meal_name = meal_name.split('(')[0].strip()  # Remove portion info
            meal_name = meal_name.split(':')[0].strip()  # Remove any trailing info
            if meal_name and len(meal_name) > 3:  # Avoid empty or too short matches
                previous_meals[meal_type].append(meal_name)