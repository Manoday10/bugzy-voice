"""
Exercise Plan Generation Module

This module handles all exercise plan generation functionality including:
- Individual day exercise plan generation
- Complete 7-day exercise plan generation
- Exercise plan splitting utilities
"""

import time
import re
import logging
from typing import Dict, TYPE_CHECKING

from app.services.llm.bedrock_llm import ChatBedRockLLM

logger = logging.getLogger(__name__)
from app.services.whatsapp.messages import remove_markdown
from app.services.whatsapp.client import send_whatsapp_message
from app.services.media.video import search_exercise_videos, format_video_references

# Import State type for type hinting
if TYPE_CHECKING:
    from app.services.chatbot.bugzy_general.state import State
else:
    State = "State"

# Initialize LLM
llm = ChatBedRockLLM()


def generate_day_exercise_plan(state: State, day_number: int, focus: str, change_request: str = None) -> str:
    """Generate a single day exercise plan using LLM."""
    
    # Get Day 1 plan for structural reference if available
    day1_plan = state.get('day1_plan', '')
    
    # Create a specific prompt for this day
    # Extract the actual duration value from the user's session_duration
    session_duration = state.get('session_duration', '30 mins')
    
    prompt = f"""
You are a certified fitness coach creating a personalized exercise plan for Day {day_number}.

USER PROFILE:
- Name: {state.get('user_name', 'Friend')}
- Fitness Level: {state.get('fitness_level', 'Beginner')}
- Recent Activities: {state.get('activity_types', 'None')}
- Exercise Frequency: {state.get('exercise_frequency', '0 days')}
- Intensity Preference: {state.get('exercise_intensity', 'Moderate')}
- Session Duration: {session_duration}
- Sedentary Time: {state.get('sedentary_time', 'Moderate')}
- Primary Goals: {state.get('exercise_goals', 'General Wellness')}


DAY {day_number} FOCUS: {focus}

CRITICAL REQUIREMENTS:
1. The TOTAL workout duration MUST match the user's session duration: {session_duration}
2. Design the workout to fill the ENTIRE duration specified by the user
3. If the user specified 90+ minutes, create a comprehensive workout with more exercises, sets, and rest periods
4. Adjust the number of exercises, sets, reps, and rest periods to match the total duration

INSTRUCTIONS:
1. Create a detailed workout for Day {day_number} ONLY.
2. Structure it exactly like this:

**Day {day_number}: {focus}** 🏋️

**Duration:** {session_duration}
**Intensity:** {state.get('exercise_intensity', 'Moderate')}

**WARM-UP (proportional to total duration):**
- [Exercise 1]: [Reps/Time]
- [Exercise 2]: [Reps/Time]

**MAIN WORKOUT:**
A. [Exercise Name]
   - Sets: [X] | Reps: [X]
   - Form: [Brief tip]

B. [Exercise Name]
   - Sets: [X] | Reps: [X]
   - Form: [Brief tip]

C. [Exercise Name]
   - Sets: [X] | Reps: [X]
   - Form: [Brief tip]

[Add more exercises if duration is longer - scale the workout to match {session_duration}]

**COOL-DOWN (proportional to total duration):**
- [Stretch 1]: [Time]
- [Stretch 2]: [Time]

3. Keep it concise and formatted for WhatsApp (use bolding).
4. Do NOT include any intro or outro text, just the plan.
5. Do NOT include disclaimers (we add them separately).
6. IMPORTANT: Scale the workout complexity and number of exercises to match {session_duration}
"""

    # If user provided feedback on Day 1, apply it to subsequent days
    if change_request and day_number > 1:
        prompt += f"\n\nUSER'S DAY 1 FEEDBACK (Apply to all subsequent days):\nThe user made the following request when reviewing Day 1:\n\"{change_request}\"\n\nPlease ensure this day respects this feedback and maintains consistency."

    # If Day 1 exists, ask to match its style
    if day1_plan:
        prompt += f"\n\nMatch the style/formatting of Day 1:\n{day1_plan[:200]}..."

    response = llm.invoke(prompt)
    base_plan = response.content.strip()
    
    # Search for relevant exercise videos
    try:
        # Primary query using the focus verbatim
        search_query = f"{focus} workout exercises"
        videos = search_exercise_videos(search_query, max_results=3)

        # Fallback queries if nothing found (or very weak results)
        if not videos:
            focus_l = focus.lower()
            if "cardio" in focus_l or "endurance" in focus_l:
                fallback = "cardio endurance workout"
            elif "core" in focus_l:
                fallback = "core stability workout"
            elif "mobility" in focus_l or "stretch" in focus_l:
                fallback = "mobility stretching routine"
            elif "upper" in focus_l:
                fallback = "upper body strength workout"
            elif "lower" in focus_l or "power" in focus_l:
                fallback = "lower body workout"
            elif "recovery" in focus_l:
                fallback = "active recovery workout"
            else:
                fallback = f"{focus} workout"
            videos = search_exercise_videos(fallback, max_results=3)

        # Remove markdown formatting from base plan BEFORE adding videos
        # This preserves the *bold* formatting in video references
        cleaned_base_plan = remove_markdown(base_plan)
        
        # Add video references to the cleaned plan (video references keep their *bold* formatting)
        video_references = format_video_references(videos)
        final_plan = cleaned_base_plan + (video_references if video_references else "")
        return final_plan
    except Exception as e:
        logger.error("⚠️ Could not fetch video references: %s", e)
        # Return cleaned plan without videos
        return remove_markdown(base_plan)


def generate_complete_7day_exercise_plan(state: State) -> dict:
    """Generate a complete 7-day exercise plan with separate LLM calls for each day.
    
    Returns a dictionary with keys: 'day2', 'day3', 'day4', 'day5', 'day6', 'day7'
    """
    
    days_info = [
        (2, "Cardio & Endurance"),
        (3, "Core Stability"),
        (4, "Mobility & Stretching"),
        (5, "Upper Body Strength"),
        (6, "Lower Body Power"),
        (7, "Active Recovery"),
    ]
    
    # Get Day 1 plan for context
    day1_plan = state.get('day1_plan', '')
    
    # Extract user's change request if it exists (to maintain consistency across all days)
    user_change_request = state.get('day1_change_request', None)
    
    individual_days = {}
    
    for day_num, focus in days_info:
        try:
            logger.info("🔄 Generating Day %s exercise plan (%s)...", day_num, focus)
            
            # Generate the plan for this day, passing the change request
            day_plan = generate_day_exercise_plan(state, day_num, focus, change_request=user_change_request)
            
            # Store it
            individual_days[f'day{day_num}'] = day_plan
            logger.info("✅ Generated Day %s exercise plan", day_num)
            
        except Exception as e:
            logger.error("⚠️ Error generating Day %s exercise plan: %s", day_num, e)
            individual_days[f'day{day_num}'] = f"*Day {day_num}: {focus}* 🏋️\n\n⚠️ Unable to generate plan for this day. Please try again."
            
    return individual_days


def split_7day_exercise_plan(complete_plan: str, user_id: str = None, state = None) -> dict:
    """
    Split the generated 7-day exercise plan (Days 2-7) into individual day plans.
    
    Returns a dictionary with keys: 'day2', 'day3', 'day4', 'day5', 'day6', 'day7'
    """
    days = {}
    
    # More robust pattern to match various day formats
    # Matches "**Day 2:", "*Day 2:", "Day 2:", "Day 2 -", etc.
    day_pattern = r'(?:\*\*|\*|^)?Day\s*(\d)(?:[:\-]|\s+\*\*|\s+\*|\s+)(.*?)(?=(?:\*\*|\*|^)?Day\s*\d|$)'
    
    # Find all day markers
    day_matches = list(re.finditer(day_pattern, complete_plan, re.IGNORECASE | re.DOTALL))
    
    if not day_matches:
        # Fallback: try splitting by "---" separator
        parts = complete_plan.split('---')
        if len(parts) >= 6:
            for i, part in enumerate(parts[:6], start=2):
                days[f'day{i}'] = part.strip()
        else:
            # If can't split, return the whole plan for each day (fallback)
            logger.warning("⚠️ Warning: Could not split exercise plan by days. Using full plan for all days.")
            for day_num in range(2, 8):
                days[f'day{day_num}'] = complete_plan
        return days
    
    # Extract content for each day
    for match in day_matches:
        day_num = int(match.group(1))
        # Skip Day 1 if it somehow got in there (we only want 2-7)
        if day_num == 1:
            continue
            
        # The content is in group 2, but we need to be careful about where it ends
        # The regex lookahead handles the stop at the next "Day X"
        day_content = f"*Day {day_num} {match.group(2).strip()}"
        
        # Clean up trailing separators
        day_content = re.sub(r'\n---+\n$', '', day_content).strip()
        
        days[f'day{day_num}'] = day_content
    
    # Fill in any missing days
    for day_num in range(2, 8):
        if f'day{day_num}' not in days:
            days[f'day{day_num}'] = f"Day {day_num} plan not found in generated content."
            logger.warning("⚠️ Warning: Day %s exercise plan not found in split.", day_num)
    
    # If user_id provided, send each day as a single message
    if user_id:
        for day_num in range(2, 8):
            day_key = f'day{day_num}'
            day_text = days.get(day_key, f"Day {day_num} plan not found.")
            send_whatsapp_message(user_id, day_text)
            time.sleep(0.5)
    
    return days