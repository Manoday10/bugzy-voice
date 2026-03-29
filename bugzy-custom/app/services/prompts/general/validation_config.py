# ------------------ COMBINED VALIDATION CONFIGURATION ------------------ #
VALIDATION_RULES = {
    "age": {
        "question": "🎂 What's your age?",
        "validation_prompt": """
You are validating an age input. The user was asked: "What's your age?"

ACCEPT any response that indicates an age, including:
- Simple numbers: "25", "30", "45"
- Numbers with text: "I'm 28 years old", "28 years", "28 yrs"
- Age ranges that are reasonable: "mid-20s", "around 30", "late thirties"
- Any number between 1-120 that could realistically be someone's age

Be extremely flexible with formats and natural language expressions of age.

ONLY REJECT responses that are:
- Completely unrelated to age: product questions, random text, technical topics
- Unrealistic ages: numbers above 120 or below 1
- Inappropriate content: offensive language, explicit content

IMPORTANT SAFETY CHECK:
If the user message expresses sadness, depression, anxiety, hopelessness, mentions of “anti depression”,
or any mental/emotional distress, you MUST NOT respond casually or positively (e.g., no “nice”, “cool”, “great”).
In such cases, you should still perform the validation task (VALID/INVALID), but the system will override
the conversational reply and send a dedicated, supportive mental-health-safe message instead.

User input: "{input}"

Is this input relevant and valid for the age question?
Respond with only "VALID" or "INVALID". If invalid, explain why briefly.
"""
    },
    "height": {
        "question": "📏 What's your height?",
        "validation_prompt": """
You are validating a height input. The user was asked: "What's your height?"

ACCEPT any response that indicates height, including:
- Centimeters: "170 cm", "175", "5'8" in cm", "180cm"
- Feet and inches: "5'8"", "5 feet 8 inches", "5'8", "6 ft"
- Meters: "1.75m", "1.8 meters", "1.70"
- Approximate descriptions: "around 5'8"", "about 170cm", "tall", "average height"
- Any realistic height between 50-250 cm or 1'6"-8'0"

Be extremely flexible with units, formats, and natural language expressions.

ONLY REJECT responses that are:
- Completely unrelated to height: product questions, random text, technical topics
- Unrealistic heights: extremely short or tall measurements outside human range
- Inappropriate content: offensive language, explicit content

IMPORTANT SAFETY CHECK:
If the user message expresses sadness, depression, anxiety, hopelessness, mentions of “anti depression”,
or any mental/emotional distress, you MUST NOT respond casually or positively (e.g., no “nice”, “cool”, “great”).
In such cases, you should still perform the validation task (VALID/INVALID), but the system will override
the conversational reply and send a dedicated, supportive mental-health-safe message instead.

User input: "{input}"

Is this input relevant and valid for the height question?
Respond with only "VALID" or "INVALID". If invalid, explain why briefly.
"""
    },
    "weight": {
        "question": "⚖️ What's your weight?",
        "validation_prompt": """
You are validating a weight input. The user was asked: "What's your weight?"

ACCEPT any response that indicates weight, including:
- Kilograms: "70 kg", "75", "80kg", "65 kgs"
- Pounds: "150 lbs", "160 pounds", "170lb"
- Approximate descriptions: "around 70kg", "about 150 lbs", "average weight"
- Any realistic weight between 20-200 kg or 40-440 lbs

Be extremely flexible with units, formats, and natural language expressions.

ONLY REJECT responses that are:
- Completely unrelated to weight: product questions, random text, technical topics
- Unrealistic weights: extremely light or heavy measurements outside human range
- Inappropriate content: offensive language, explicit content
- Evasive responses: "don't want to tell", "private", "not sharing" (weight is important for health planning)

IMPORTANT SAFETY CHECK:
If the user message expresses sadness, depression, anxiety, hopelessness, mentions of “anti depression”,
or any mental/emotional distress, you MUST NOT respond casually or positively (e.g., no “nice”, “cool”, “great”).
In such cases, you should still perform the validation task (VALID/INVALID), but the system will override
the conversational reply and send a dedicated, supportive mental-health-safe message instead.

User input: "{input}"

Is this input relevant and valid for the weight question?
Respond with only "VALID" or "INVALID". If invalid, explain why briefly.
"""
    },
    "fitness_level": {
        "question": "💪 Fitness level (Beginner / Intermediate / Advanced)?",
        "valid_options": ["beginner", "intermediate", "advanced"],
        "typo_variations": {
            "beginner": ["begginer", "begginer", "newbie", "new", "starting", "just started", "novice", "amateur"],
            "intermediate": ["intermediat", "intermedite", "intermed", "mid", "middle", "moderate", "some experience"],
            "advanced": ["advance", "advancd", "expert", "pro", "professional", "experienced", "veteran"]
        },
        "validation_prompt": """
You are validating a fitness level input. The user was asked: "Fitness level (Beginner / Intermediate / Advanced)?"

Valid responses include: beginner, intermediate, advanced, or any clear variation of these (e.g., "I'm a beginner", "intermediate level", "advanced fitness", "just starting", "newbie", "expert", "pro")

Be flexible with typos and variations. Accept responses that clearly indicate fitness level even with minor spelling errors.

INVALID responses: "I don't want to tell", "not sharing", "prefer not to say", or similar evasive answers. Exercise planning requires this information for safety.

IMPORTANT SAFETY CHECK:
If the user message expresses sadness, depression, anxiety, hopelessness, mentions of “anti depression”,
or any mental/emotional distress, you MUST NOT respond casually or positively (e.g., no “nice”, “cool”, “great”).
In such cases, you should still perform the validation task (VALID/INVALID), but the system will override
the conversational reply and send a dedicated, supportive mental-health-safe message instead.

User input: "{input}"

Is this input relevant and valid for the fitness level question?
Respond with only "VALID" or "INVALID". If invalid, explain why briefly.
"""
    },
    "activity_types": {
        "question": "🏃‍♀️ Activities last week? (walking, gym, yoga, etc.)",
        "validation_prompt": """
You are validating an activity types input. The user was asked: "Activities last week? (walking, gym, yoga, etc.)"

Valid responses should mention physical activities, exercises, or sports they did. Examples: "walking and yoga", "went to gym", "no exercise", "running", "swimming", "didn't do much", "nothing", "just walking"

Be flexible with typos and variations. Accept responses that clearly indicate physical activities even with minor spelling errors.

INVALID responses: "I don't want to tell", "not sharing", "prefer not to say", random text, product questions, unrelated topics. Exercise planning requires this information.

IMPORTANT SAFETY CHECK:
If the user message expresses sadness, depression, anxiety, hopelessness, mentions of “anti depression”,
or any mental/emotional distress, you MUST NOT respond casually or positively (e.g., no “nice”, “cool”, “great”).
In such cases, you should still perform the validation task (VALID/INVALID), but the system will override
the conversational reply and send a dedicated, supportive mental-health-safe message instead.

User input: "{input}"

Is this input relevant and valid for the activity question?
Respond with only "VALID" or "INVALID". If invalid, explain why briefly.
"""
    },
    "exercise_frequency": {
        "question": "📅 How many days per week do you exercise?",
        "validation_prompt": """
You are validating an exercise frequency input. The user was asked: "How many days per week do you exercise?"

Valid responses should indicate a number of days (0-7) or frequency. Examples: "3 days", "5", "twice a week", "daily", "never", "not much", "rarely", "sometimes", "2-3 times"

Be flexible with typos and variations. Accept responses that clearly indicate frequency even with minor spelling errors.

INVALID responses: "I don't want to tell", "not sharing", "prefer not to say", unrelated topics, random text. Exercise planning requires this information for safety.

IMPORTANT SAFETY CHECK:
If the user message expresses sadness, depression, anxiety, hopelessness, mentions of “anti depression”,
or any mental/emotional distress, you MUST NOT respond casually or positively (e.g., no “nice”, “cool”, “great”).
In such cases, you should still perform the validation task (VALID/INVALID), but the system will override
the conversational reply and send a dedicated, supportive mental-health-safe message instead.

User input: "{input}"

Is this input relevant and valid for the frequency question?
Respond with only "VALID" or "INVALID". If invalid, explain why briefly.
"""
    },
    "exercise_intensity": {
        "question": "💨 Exercise intensity (Light / Moderate / Vigorous)?",
        "valid_options": ["light", "moderate", "vigorous"],
        "typo_variations": {
            "light": ["lite", "easy", "low", "gentle", "soft", "mild", "low intensity"],
            "moderate": ["moderat", "medium", "mid", "normal", "regular", "moderate intensity"],
            "vigorous": ["vigor", "intense", "high", "hard", "strong", "vigorous intensity", "high intensity"]
        },
        "validation_prompt": """
You are validating an exercise intensity input. The user was asked: "Exercise intensity (Light / Moderate / Vigorous)?"

Valid responses include: light, moderate, vigorous, or descriptions of intensity level (e.g., "easy", "hard", "intense", "low", "high")

Be flexible with typos and variations. Accept responses that clearly indicate intensity level even with minor spelling errors.

INVALID responses: "I don't want to tell", "not sharing", "prefer not to say". Exercise planning requires this information for safety and effectiveness.

IMPORTANT SAFETY CHECK:
If the user message expresses sadness, depression, anxiety, hopelessness, mentions of “anti depression”,
or any mental/emotional distress, you MUST NOT respond casually or positively (e.g., no “nice”, “cool”, “great”).
In such cases, you should still perform the validation task (VALID/INVALID), but the system will override
the conversational reply and send a dedicated, supportive mental-health-safe message instead.

User input: "{input}"

Is this input relevant and valid for the intensity question?
Respond with only "VALID" or "INVALID". If invalid, explain why briefly.
"""
    },
    "session_duration": {
        "question": "⏱️ Session duration (e.g., 30 mins, 45 mins)?",
        "validation_prompt": """
You are validating a session duration input. The user was asked: "Session duration (e.g., 30 mins, 45 mins)?"

Valid responses should indicate time duration. Examples: "30 minutes", "45 mins", "1 hour", "20-30 min", "half hour", "about 30", "not sure", "whatever works"

Be flexible with typos and variations. Accept responses that clearly indicate time duration even with minor spelling errors.

INVALID responses: "I don't want to tell", "not sharing", "prefer not to say", unrelated topics, random text. Exercise planning requires this information.

IMPORTANT SAFETY CHECK:
If the user message expresses sadness, depression, anxiety, hopelessness, mentions of “anti depression”,
or any mental/emotional distress, you MUST NOT respond casually or positively (e.g., no “nice”, “cool”, “great”).
In such cases, you should still perform the validation task (VALID/INVALID), but the system will override
the conversational reply and send a dedicated, supportive mental-health-safe message instead.

User input: "{input}"

Is this input relevant and valid for the duration question?
Respond with only "VALID" or "INVALID". If invalid, explain why briefly.
"""
    },
    "sedentary_time": {
        "question": "🪑 Hours per day sitting (excluding sleep)?",
        "validation_prompt": """
You are validating a sedentary time input. The user was asked: "Hours per day sitting (excluding sleep)?"

Valid responses should indicate hours or time spent sitting. Examples: "8 hours", "4-5 hours", "most of the day", "not much", "all day", "a lot", "too much", "not sure"

Be flexible with typos and variations. Accept responses that clearly indicate sitting time even with minor spelling errors.

INVALID responses: "I don't want to tell", "not sharing", "prefer not to say", unrelated topics, random text. Exercise planning requires this information.

IMPORTANT SAFETY CHECK:
If the user message expresses sadness, depression, anxiety, hopelessness, mentions of “anti depression”,
or any mental/emotional distress, you MUST NOT respond casually or positively (e.g., no “nice”, “cool”, “great”).
In such cases, you should still perform the validation task (VALID/INVALID), but the system will override
the conversational reply and send a dedicated, supportive mental-health-safe message instead.

User input: "{input}"

Is this input relevant and valid for the sedentary time question?
Respond with only "VALID" or "INVALID". If invalid, explain why briefly.
"""
    },
    "exercise_goals": {
        "question": "🎯 Fitness goals (Weight loss / Muscle gain / Mobility / Health)?",
        "validation_prompt": """
You are validating an exercise goals input. The user was asked: "Fitness goals (Weight loss / Muscle gain / Mobility / Health)?"

Valid responses should mention fitness goals. Examples: "weight loss", "build muscle", "improve mobility", "general health", "get stronger", "lose weight", "muscle gaining", "get fit", "stay healthy", "flexibility"

Be flexible with typos and variations. Accept responses that clearly indicate fitness goals even with minor spelling errors.

INVALID responses: "I don't want to tell", "not sharing", "prefer not to say", unrelated topics, random text. Exercise planning requires clear goals.

IMPORTANT SAFETY CHECK:
If the user message expresses sadness, depression, anxiety, hopelessness, mentions of “anti depression”,
or any mental/emotional distress, you MUST NOT respond casually or positively (e.g., no “nice”, “cool”, “great”).
In such cases, you should still perform the validation task (VALID/INVALID), but the system will override
the conversational reply and send a dedicated, supportive mental-health-safe message instead.

User input: "{input}"

Is this input relevant and valid for the goals question?
Respond with only "VALID" or "INVALID". If invalid, explain why briefly.
"""
    },
    "health_conditions": {
        "question": "🩺 Do you have any health conditions I should know about?",
        "validation_prompt": """
You are validating a response about health conditions for meal planning. The user was asked: "Do you have any health conditions I should know about?"

VALID responses include:
- Specific health conditions: "diabetes", "IBS", "hypertension", "thyroid issues", "PCOS", "heart disease", "kidney disease", "celiac disease", "Crohn's disease"
- Statements indicating no conditions: "none", "no", "nothing", "no conditions", "all good", "healthy", "no health issues"
- Medical terms or conditions: "high blood pressure", "high cholesterol", "asthma", "arthritis", "autoimmune disease"
- Vague but relevant: "some digestive issues", "minor health problems", "doctor said I have...", "diagnosed with..."

INVALID responses - REJECT these:
- Food items or meals: "rice", "chicken", "eggs", "bread", "vegetables", "meat", "fish", "dal", "roti", "pasta", "salad"
- Meal descriptions: "rice and chicken", "eggs and toast", "dal chawal", "chicken curry", "vegetable soup"
- Dinner/lunch/breakfast items: Any description that sounds like a meal or food combination
- Time-related responses: "7 PM", "8:30", "evening", "morning" (these are meal timings, not health conditions)
- Completely unrelated topics: greetings, random text, product questions
- Empty or unclear responses: just "yes", "yeah", "ok" without specifying a condition

CRITICAL RULE: If the response mentions ANY food items, ingredients, or meal descriptions (like "rice", "chicken", "vegetables", "dal", "roti", "eggs", "bread", "pasta", etc.), it is INVALID. The user is likely confusing this with a meal question.

IMPORTANT SAFETY CHECK:
If the user message expresses sadness, depression, anxiety, hopelessness, mentions of "anti depression",
or any mental/emotional distress, you MUST NOT respond casually or positively (e.g., no "nice", "cool", "great").
In such cases, you should still perform the validation task (VALID/INVALID), but the system will override
the conversational reply and send a dedicated, supportive mental-health-safe message instead.

User input: "{input}"

Is this input relevant and valid for the health conditions question?
Respond with only "VALID" or "INVALID". If invalid, explain why briefly.
"""
    },
    "medications": {
        "question": "💊 Just to help us understand better, could you tell me if you're on any medications? Feel free to say 'none' if not.",
        "validation_prompt": """
    You are validating a response about medications. The user was asked: "Just to help us understand better, could you tell me if you're on any medications? Feel free to say 'none' if not."

    Valid responses include:
    - Specific medication names: "metformin", "insulin", "levothyroxine", "lisinopril", "omeprazole", "aspirin"
    - General medication descriptions: "diabetes medication", "blood pressure pills", "thyroid medicine", "antacid"
    - Multiple medications: "metformin and atorvastatin", "insulin + blood pressure meds", "metformin, levothyroxine"
    - Statements indicating no medications: "none", "no", "not taking any", "no medications", "nothing", "none at all", "nope", "nah"
    - Uncertain or privacy-based replies: "not sure", "prefer not to say", "don't want to share", "rather not share", "idk", "I don't know", "unsure", "can't remember"
    - Casual/informal responses: "just vitamins", "some pills", "nothing regular", "only when needed", "supplements only"
    - The Good Bug products (treat as supplements/medications, NOT as product questions):
    * "Metabolically Lean AMS", "AMS", "Advanced Metabolic System"
    * "Metabolically Lean Supercharged", "Supercharged"
    * "PCOS Balance", "PCOD Balance"
    * "Gut Balance"
    * "Bye Bye Bloat"
    * "Smooth Move"
    * "IBS Rescue", "IBS C", "IBS Constipation"
    * "IBS DnM", "IBS D&M", "IBS D", "IBS M", "IBS Diarrhea", "IBS Mixed"
    * "First Defense", "First Defence"
    * "Sleep and Calm"
    * "Good Down There"
    * "Good to Glow"
    * "Happy Tummies"
    * "Acidity Aid"
    * "Gut Cleanse"
    * "Metabolic Fiber Boost", "Metabolic Fiber"
    * "Smooth Move Fiber Boost", "Smooth Fiber"
    * "Prebiotic Fiber Boost", "Fiber Boost"
    * "Water Kefir", "Kefir"
    * "Kombucha"

    IMPORTANT: If the user mentions any of The Good Bug products, accept it as a VALID medication response. Do NOT treat it as a product question. They are sharing what they currently consume as part of their health regimen.

    Be extremely flexible with typos, brand names, generic names, and casual descriptions.
    Accept responses that clearly indicate medications or confirm none are being taken.
    Be friendly and empathetic - users may be hesitant about sharing medications.

    Invalid responses: 
    - Empty or blank responses (no text provided)
    - Completely unrelated topics (e.g., "good morning", "how are you", "thanks")
    - Random text or greetings
    - Simple affirmatives without details (e.g., just "yes", "yeah", "yep", "yup" without specifying medications)
    - Questions asking about products (e.g., "what is AMS?", "how does PCOS Balance work?", "tell me about X")

    CRITICAL RULES:
    1. Empty/blank input = INVALID (no information provided)
    2. "yes"/"yeah"/"yep" alone = INVALID (doesn't specify which medications)
    3. "idk"/"I don't know" = VALID (valid uncertain response)
    4. "AMS" alone = VALID (it's a Good Bug product they're taking)
    5. "what is AMS?" = INVALID (it's a question, not an answer)
    6. "just vitamins" = VALID (valid casual response about supplements)

    User input: "{input}"

    Is this input relevant and valid for the medications question?
    Respond with only "VALID" or "INVALID". If invalid, explain why briefly.
    """
    },
    "meal_timing_breakfast": {
    "question": "🕐 When do you usually have breakfast?",
    "default_timing": "7-8 AM",
    "validation_prompt": """
You are validating a breakfast timing response. The user was asked: "When do you usually have breakfast?"

ACCEPT any response that indicates a time, including:
- Numbers that could be times: "7", "8", "9", "10", "11" (assume AM for breakfast)
- Times with colons: "7:30", "8:15", "9:00" (assume AM for breakfast) 
- Times with AM/PM: "8 am", "9:30 AM", "7:00 am"
- Time ranges: "7-8", "between 8-9", "around 7:30"
- Descriptive times: "early morning", "around 8", "before 9", "no fixed time", "morning", "9ish", "late breakfast"
- Flexible responses: "anytime you prefer", "whatever works", "flexible", "depends", "varies", "up to you", "not fixed", "whenever I wake up", "depends on work"
- Meal skipping: "I don't eat breakfast", "skip breakfast", "no breakfast", "don't do breakfast"

For breakfast context, assume numbers 5-12 refer to morning times (AM) automatically.
For flexible responses like "anytime you prefer", default timing of 7-8 AM will be used.

REJECT 24-hour format times like "14:00", "1500", "13:30", "1400" for breakfast as these are afternoon/evening times and inappropriate for breakfast timing.

Be very flexible with formats and assume reasonable breakfast timing context.

Invalid responses: random text, completely unrelated content, or irrelevant phrases.

IMPORTANT SAFETY CHECK:
If the user message expresses sadness, depression, anxiety, hopelessness, mentions of “anti depression”,
or any mental/emotional distress, you MUST NOT respond casually or positively (e.g., no “nice”, “cool”, “great”).
In such cases, you should still perform the validation task (VALID/INVALID), but the system will override
the conversational reply and send a dedicated, supportive mental-health-safe message instead.

User input: "{input}"

Is this input relevant and valid for the breakfast timing question?
Respond with only "VALID" or "INVALID". If invalid, explain why briefly.
"""

    },
    "meal_timing_lunch": {
    "question": "🥗 When do you usually have lunch?",
    "default_timing": "1-2 PM",
    "validation_prompt": """
You are validating a lunch timing response. The user was asked: "When do you usually have lunch?"

ACCEPT any response that indicates a time, including:
- Numbers that could be times: "12", "1", "2", "3", "4" (assume PM for lunch)
- Times with colons: "12:30", "1:15", "2:00" (assume PM for lunch)
- Times with AM/PM: "1 pm", "2:30 PM", "12:00 pm"
- Time ranges: "12-1", "between 1-2", "around 2:30"
- Descriptive times: "afternoon", "around 1", "after 12", "no fixed time", "depends on work", "not fixed"
- Flexible responses: "anytime you prefer", "whatever works", "flexible", "depends", "varies", "up to you"
- Meal skipping: "I don't eat lunch", "skip lunch", "no lunch", "don't do lunch", "don't usually have lunch", "I skip lunch"

For lunch context, assume numbers 11-5 refer to afternoon times (PM) automatically.
For flexible responses like "anytime you prefer", default timing of 1-2 PM will be used.

REJECT 24-hour format times like "01:00", "0200", "02:30" for lunch as these are night/early morning times and inappropriate for lunch timing.

Be very flexible with formats and assume reasonable lunch timing context.

Invalid responses: unrelated topics, foods, or completely non-time answers.

IMPORTANT SAFETY CHECK:
If the user message expresses sadness, depression, anxiety, hopelessness, mentions of “anti depression”,
or any mental/emotional distress, you MUST NOT respond casually or positively (e.g., no “nice”, “cool”, “great”).
In such cases, you should still perform the validation task (VALID/INVALID), but the system will override
the conversational reply and send a dedicated, supportive mental-health-safe message instead.

User input: "{input}"

Is this input relevant and valid for the lunch timing question?
Respond with only "VALID" or "INVALID". If invalid, explain why briefly.
"""
},
    "meal_timing_dinner": {
    "question": "🍽️ What about dinner?",
    "default_timing": "8-9 PM",
    "validation_prompt": """
You are validating a dinner timing response. The user was asked: "What about dinner?"

ACCEPT any response that indicates a time, including:
- Numbers that could be times: "7", "8", "9", "10", "11" (assume PM for dinner)
- Times with colons: "7:30", "8:15", "9:00" (assume PM for dinner)
- Times with AM/PM: "8 pm", "9:30 PM", "7:00 pm"
- Time ranges: "7-8", "between 8-9", "around 8:30"
- Descriptive times: "evening", "night", "around 8", "late", "no fixed time", "depends", "not fixed"
- Flexible responses: "anytime you prefer", "whatever works", "flexible", "depends", "varies", "up to you"
- Meal skipping: "I don't eat dinner", "skip dinner", "no dinner", "don't do dinner", "sometimes none"

For dinner context, assume numbers 6-11 refer to evening times (PM) automatically.
For flexible responses like "anytime you prefer", default timing of 8-9 PM will be used.

REJECT 24-hour format times like "01:00", "0200", "02:30", "03:00" for dinner as these are night/early morning times and inappropriate for dinner timing.

Be very flexible with formats and assume reasonable dinner timing context.

Invalid responses: completely unrelated topics or meaningless text.

IMPORTANT SAFETY CHECK:
If the user message expresses sadness, depression, anxiety, hopelessness, mentions of “anti depression”,
or any mental/emotional distress, you MUST NOT respond casually or positively (e.g., no “nice”, “cool”, “great”).
In such cases, you should still perform the validation task (VALID/INVALID), but the system will override
the conversational reply and send a dedicated, supportive mental-health-safe message instead.

User input: "{input}"

Is this input relevant and valid for the dinner timing question?
Respond with only "VALID" or "INVALID". If invalid, explain why briefly.
"""
    },
    "current_breakfast": {
        "question": "🍳 What do you typically eat for breakfast? And roughly how much?",
        "validation_prompt": """
You are validating a breakfast food response. The user was asked: "What do you typically eat for breakfast? And roughly how much?"

ACCEPT any response that mentions:
- Any food items (with or without quantities): "4 eggs", "chicken", "rice", "bread", "oats", "fruits", "eggs", "toast", "coffee"
- Indian breakfast items: "chai khari", "poha", "upma", "idli", "dosa", "paratha", "aloo sabzi", "dal chawal"
- Beverages with snacks: "tea with biscuits", "coffee and toast", "chai", "milk", "coffee"
- Simple quantities: "2 rotis", "1 bowl", "small portion", "a lot"
- Meal skipping: "skip breakfast", "don't eat breakfast", "no breakfast", "nothing", "I skip breakfast" 
- General descriptions: "light breakfast", "heavy meal", "usual stuff", "home food", "whatever is available", "Indian breakfast", "Western breakfast", "Breakfast at home", "Breakfast on the go"
- Privacy or non-disclosure: "prefer not to say", "don't want to tell", "not fixed"
- Regional foods: Any mention of local/regional food items from any cuisine

Single-word answers like "eggs", "toast", or "coffee" are acceptable — assume they describe breakfast.

Be extremely flexible with typos, abbreviations, and variations. Accept ALL food-related responses, including regional and cultural food combinations. Be warm and flexible.

ONLY REJECT responses that are:
- Completely unrelated to food/meals: product questions, random text, technical topics
- Inappropriate content: offensive language, explicit content
- Totally unrelated topics, nonsense text, or random emojis

IMPORTANT SAFETY CHECK:
If the user message expresses sadness, depression, anxiety, hopelessness, mentions of “anti depression”,
or any mental/emotional distress, you MUST NOT respond casually or positively (e.g., no “nice”, “cool”, “great”).
In such cases, you should still perform the validation task (VALID/INVALID), but the system will override
the conversational reply and send a dedicated, supportive mental-health-safe message instead.

User input: "{input}"

Is this input relevant and valid for the breakfast food question?
Respond with only "VALID" or "INVALID". If invalid, explain why briefly.
"""
    },
    "current_lunch": {
        "question": "🍱 How about lunch – what's your usual?",
        "validation_prompt": """
You are validating a lunch food response. The user was asked: "How about lunch – what's your usual?"

ACCEPT any response that mentions:
- Any food items (with or without quantities): "chicken", "rice and dal", "salad", "sandwich", "pasta", "rice", "roti"
- Indian lunch items: "dal rice", "roti sabzi", "rajma chawal", "curd rice", "biryani", "sambar rice"
- Any beverages: "soup", "smoothie", "water", "buttermilk", "lassi"
- Simple quantities: "1 plate", "small portion", "big meal", "half plate"
- Meal skipping: "skip lunch", "don't eat lunch", "no lunch", "nothing", "I skip lunch", "don't usually have lunch"
- General descriptions: "light lunch", "heavy meal", "same as always", "usual stuff", "home food", "canteen food", "depends on day"
- Privacy or non-disclosure: "prefer not to say", "don't want to tell", "not fixed"
- Regional foods: Any mention of local/regional food items from any cuisine

Short, casual, or single-word food responses are acceptable.

Be extremely flexible with typos, abbreviations, and variations. Accept ALL food-related responses, including regional and cultural food combinations. Be flexible and accept honest or minimal answers.

ONLY REJECT responses that are:
- Completely unrelated to food/meals: product questions, random text, technical topics
- Inappropriate content: offensive language, explicit content

IMPORTANT SAFETY CHECK:
If the user message expresses sadness, depression, anxiety, hopelessness, mentions of “anti depression”,
or any mental/emotional distress, you MUST NOT respond casually or positively (e.g., no “nice”, “cool”, “great”).
In such cases, you should still perform the validation task (VALID/INVALID), but the system will override
the conversational reply and send a dedicated, supportive mental-health-safe message instead.

User input: "{input}"

Is this input relevant and valid for the lunch question?
Respond with only "VALID" or "INVALID". If invalid, explain why briefly.
"""
    },
    "current_dinner": {
        "question": "🍽️ And for dinner?",
        "validation_prompt": """
You are validating a dinner food response. The user was asked: "And for dinner?"

ACCEPT any response that mentions:
- Any food items (with or without quantities): "chicken", "roti and sabzi", "soup", "rice", "fish"
- Indian dinner items: "dal roti", "rajma chawal", "chicken curry", "paneer sabzi", "khichdi", "pulao"
- Any beverages: "soup", "milk", "tea", "buttermilk"
- Simple quantities: "2 pieces", "small dinner", "big meal", "1 bowl"
- Meal skipping: "skip dinner", "don't eat dinner", "no dinner", "nothing", "I skip dinner", "don't do dinner"
- General descriptions: "light dinner", "heavy meal", "same as lunch", "usual stuff", "home food", "whatever's cooked", "normal Indian food", "depends on day", "non-vegetarian dinner", "vegetarian dinner", "dinner at home", "dinner on the go", "any type of food", "any type of dinner"
- Regional foods: Any mention of local/regional food items from any cuisine

Single-word or short answers like "chicken" or "rice" are valid — they clearly indicate a meal.

Be extremely flexible with typos, abbreviations, and variations. Accept ALL food-related responses, including regional and cultural food combinations.

ONLY REJECT responses that are:
- Completely unrelated to food/meals: product questions, random text, technical topics
- Inappropriate content: offensive language, explicit content
- Random, off-topic text, or meaningless phrases

IMPORTANT SAFETY CHECK:
If the user message expresses sadness, depression, anxiety, hopelessness, mentions of “anti depression”,
or any mental/emotional distress, you MUST NOT respond casually or positively (e.g., no “nice”, “cool”, “great”).
In such cases, you should still perform the validation task (VALID/INVALID), but the system will override
the conversational reply and send a dedicated, supportive mental-health-safe message instead.

User input: "{input}"

Is this input relevant and valid for the dinner question?
Respond with only "VALID" or "INVALID". If invalid, explain why briefly.
"""
    },
    "diet_preference": {
        "question": "🥗 What's your dietary preference?",
        "valid_options": ["non-vegetarian", "vegetarian", "vegan", "pescatarian", "flexitarian", "keto"],
        "typo_variations": {
            "non-vegetarian": ["non veg", "nonveg", "meat eater"],
            "vegetarian": ["veg", "veggie", "vegetarian"],
            "vegan": ["plant based", "plant-based"],
            "pescatarian": ["pescatarian", "pescetarian", "seafood only"],
            "flexitarian": ["flexi", "mostly veg"],
            "keto": ["ketogenic", "low carb", "low-carb"]
        },
        "validation_prompt": """
You are validating a dietary preference response. The user was asked: "What's your dietary preference?"

Valid responses include common diet styles (e.g., non-vegetarian, vegetarian, vegan, pescatarian, flexitarian, keto) or statements indicating no specific preference, none, not any.

Be flexible with typos and related phrases that clearly indicate a diet style.

Invalid responses: unrelated topics or non-diet answers.

IMPORTANT SAFETY CHECK:
If the user message expresses sadness, depression, anxiety, hopelessness, mentions of “anti depression”,
or any mental/emotional distress, you MUST NOT respond casually or positively (e.g., no “nice”, “cool”, “great”).
In such cases, you should still perform the validation task (VALID/INVALID), but the system will override
the conversational reply and send a dedicated, supportive mental-health-safe message instead.

User input: "{input}"

Is this input relevant and valid for the dietary preference question?
Respond with only "VALID" or "INVALID". If invalid, explain why briefly.
"""
    },
    "cuisine_preference": {
        "question": "🍛 Do you have any cuisine preferences?",
        "validation_prompt": """
You are validating a cuisine preference response. The user was asked: "Do you have any cuisine preferences?"

Valid responses should mention one or more cuisines (e.g., Indian, South Indian, Italian, Chinese, all cuisines) or indicate no preference, not any, none, not any preference.

Be flexible with typos and shorthand names of cuisines.

Invalid responses: unrelated topics or non-food answers.

IMPORTANT SAFETY CHECK:
If the user message expresses sadness, depression, anxiety, hopelessness, mentions of “anti depression”,
or any mental/emotional distress, you MUST NOT respond casually or positively (e.g., no “nice”, “cool”, “great”).
In such cases, you should still perform the validation task (VALID/INVALID), but the system will override
the conversational reply and send a dedicated, supportive mental-health-safe message instead.

User input: "{input}"

Is this input relevant and valid for the cuisine preference question?
Respond with only "VALID" or "INVALID". If invalid, explain why briefly.
"""
    },
    "allergies": {
        "question": "🚫 Do you have any food allergies or intolerances?",
        "validation_prompt": """
You are validating an allergies or intolerances response. The user was asked: "Do you have any food allergies or intolerances?"

Valid responses include:
- Clear mentions of allergies or intolerances: "dairy allergy", "gluten sensitive", "nut allergy", "lactose intolerant", "spice intolerance"
- Responses indicating no allergies: "none", "no", "not any", "no allergies", "no intolerances", "nothing", "not that I know of"
- Mild or uncertain mentions: "not sure", "maybe dairy", "sometimes spicy food bothers me"
- Skipping or privacy-based replies: "prefer not to say", "don't want to tell", "not comfortable sharing"

Be flexible and empathetic — users may describe this casually or vaguely.
Typos or informal language like "alergic", "glutin", "lactose intolrant", "nope" are acceptable.

Invalid responses: random text or completely unrelated topics (like "good morning", "hello", etc.).

IMPORTANT SAFETY CHECK:
If the user message expresses sadness, depression, anxiety, hopelessness, mentions of “anti depression”,
or any mental/emotional distress, you MUST NOT respond casually or positively (e.g., no “nice”, “cool”, “great”).
In such cases, you should still perform the validation task (VALID/INVALID), but the system will override
the conversational reply and send a dedicated, supportive mental-health-safe message instead.

User input: "{input}"

Is this input relevant and valid for the allergies question?
Respond with only "VALID" or "INVALID". If invalid, explain why briefly.
"""
    },
    "water_intake": {
        "question": "💧 Approximately how much water do you drink daily?",
        "validation_prompt": """
You are validating a water intake response. The user was asked: "Approximately how much water do you drink daily?"

Valid responses should mention quantity (glasses, liters, bottles) or qualitative descriptions (e.g., "a lot", "not much", "2 liters").

Be flexible with typos and numeric formats.

INVALID responses: "I don't want to tell", "not sharing", "prefer not to say", unrelated topics, or non-quantity answers. Water intake is important for meal planning.

IMPORTANT SAFETY CHECK:
If the user message expresses sadness, depression, anxiety, hopelessness, mentions of “anti depression”,
or any mental/emotional distress, you MUST NOT respond casually or positively (e.g., no “nice”, “cool”, “great”).
In such cases, you should still perform the validation task (VALID/INVALID), but the system will override
the conversational reply and send a dedicated, supportive mental-health-safe message instead.

User input: "{input}"

Is this input relevant and valid for the water intake question?
Respond with only "VALID" or "INVALID". If invalid, explain why briefly.
"""
    },
    "beverages": {
        "question": "☕ Any other beverages you regularly have? If yes, how many per day?",
        "validation_prompt": """
You are validating a beverages response. The user was asked: "Any other beverages you regularly have? If yes, how many per day?"

Valid responses include:
- Beverage mentions: "tea", "coffee", "green tea", "soft drinks", "juice", "energy drinks", "chai", "cold drink", "soda"
- With quantities: "2 cups of tea", "3 coffees a day", "sometimes juice", "1 glass", "once in a while"
- Indicating none: "none", "no", "I don't drink any", "just water"
- Privacy or uncertainty: "not sure", "prefer not to say", "don't want to tell", "depends on the day"

Be flexible and friendly — people may respond casually or vaguely.
Accept typos, short answers, and conversational phrases.

Invalid responses: completely unrelated text (like greetings or random words not connected to beverages).

IMPORTANT SAFETY CHECK:
If the user message expresses sadness, depression, anxiety, hopelessness, mentions of “anti depression”,
or any mental/emotional distress, you MUST NOT respond casually or positively (e.g., no “nice”, “cool”, “great”).
In such cases, you should still perform the validation task (VALID/INVALID), but the system will override
the conversational reply and send a dedicated, supportive mental-health-safe message instead.

User input: "{input}"

Is this input relevant and valid for the beverages question?
Respond with only "VALID" or "INVALID". If invalid, explain why briefly.
"""
    },
    "lifestyle": {
        "question": "🥐 How often do you eat outside food?",
        "validation_prompt": """
You are validating an outside food frequency response. The user was asked: "How often do you eat outside food?"

Valid responses include:
- Frequency descriptions: "rarely", "once a week", "1-2 times", "3-4 times", "daily", "every weekend", "occasionally", "wekly", "ocasionly", "rarelly"
- Flexible phrases: "sometimes", "depends on work", "not fixed", "too often", "hardly ever", "whenever I feel lazy", "only weekends"
- Privacy or non-disclosure: "prefer not to say", "don't want to tell", "rather not share"
- Humor or casual phrasing: "too much 😅"

Be friendly and understanding — users may answer casually, vaguely, or with humor.
Accept short, informal, or approximate answers. Typos are fine.

Invalid responses: completely unrelated text (like greetings or random off-topic sentences).

IMPORTANT SAFETY CHECK:
If the user message expresses sadness, depression, anxiety, hopelessness, mentions of “anti depression”,
or any mental/emotional distress, you MUST NOT respond casually or positively (e.g., no “nice”, “cool”, “great”).
In such cases, you should still perform the validation task (VALID/INVALID), but the system will override
the conversational reply and send a dedicated, supportive mental-health-safe message instead.

User input: "{input}"

Is this input relevant and valid for the outside food frequency question?
Respond with only "VALID" or "INVALID". If invalid, explain why briefly.
"""
    },
    "activity_level": {
        "question": "🏃 How active are you usually?",
        "valid_options": ["sedentary", "lightly active", "moderate", "very active", "extreme"],
        "typo_variations": {
            "sedentary": ["sedantary", "desk job", "little activity"],
            "lightly active": ["light", "light activity", "walks sometimes"],
            "moderate": ["moderately active", "moderate active", "regular exercise"],
            "very active": ["very", "highly active", "intense"],
            "extreme": ["athlete", "extremely active", "daily intense"]
        },
        "validation_prompt": """
You are validating an activity level response. The user was asked: "How active are you usually?"

Valid responses include standard activity levels (sedentary, lightly active, moderate, very active, extreme) or clear descriptions of activity habits.

Be flexible with typos and descriptive phrases.

Invalid responses: unrelated topics or non-activity answers.

IMPORTANT SAFETY CHECK:
If the user message expresses sadness, depression, anxiety, hopelessness, mentions of “anti depression”,
or any mental/emotional distress, you MUST NOT respond casually or positively (e.g., no “nice”, “cool”, “great”).
In such cases, you should still perform the validation task (VALID/INVALID), but the system will override
the conversational reply and send a dedicated, supportive mental-health-safe message instead.

User input: "{input}"

Is this input relevant and valid for the activity level question?
Respond with only "VALID" or "INVALID". If invalid, explain why briefly.
"""
    },
    "sleep_stress": {
        "question": "😴 How are your sleep and stress levels? (hours of sleep, stress level)",
        "validation_prompt": """
You are validating a sleep and stress response. The user was asked: "How are your sleep and stress levels? (hours of sleep, stress level)"

Valid responses include:
- Specific details: "6 hours, high stress", "7-8 hours, low stress", "sleep well, medium stress", "8 hr"
- General feelings: "not great", "okay", "good", "tired all the time", "pretty stressed", "doing fine", "all good", "pretty good", "fine", "could be better", "okayish"
- Flexible or vague answers: "depends", "varies", "can't sleep properly", "no stress", "lots of stress", "sleep okayish"
- Skipping or privacy: "prefer not to say", "don't want to tell", "rather not share"

Be kind and understanding — users may answer casually or emotionally rather than precisely.
Be very flexible with typos and natural language. Accept general wellness descriptions and typos like "streess", "slepp".

Invalid responses: completely unrelated text (like greetings, random numbers without context, or off-topic phrases).

IMPORTANT SAFETY CHECK:
If the user message expresses sadness, depression, anxiety, hopelessness, mentions of “anti depression”,
or any mental/emotional distress, you MUST NOT respond casually or positively (e.g., no “nice”, “cool”, “great”).
In such cases, you should still perform the validation task (VALID/INVALID), but the system will override
the conversational reply and send a dedicated, supportive mental-health-safe message instead.

User input: "{input}"

Is this input relevant and valid for the sleep and stress question?
Respond with only "VALID" or "INVALID". If invalid, explain why briefly.
"""
    },
    "supplements": {
        "question": "💊 Are you currently taking any supplements? (Vitamins, Minerals, Protein powder, etc.)",
        "validation_prompt": """
You are validating a supplements response. The user was asked: "Are you currently taking any supplements? (Vitamins, Minerals, Protein powder, etc.)"

Valid responses include:
- Specific supplements: "vitamin D", "multivitamin", "protein powder", "omega-3", "fish oil", "calcium", "magnesium", "B12", "zinc"
- Multiple supplements: "vitamin D and omega-3", "multivitamin + protein powder", "several vitamins"
- General descriptions: "some vitamins", "protein supplement", "just vitamins", "a few supplements"
- Statements indicating no supplements: "none", "no", "not taking any", "no supplements", "nothing", "don't take any"
- Uncertain or privacy-based replies: "not sure", "prefer not to say", "don't want to share", "maybe", "sometimes"

Be flexible with typos, brand names, and casual descriptions. Accept responses that clearly indicate supplements or confirm none are being taken.

Invalid responses: completely unrelated topics, random text, greetings, or off-topic questions not about supplements.

IMPORTANT SAFETY CHECK:
If the user message expresses sadness, depression, anxiety, hopelessness, mentions of “anti depression”,
or any mental/emotional distress, you MUST NOT respond casually or positively (e.g., no “nice”, “cool”, “great”).
In such cases, you should still perform the validation task (VALID/INVALID), but the system will override
the conversational reply and send a dedicated, supportive mental-health-safe message instead.

User input: "{input}"

Is this input relevant and valid for the supplements question?
Respond with only "VALID" or "INVALID". If invalid, explain why briefly.
"""
    },
    "gut_health": {
        "question": "💩 How's your gut health? Do you experience any of these digestive issues?",
        "validation_prompt": """
You are validating a gut health response. The user was asked: "How's your gut health? Do you experience any of these digestive issues?"

Valid responses include:
- Specific digestive issues: "constipation", "gas", "bloating", "acidity", "heartburn", "irregular bowel movements", "diarrhea", "IBS"
- Multiple issues: "constipation and bloating", "gas + acidity", "several issues", "all of them"
- Statements indicating no issues: "none", "no", "all good", "no issues", "everything's fine", "healthy", "no problems"
- General descriptions: "sometimes constipated", "occasional bloating", "rarely", "not much", "mild issues"
- Privacy or uncertain replies: "prefer not to say", "don't want to tell", "rather not share", "not sure", "maybe"

Be empathetic and flexible — gut health can be a sensitive topic. Accept casual descriptions, typos, and vague responses.

Invalid responses: completely unrelated topics, random text, greetings, or off-topic content not about digestion.

IMPORTANT SAFETY CHECK:
If the user message expresses sadness, depression, anxiety, hopelessness, mentions of “anti depression”,
or any mental/emotional distress, you MUST NOT respond casually or positively (e.g., no “nice”, “cool”, “great”).
In such cases, you should still perform the validation task (VALID/INVALID), but the system will override
the conversational reply and send a dedicated, supportive mental-health-safe message instead.

User input: "{input}"

Is this input relevant and valid for the gut health question?
Respond with only "VALID" or "INVALID". If invalid, explain why briefly.
"""
    },
    "meal_goals": {
        "question": "🎯 Finally, what are your main nutrition goals?",
        "validation_prompt": """
You are validating a nutrition goals response. The user was asked: "Finally, what are your main nutrition goals?"

Valid responses include:
- Common goals: "weight loss", "weight gain", "maintain weight", "better energy", "gut healing", "improve immunity", "healthy lifestyle", "feel fit", "overall wellness", "loose weight", "stay helthy", "gain muscel"
- Broader intents: "get healthier", "eat clean", "feel energetic", "tone up", "eat better"
- Neutral or uncertain replies: "not sure", "no goals", "just maintaining", "nothing specific"

Be flexible and kind — users may express their goals casually, vaguely, or with typos.
Accept short, natural language replies as valid if they reflect any nutrition, body, or wellness intent.

Invalid responses: completely unrelated topics or meaningless text (e.g., greetings, random words).

IMPORTANT SAFETY CHECK:
If the user message expresses sadness, depression, anxiety, hopelessness, mentions of “anti depression”,
or any mental/emotional distress, you MUST NOT respond casually or positively (e.g., no “nice”, “cool”, “great”).
In such cases, you should still perform the validation task (VALID/INVALID), but the system will override
the conversational reply and send a dedicated, supportive mental-health-safe message instead.

User input: "{input}"

Is this input relevant and valid for the nutrition goals question?
Respond with only "VALID" or "INVALID". If invalid, explain why briefly.
"""
    }
}