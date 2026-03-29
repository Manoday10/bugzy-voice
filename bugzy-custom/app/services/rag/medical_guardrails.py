"""
Medical Guardrails System

This module implements comprehensive medical guardrails for The Good Bug health chatbot
based on TGB Guardrails document. It detects and handles:
- Prescription drug queries
- Disease management questions
- High-risk health conditions
- Gut coach connection requests
"""

from typing import Dict, Any, List, Optional, Tuple
import re

# Import guardrail responses
from app.services.rag.optimized_prompts_with_guardrails import GUARDRAIL_RESPONSES


class MedicalGuardrails:
    """
    Comprehensive medical guardrails based on TGB Guardrails document.
    """
    
    def __init__(self):
        self.prescription_drug_response = GUARDRAIL_RESPONSES["prescription_drug"]
        self.disease_management_response = GUARDRAIL_RESPONSES["disease_management"]
        
        # High-risk conditions requiring physician consultation
        self.high_risk_conditions = {
            "nutrition": {
                "conditions": [
                    "kidney disease", "ckd", "chronic kidney disease", "renal disease",
                    "liver disease", "cirrhosis", "hepatitis", "fatty liver",
                    "transplant", "organ transplant", "kidney transplant", "liver transplant",
                    "ibd", "inflammatory bowel disease", "crohn", "ulcerative colitis",
                    "recent gi surgery", "short bowel syndrome", "bowel resection",
                    "pku", "phenylketonuria", "galactosemia", "metabolic disorder",
                    "severe food allergies", "anaphylaxis history",
                    "immunosuppressive therapy", "chemotherapy", "post-transplant",
                    "dialysis"
                ],
                "response": GUARDRAIL_RESPONSES["nutrition_high_risk"]
            },
            "fitness": {
                "conditions": [
                    "cardiac condition", "heart condition", "heart disease",
                    "uncontrolled hypertension", "high blood pressure uncontrolled",
                    "arrhythmia", "irregular heartbeat", "heart failure",
                    "severe asthma", "copd", "chronic obstructive pulmonary",
                    "respiratory condition", "lung disease",
                    "uncontrolled diabetes", "frequent hypoglycemia",
                    "diabetic complications"
                ],
                "response": GUARDRAIL_RESPONSES["fitness_high_risk"]
            },
            "surgery": {
                "conditions": [
                    "recent surgery", "post surgery", "post-surgical",
                    "bariatric surgery", "gastric bypass", "gastric sleeve",
                    "gi resection", "stoma", "colostomy", "ileostomy",
                    "surgery in last 6 months", "surgery in last 3 months"
                ],
                "response": GUARDRAIL_RESPONSES["surgery_recent"]
            },
            "injury": {
                "conditions": [
                    "recent fracture", "broken bone", "ligament tear",
                    "acl tear", "mcl tear", "spinal issue", "back injury",
                    "post-injury recovery", "physical therapy",
                    "orthopedic condition"
                ],
                "response": GUARDRAIL_RESPONSES["injury_recovery"]
            },
            "medication": {
                "conditions": [
                    "anticoagulant", "blood thinner", "warfarin", "coumadin", "heparin",
                    "immunosuppressant", "prednisone", "cyclosporine",
                    "antiepileptic", "seizure medication", "anticonvulsant",
                    "lithium", "narrow therapeutic index",
                    "dual therapy", "multiple medications",
                    "chemotherapy drugs", "cancer treatment"
                ],
                "response": GUARDRAIL_RESPONSES["medication_interaction"]
            }
        }
        
        # Prescription drug patterns - Enhanced with word boundaries (PRIORITY 3 FIX)
        self.prescription_drug_patterns = [
            # Diabetes medications
            r"\b(metformin|glucophage|insulin|glipizide|glimepiride|glyburide|januvia|victoza|ozempic|trulicity)\b",
            # Blood thinners
            r"\b(warfarin|coumadin|heparin|eliquis|xarelto|pradaxa|apixaban|rivaroxaban|dabigatran)\b",
            # Blood pressure medications
            r"\b(lisinopril|amlodipine|losartan|atenolol|metoprolol|carvedilol|valsartan|enalapril|ramipril)\b",
            # Cholesterol medications
            r"\b(atorvastatin|simvastatin|rosuvastatin|lipitor|crestor|pravastatin|lovastatin)\b",
            # Acid reflux medications
            r"\b(omeprazole|pantoprazole|esomeprazole|lansoprazole|nexium|prilosec|protonix)\b",
            # Antidepressants/Anxiety
            r"\b(sertraline|fluoxetine|escitalopram|citalopram|prozac|zoloft|lexapro|paxil|wellbutrin|cymbalta)\b",
            r"\b(alprazolam|lorazepam|diazepam|clonazepam|xanax|valium|ativan|klonopin)\b",
            # Steroids - ADD BETTER CONTEXT to avoid confusion with "inflammation" keyword
            r"\b(?:on|taking|prescribed|taking)\s+(?:prednisone|prednisolone|dexamethasone|methylprednisolone|hydrocortisone)\b",
            r"\b(prednisone|prednisolone|dexamethasone|methylprednisolone|hydrocortisone)\b(?:\s+(?:for|medication|prescription|treatment))?",
            # Thyroid medications
            r"\b(levothyroxine|synthroid|armour\s+thyroid|cytomel|liothyronine)\b",
            # Immunosuppressants
            r"\b(methotrexate|humira|remicade|enbrel|adalimumab|infliximab|etanercept|azathioprine)\b",
            # Pain medications
            r"\b(gabapentin|pregabalin|lyrica|neurontin)\b",
            r"\b(oxycodone|hydrocodone|tramadol|morphine|codeine|fentanyl|percocet|vicodin)\b",
            # Antibiotics
            r"\b(amoxicillin|azithromycin|ciprofloxacin|doxycycline|penicillin|cephalexin)\b",
            # General prescription terms - Enhanced
            r"\bprescription\s+(?:drug|medication|medicine|med|pill)s?\b",
            r"\b(?:doctor|physician|dr\.?)\s+(?:prescribed|gave\s+me|put\s+me\s+on)\b",
            r"\b(?:prescribed|taking|on)\s+(?:medication|medicine|drug|pill)s?\b",
            r"\bRx\s+(?:drug|medication|medicine)\b",
            r"\b(?:my|taking)\s+(?:meds?|pills?|medication|medicine)\b",
            r"(?:interact|interfere)\s+(?:with\s+)?(?:my\s+)?(?:medication|medicine|prescription|meds)",
        ]
        
        # Disease management patterns - Enhanced with more conditions (PRIORITY 2 FIX)
        self.disease_management_patterns = [
            # Treatment/Cure questions - General patterns
            r"(?:treat|cure|heal|fix|manage|reverse|eliminate|get\s+rid\s+of)\s*(?:my\s*)?(?:disease|condition|diabetes|cancer|heart|kidney|liver|crohn|ibs|uti|pcos|autoimmune)",
            
            # Disease-specific patterns (expanded list)
            r"(?:will|can)\s*(?:this|it|your\s+product)?\s*(?:treat|cure|reverse|heal|fix|eliminate|get\s+rid\s+of)\s*(?:my\s*)?(?:crohn|ibs|uti|pcos|fatty\s+liver|hepatitis|cirrhosis)",
            
            # Treatment claims
            r"(?:is|does|will|can)\s*(?:this|it|your\s+product)\s*(?:cure|treat|heal|fix|reverse)\s*(?:my\s*)?(?:diabetes|cancer|disease|condition|crohn|ibs|uti)",
            
            # Instead of medication
            r"(?:instead\s+of|rather\s+than|replace|substitute|use.*instead|swap.*for)\s*(?:my\s*)?(?:medication|medicine|prescription|treatment|meds|pills)",
            
            # Can I stop/discontinue medication
            r"(?:stop|quit|discontinue|come\s+off|replace)\s*(?:my\s*)?(?:medication|medicine|prescription|meds|pills)",
            
            # General disease management
            r"(?:can\s+)?(?:your\s+)?product\s*(?:help\s+)?(?:treat|manage|control|reverse)\s*(?:my\s+)?(?:disease|condition|diabetes|cancer|kidney|liver|heart|crohn|ibs|uti|pcos)",
            
            # Manage + disease name
            r"(?:manage|control|treat)\s*(?:my\s*)?(?:diabetes|cancer|kidney\s*disease|liver\s*disease|crohn|crohn's|ibs|irritable\s+bowel|uti|pcos|heart\s*disease|autoimmune|condition)",
        ]
        
        # Gut coach / Health professional connection patterns
        self.gut_coach_connection_patterns = [
            # Direct requests to speak with coach/professional
            r"(?:talk|speak|connect|chat)\s+(?:to|with)\s+(?:a\s+)?(?:gut\s+)?(?:coach|health\s+coach|professional|expert|specialist|nutritionist|dietitian)",
            r"(?:can\s+i|i\s+want\s+to|i'd\s+like\s+to|i\s+need\s+to)\s+(?:talk|speak|connect|chat)\s+(?:to|with)\s+(?:a\s+)?(?:gut\s+)?(?:coach|health\s+coach|professional|expert|specialist)",
            
            # Requests for human assistance
            r"(?:connect\s+me|put\s+me\s+in\s+touch)\s+(?:with|to)\s+(?:a\s+)?(?:gut\s+)?(?:coach|health\s+coach|professional|expert|specialist|human|person|nutritionist|real\s+person)",
            r"(?:speak|talk)\s+(?:to|with)\s+(?:a\s+)?(?:real\s+)?(?:person|human|coach|expert|professional)",
            r"(?:talk|speak)\s+(?:to|with)\s+(?:someone|anybody|anyone)",
            
            # Need help from professional - more flexible
            r"(?:need|want)\s+(?:help|guidance|advice|support)\s+(?:from|by)\s+(?:a\s+)?(?:gut\s+health\s+expert|gut\s+health\s+coach|gut\s+coach|health\s+coach|professional|expert|specialist)",
            r"(?:get|have)\s+(?:a\s+)?(?:gut\s+health\s+expert|gut\s+health\s+coach|gut\s+coach|health\s+coach|professional|expert)\s+(?:help|assist|guide)\s+me",
            
            # Contact/reach out to professional
            r"(?:contact|reach|call)\s+(?:a\s+)?(?:gut\s+)?(?:coach|health\s+coach|professional|expert|specialist|nutritionist)",
            r"(?:how\s+(?:do\s+i|can\s+i)|where\s+can\s+i)\s+(?:contact|reach|find|get)\s+(?:a\s+)?(?:gut\s+)?(?:coach|health\s+coach|professional|expert)",
            
            # Phone number requests
            r"(?:phone|contact)\s+(?:number|details)\s+(?:for|of)\s+(?:a\s+)?(?:gut\s+)?(?:coach|health\s+coach|professional|expert)",
            r"(?:give|share|provide)\s+(?:me\s+)?(?:the\s+)?(?:phone|contact)\s+(?:number|details)\s+(?:for|of)\s+(?:a\s+)?(?:coach|professional|expert)",
            
            # Schedule/book with professional
            r"(?:schedule|book|arrange)\s+(?:a\s+)?(?:call|session|consultation|appointment)\s+(?:with|to)\s+(?:a\s+)?(?:gut\s+)?(?:coach|health\s+coach|professional|expert)",
            
            # Connect me patterns (more flexible)
            r"connect\s+me\s+(?:with|to)\s+(?:a\s+)?(?:nutritionist|expert|specialist|health\s+expert|gut\s+health\s+expert)",
            
            # Speak/talk with patterns (more flexible to catch "Can I speak with a health professional")
            r"(?:can\s+i|could\s+i|may\s+i)\s+(?:speak|talk)\s+(?:with|to)\s+(?:a\s+)?(?:health\s+)?(?:professional|expert|specialist|coach)",
            
            # Put me in touch patterns
            r"put\s+me\s+in\s+touch\s+(?:with|to)\s+(?:a\s+)?(?:real\s+)?(?:person|human|coach|professional|expert)",
        ]
        
        self.gut_coach_response = GUARDRAIL_RESPONSES["gut_coach_connection"]

    def check_guardrails(self, message: str, health_context: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[str]]:
        """Check all guardrails against the message and health context."""
        message_lower = message.lower()
        
        # Check for gut coach / health professional connection requests
        for pattern in self.gut_coach_connection_patterns:
            if re.search(pattern, message_lower, re.IGNORECASE):
                return (True, "gut_coach_connection", self.gut_coach_response)
        
        # Check for prescription drug queries
        for pattern in self.prescription_drug_patterns:
            if re.search(pattern, message_lower, re.IGNORECASE):
                return (True, "prescription_drug", self.prescription_drug_response)
        
        # Check for disease management queries
        for pattern in self.disease_management_patterns:
            if re.search(pattern, message_lower, re.IGNORECASE):
                return (True, "disease_management", self.disease_management_response)
        
        # Check health context for high-risk conditions (IMPROVED MATCHING - PRIORITY 1 FIX)
        health_info = self._compile_health_info(health_context)
        combined_text = message_lower + " " + health_info  # Check both message and health context
        
        for category, data in self.high_risk_conditions.items():
            for condition in data["conditions"]:
                # Use word boundary regex for more accurate matching
                pattern = r"\b" + re.escape(condition) + r"\b"
                if re.search(pattern, combined_text, re.IGNORECASE):
                    return (True, f"high_risk_{category}", data["response"])
        
        return (False, None, None)
    
    def _compile_health_info(self, health_context: Dict[str, Any]) -> str:
        """Compile all health information into a single searchable string"""
        parts = []
        for key in ["health_conditions", "allergies", "medications", "supplements", "gut_health"]:
            if health_context.get(key):
                parts.append(health_context[key].lower())
        return " ".join(parts)
    
    def get_condition_specific_warning(self, health_context: Dict[str, Any]) -> List[str]:
        """Generate specific warnings based on health context"""
        warnings = []
        health_info = self._compile_health_info(health_context)
        
        for category, data in self.high_risk_conditions.items():
            for condition in data["conditions"]:
                if condition in health_info:
                    warnings.append(f"⚠️ Due to your {condition}, {data['response']}")
                    break
        
        return warnings
