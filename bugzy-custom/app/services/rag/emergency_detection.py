"""
CTAS (Canadian Triage and Acuity Scale) Emergency Detection System

This module implements emergency detection for The Good Bug health chatbot
based on CTAS guidelines. It detects medical emergencies and mental health
crises, providing appropriate emergency responses.
"""

from enum import Enum
from typing import Optional, Tuple
import re

# Import guardrail responses
from app.services.rag.optimized_prompts_with_guardrails import GUARDRAIL_RESPONSES


class CTASLevel(Enum):
    """Canadian Triage and Acuity Scale Levels"""
    RESUSCITATION = 1  # Immediate life-threatening
    EMERGENT = 2       # Potentially life-threatening
    URGENT = 3         # Could progress to serious
    LESS_URGENT = 4    # Related to patient distress
    NON_URGENT = 5     # Can wait for care


class EmergencyDetector:
    """
    Enhanced emergency detector with comprehensive pattern matching and fuzzy support.
    Detects medical emergencies based on CTAS guidelines from TGB Guardrails.
    Returns appropriate emergency responses with CTAS level classification.
    """
    
    def __init__(self):
        # Emergency keywords and patterns mapped to CTAS levels
        self.emergency_patterns = {
            # CTAS Level 1 - Resuscitation (Immediate)
            CTASLevel.RESUSCITATION: {
                "patterns": [
                    # Breathing/Airway emergencies - Enhanced
                    r"(?:chok(?:ing|ed?)|gagg(?:ing|ed?))\s*(?:and)?\s*(?:can'?t?|unable\s+to|cannot)\s*(?:swallow|breathe?|get\s+air)",
                    r"throat\s*(?:is\s*)?(?:closing|swelling|shutting)\s*(?:up|off)?",
                    r"(?:can'?t?|cannot|unable\s+to)\s*(?:breathe?|get\s+(?:any\s*)?air|take\s+(?:a\s*)?breath)",
                    r"(?:not\s+)?breath(?:ing|e)\s*(?:properly|well|at\s+all)",
                    r"(?:gasping|struggling)\s+(?:for\s+)?(?:air|breath|to\s+breathe)",
                    r"suffocating",
                    
                    # Swelling/Allergic reaction - Enhanced
                    r"(?:lips?|tongue|face|throat)\s*(?:and\s*)? (?:are\s*)?(?:swelling|swollen|puff(?:ing|ed)\s*up)",
                    r"(?:severe|bad|serious)\s*(?:allergic\s*)?(?:reaction|swelling)",
                    r"anaphyla(?:xis|ctic)",
                    
                    # Neurological - Enhanced
                    r"(?:slurred|garbled|unclear)\s*(?:speech|talking|words)",
                    r"(?:suddenly|very)\s*(?:confused|disoriented)",
                    r"(?:can'?t?|cannot|unable\s+to)\s*(?:feel|move)\s*(?:my\s*)?(?:legs?|arms?|body)",
                    r"(?:numb|paralyz(?:ed?|ing)|no\s+feeling)\s*(?:in\s*)?(?:my\s*)?(?:legs?|arms?|limbs?)",
                    r"(?:lost|losing)\s*(?:feeling|sensation)\s*(?:in\s*)?(?:my\s*)?(?:legs?|arms?)",
                    
                    # Poisoning - Enhanced
                    r"(?:drank|ate|swallowed|ingested|consumed)\s*(?:something\s*)?(?:poison(?:ous)?|toxic|chemical)",
                    r"(?:poison(?:ed?|ing)|toxic)\s*(?:substance|chemical)?",
                    r"(?:accidental|chemical)\s*(?:ingestion|poisoning)",
                    
                    # Fall/Trauma - Enhanced
                    r"fell\s*(?:down|off|from)?.*?(?:can'?t?|cannot)\s*(?:feel|move)",
                    r"(?:serious|bad|major)\s*(?:fall|accident|injury).*?(?:can'?t?|cannot)\s*(?:feel|move)",
                ],
                "keywords": [
                    "throat closing", "can't breathe", "cant breathe", "unable to breathe",
                    "gasping for air", "suffocating", "choking badly", "struggling to breathe",
                    "lips swelling", "tongue swelling", "face swelling", "throat swelling",
                    "anaphylaxis", "severe allergic reaction",
                    "slurred speech", "confused suddenly", "paralyzed", "can't feel legs",
                    "numb legs", "lost feeling", "no sensation",
                    "poison", "poisoned", "drank poison", "toxic substance",
                    "fell and can't feel", "fell and paralyzed"
                ],
                "category": "resuscitation",
                "response_template": "I'm really sorry to hear that you're experiencing {symptom}. This is a medical emergency that requires immediate attention. In India, call 112 (national emergency) or 108 (ambulance) or go to the nearest hospital emergency RIGHT NOW. Your life may be at risk, and every second counts. Please seek help immediately. 🚨"
            },
            
            # CTAS Level 2 - Emergent
            CTASLevel.EMERGENT: {
                "patterns": [
                    # Chest pain/Cardiac - Enhanced
                    r"(?:severe|intense|extreme|terrible|crushing|sharp)\s*(?:chest\s*)?pain(?:\s*(?:in\s*)?(?:my\s*)?chest)?",
                    r"(?:chest|heart)\s*(?:pain|hurt(?:s|ing)|ache|discomfort).*?(?:severe|intense|bad|terrible|crushing)",
                    r"(?:have|experiencing)\s*(?:severe|intense|extreme|terrible|crushing|sharp)\s*chest\s*pain",
                    r"(?:pressure|tightness|squeezing|heaviness)\s*(?:in|on)\s*(?:my\s*)?chest",
                    r"(?:heart|chest)\s*(?:feels?\s*)?(?:tight|squeezed|heavy|compressed)",
                    r"(?:elephant|weight)\s*(?:on|pressing)\s*(?:my\s*)?chest",
                    
                    # Heart rate - Enhanced
                    r"heart\s*(?:rate\s*)?(?:is\s*)?(?:extremely|very|really)\s*(?:fast|rapid|racing|pounding)",
                    r"(?:heart|pulse)\s*(?:is\s*)?(?:racing|pounding|beating\s+(?:too\s*)?fast)",
                    r"(?:palpitations?|irregular\s+heartbeat)",
                    
                    # Breathing difficulties - Enhanced
                    r"(?:can'?t?|cannot|unable\s+to)\s*(?:catch|get)\s*(?:my\s*)?breath",
                    r"(?:difficulty|trouble|hard\s+(?:time)?|struggling)\s*(?:breathing|to\s+breathe)",
                    r"(?:short|out)\s*(?:of\s*)?breath.*?(?:severe|extreme|very|really)",
                    r"(?:wheezy?|wheezing)\s*(?:and)?\s*(?:can'?t?|cannot)\s*breathe",
                    r"(?:breathing|breath)\s*(?:is\s*)?(?:very\s*)?(?:difficult|hard|labored)",
                    
                    # Abdominal pain - Enhanced
                    r"(?:intense|severe|extreme|unbearable|terrible)\s*(?:abdominal|stomach|belly|gut)\s*pain",
                    r"(?:abdominal|stomach|belly)\s*pain.*?(?:intense|severe|unbearable|terrible)",
                    r"(?:constipation|blocked).*?(?:severe|extreme|intense)\s*(?:abdominal\s*)?pain",
                    r"(?:stomach|belly|gut)\s*(?:hurt(?:s|ing)|ache).*?(?:severe|really\s+bad|terrible)",
                    
                    # Mental health - Enhanced (also in separate section)
                    r"(?:feel(?:ing)?|am)\s*(?:hopeless|desperate).*?(?:ending|end)\s*(?:my\s*)?(?:life|it\s*all)",
                    r"(?:suicid(?:al|e)|self-harm)",
                    r"(?:ending|end)\s*(?:my\s*)?(?:life|it\s*all)",
                    r"(?:kill|hurt|harm)\s*(?:my)?self",
                    r"(?:want|wish)\s*(?:to\s*)?(?:die|be\s+dead)",
                    r"(?:don'?t|do\s+not)\s*(?:want\s+to\s*)?(?:live|be\s+alive)\s*(?:anymore|any\s+more)",
                    r"(?:life|living)\s*(?:is\s*)?(?:not\s+worth|pointless|meaningless)",
                    
                    # Dehydration/Urination - Enhanced
                    r"(?:haven'?t?|have\s+not|not)\s*(?:eaten|urinated|peed).*?(?:not\s+)?(?:pass(?:ing|ed)?|producing)\s*(?:much\s*)?(?:urine|pee)",
                    r"(?:no|very\s+little)\s*(?:urine|pee).*?(?:days?|hours?)",
                    
                    # Headache - Enhanced
                    r"(?:sudden|extreme|severe|worst|intense|terrible)\s*(?:and\s*)?(?:severe\s*)?headache",
                    r"(?:headache|head\s*pain).*?(?:sudden|extreme|severe|worst|unbearable)",
                    r"(?:worst|most\s+severe)\s*headache\s*(?:of\s+)?(?:my\s*)?life",
                    
                    # Neurological symptoms - Enhanced
                    r"(?:numbness|tingling|pins\s+and\s+needles)\s*(?:and\s*)?(?:tingling|numbness)?",
                    r"(?:vision|sight)\s*(?:is\s*)?(?:blurry|blurred|double|doubled)",
                    r"(?:seeing|vision)\s*(?:double|two\s+of\s+everything)",
                    r"(?:lightheaded|dizzy|faint).*?(?:pass(?:ing)?\s*out|fainting|losing\s+consciousness)",
                    
                    # Head injury - Enhanced
                    r"(?:hit|struck|banged|bumped)\s*(?:my\s*)?head\s*(?:really|very)?\s*(?:hard|badly)",
                    r"(?:head\s*)?(?:injury|trauma).*?(?:severe|serious|bad)",
                    
                    # Seizure - Enhanced
                    r"(?:having|had|experiencing)\s*(?:a\s*)?(?:seizure|convulsion|fit)",
                    r"\b(?:seizure|convulsion|fit)\b",
                    
                    # Bleeding - Enhanced
                    r"(?:bleeding|blood).*?(?:not\s+)?(?:stopping|won'?t\s+stop|continuous|severe)",
                    r"(?:severe|heavy|uncontrolled|excessive)\s*(?:bleeding|blood\s+loss)",
                    r"(?:pregnant|pregnancy).*?(?:bleeding|blood)\s*(?:heavily|a\s+lot)",
                    r"(?:32|thirty[- ]?two)\s*weeks?\s*pregnant.*?(?:bleeding|blood)",
                    
                    # Fever - Enhanced
                    r"(?:fever|temperature).*?(?:3|three|several)\s*days.*?(?:not\s+)?(?:responding|getting\s+(?:better|worse))",
                    r"(?:high|persistent)\s*fever.*?(?:days?|not\s+improving)",
                ],
                "keywords": [
                    "severe chest pain", "crushing chest pain", "chest pressure", "tight chest", "intense chest pain",
                    "heart racing", "heart pounding", "palpitations",
                    "can't catch breath", "cant catch breath", "difficulty breathing", "trouble breathing",
                    "short of breath", "wheezing badly",
                    "intense abdominal pain", "severe stomach pain", "unbearable pain",
                    "hopeless", "suicidal", "want to die", "kill myself", "end my life",
                    "life not worth living", "don't want to live",
                    "not passing urine", "no urine", "dehydrated badly",
                    "sudden severe headache", "worst headache", "extreme headache",
                    "numbness tingling", "blurry vision", "seeing double", "double vision",
                    "lightheaded pass out", "dizzy fainting",
                    "hit head hard", "head injury", "head trauma",
                    "seizure", "convulsion", "having a fit",
                    "bleeding won't stop", "uncontrolled bleeding", "heavy bleeding",
                    "pregnant bleeding", "pregnancy bleeding",
                    "fever 3 days", "persistent fever"
                ],
                "category": "emergent",
                "response_template": "I'm really sorry to hear that you're experiencing {symptom}. These symptoms may be serious and may require immediate medical attention. In India, call 112 or 108 or go to the nearest hospital emergency right away. Your safety is the most important thing right now. 🚨"
            },
            
            # CTAS Level 3 - Urgent
            CTASLevel.URGENT: {
                "patterns": [
                    # Vomiting - Enhanced
                    r"(?:severe|constant|continuous|extreme)\s*(?:nausea\s*(?:and\s*)?)?(?:vomiting|throwing\s+up).*?(?:can'?t?|cannot)\s*(?:keep\s*)?(?:anything|food|water)\s*down",
                    r"(?:vomiting|throwing\s+up).*?(?:can'?t?|cannot|unable\s+to)\s*(?:keep|hold)\s*(?:anything|food|water)\s*down",
                    r"(?:can'?t?|cannot)\s*(?:keep|hold)\s*(?:anything|food|water)\s*down.*?(?:vomiting|throwing\s+up)",
                    
                    # Diarrhea - Enhanced
                    r"(?:diarrhea|diarrhoea|loose\s+stools).*?(?:3|three|several)\s*days.*?(?:dizzy|weak|faint)",
                    r"(?:dizzy|weak|faint).*?(?:diarrhea|diarrhoea).*?(?:3|three|several)\s*days",
                    r"(?:severe|bad|constant)\s*(?:diarrhea|diarrhoea).*?(?:days?|dehydrated)",
                    
                    # Hypoglycemia - Enhanced
                    r"(?:haven'?t?|have\s+not)\s*eaten.*?(?:dizzy|shaking|sweating|weak|faint)",
                    r"(?:dizzy|shaking|sweating|weak|faint).*?(?:haven'?t?|have\s+not)\s*eaten",
                    r"(?:hypoglycemi[ac]|low\s+blood\s+sugar)",
                    r"blood\s*sugar\s*(?:is\s*)?(?:very\s*)?(?:low|dropping|crashed)",
                    r"(?:sugar|glucose)\s*(?:level\s*)?(?:is\s*)?(?:too\s*)?low",
                    
                    # Dehydration - Enhanced
                    r"(?:dehydrat(?:ed|ion)|severely\s+thirsty)",
                    r"(?:very|extremely|severely)\s*(?:dehydrated|thirsty).*?(?:dizzy|weak|faint)",
                    r"(?:no|little)\s*(?:water|fluids?).*?(?:days?|dehydrated)",
                ],
                "keywords": [
                    "severe vomiting", "constant vomiting", "throwing up everything",
                    "can't keep anything down", "cant keep food down",
                    "diarrhea for days", "diarrhea 3 days", "severe diarrhea",
                    "dizzy and sweating", "dizzy weak", "shaking sweating",
                    "hypoglycemia", "hypoglycemic", "blood sugar low", "sugar level low",
                    "dehydrated", "dehydration", "severely dehydrated", "very thirsty"
                ],
                "category": "urgent",
                "response_template": "I'm really sorry to hear that you're experiencing {symptom}. These symptoms may be serious and may require immediate medical attention. In India, call 112 or 108 or go to the nearest hospital emergency right away. Your safety is the most important thing right now. 💚"
            }
        }
        
        # Mental health specific patterns - always CTAS Level 2 - Enhanced
        self.mental_health_patterns = [
            r"suicid(?:al|e)",
            r"(?:kill|hurt|harm)\s*(?:my)?self",
            r"end(?:ing)?\s*(?:my\s*)?(?:life|it\s*all)",
            r"(?:want|wish)\s*(?:to\s*)?(?:die|be\s+dead)",
            r"(?:don'?t|do\s+not)\s*(?:want\s+to\s*)?(?:live|be\s+alive)\s*(?:anymore|any\s+more)",
            r"self[\s-]?harm(?:ing)?",
            r"hurt(?:ing)?\s*(?:my)?self\s*(?:intentionally|on\s+purpose)",
            r"(?:feel(?:ing)?|am)\s*(?:hopeless|desperate).*?(?:no|don'?t)\s*(?:see\s*)?(?:a\s*)?(?:point|reason|way|hope)",
            r"(?:life|living)\s*(?:is\s*)?(?:not\s+worth|pointless|meaningless|unbearable)",
            r"(?:better\s+off|everyone\s+would\s+be\s+better)\s*(?:if\s+)?(?:I\s+(?:was|were)\s+)?(?:dead|gone)",
            r"(?:thinking\s+(?:about|of)|planning)\s*(?:ending|suicide|killing\s+myself)",
        ]
        
        self.mental_health_response = GUARDRAIL_RESPONSES["mental_health_crisis"]

    def detect_emergency(self, message: str) -> Tuple[bool, Optional[CTASLevel], Optional[str], Optional[str]]:
        """
        Enhanced emergency detection with safe-word filtering and robust matching.
        
        Returns:
            Tuple of (is_emergency, ctas_level, category, response)
        """
        message_lower = message.lower().strip()
        
        # SAFE WORD PROTECTION: If the message is a common positive/safe status or a known survey option, skip detection
        safe_messages = [
            # Hydration survey
            "well hydrated", "hydrated", "sip occasionally", "only after", "often dehydrated",
            # Movement survey
            "yoga/twists", "walking", "core work", "none",
            # Digestive comfort survey
            "good", "bloated/gassy", "heavy", "acidic/heartburn", "sleepy", "normal",
            # General status
            "feeling good", "steady", "well", "okay", "fine", 
            "nothing to report", "balanced", "regular", "no issues"
        ]
        if message_lower in safe_messages:
            return (False, None, None, None)
            
        # Normalize common typos and variations
        message_normalized = self._normalize_text(message_lower)
        
        # First check for mental health emergencies
        for pattern in self.mental_health_patterns:
            if re.search(pattern, message_normalized, re.IGNORECASE):
                return (True, CTASLevel.EMERGENT, "mental_health_distress", self.mental_health_response)
        
        # Check other emergency patterns by severity
        for ctas_level in [CTASLevel.RESUSCITATION, CTASLevel.EMERGENT, CTASLevel.URGENT]:
            level_data = self.emergency_patterns[ctas_level]
            
            # Check regex patterns
            for pattern in level_data["patterns"]:
                if re.search(pattern, message_normalized, re.IGNORECASE):
                    symptom = self._extract_symptom(message)
                    response = level_data["response_template"].format(symptom=symptom)
                    return (True, ctas_level, level_data["category"], response)
            
            # Check keywords with STRICTER fuzzy matching
            for keyword in level_data["keywords"]:
                if self._robust_keyword_match(keyword.lower(), message_normalized):
                    symptom = self._extract_symptom(message)
                    response = level_data["response_template"].format(symptom=symptom)
                    return (True, ctas_level, level_data["category"], response)
        
        return (False, None, None, None)
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text to handle common typos and variations"""
        # Common typo corrections
        typo_map = {
            r'\bbreth\b': 'breath',
            r'\bbreathing\b': 'breathe',
            r'\bcant\b': "can't",
            r'\bdont\b': "don't",
            r'\bwont\b': "won't",
            r'\bdidnt\b': "didn't",
            r'\bhavent\b': "haven't",
            r'\bisnt\b': "isn't",
            r'\barent\b': "aren't",
            r'\bcouldnt\b': "couldn't",
            r'\bwouldnt\b': "wouldn't",
            r'\bshouldnt\b': "shouldn't",
            r'\bchocking\b': 'choking',
            r'\bswolling\b': 'swelling',
            r'\bpoisining\b': 'poisoning',
            r'\bdiarea\b': 'diarrhea',
            r'\bdiarrea\b': 'diarrhea',
            r'\bdiarehea\b': 'diarrhea',
            r'\bvomitting\b': 'vomiting',
            r'\bthrowin\s+up\b': 'throwing up',
            r'\bsiezure\b': 'seizure',
        }
        
        normalized = text
        for pattern, replacement in typo_map.items():
            normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)
        
        return normalized
    
    def _robust_keyword_match(self, keyword: str, text: str) -> bool:
        """
        Improved keyword matching that handles typos without over-matching.
        """
        # 1. Direct whole-phrase match - safest and fastest
        if keyword in text:
            # For "dehydrated", ensure it's not "well hydrated"
            if keyword == "dehydrated" and "well hydrated" in text:
                return False
            return True
        
        # 2. Support for multi-word phrases (e.g., "short of breath")
        keyword_words = keyword.split()
        if len(keyword_words) > 1:
            # Check if all key words from the phrase are in the text
            # (ignoring small filler words like 'of', 'and', 'the')
            main_words = [w for w in keyword_words if len(w) > 2]
            return all(re.search(r'\b' + re.escape(w) + r'\b', text, re.IGNORECASE) for w in main_words)
        
        # 3. Typo tolerance for single-word keywords
        # Use simple edit distance to catch single-character typos
        keyword_len = len(keyword)
        if keyword_len < 4:
            # No fuzzy matching for very short words
            return re.search(r'\b' + re.escape(keyword) + r'\b', text, re.IGNORECASE) is not None
            
        for word in text.split():
            # Strip punctuation for cleaner comparison
            word_clean = re.sub(r'[^\w]', '', word)
            if not word_clean:
                continue
                
            # SPECIAL CASE: "hydrated" and "dehydrated"
            if keyword == "dehydrated" and word_clean == "hydrated":
                continue
                
            # If length is very different, skip
            if abs(len(word_clean) - keyword_len) > 2:
                continue
                
            # Calculate simple Levenshtein distance
            dist = self._levenshtein_distance(keyword, word_clean)
            
            # Allow max 1 edit for words up to 6 chars, 2 edits for longer words
            max_dist = 1 if keyword_len <= 6 else 2
            if dist <= max_dist:
                return True
                
        return False
        
    def _levenshtein_distance(self, s1: str, s2: str) -> int:
        """Simple Levenshtein distance calculation"""
        if len(s1) < len(s2):
            return self._levenshtein_distance(s2, s1)

        if not s2:
            return len(s1)

        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row

        return previous_row[-1]
    
    def _extract_symptom(self, message: str) -> str:
        """Extract a clean symptom description from the message"""
        symptom = message.strip()
        symptom = re.sub(r'\?+$', '', symptom)
        symptom = re.sub(r'^(I\'?m\s*|I\s*am\s*|I\s*have\s*|I\s*feel\s*)', '', symptom, flags=re.IGNORECASE)
        if len(symptom) > 100:
            symptom = symptom[:100] + "..."
        return symptom.lower()
