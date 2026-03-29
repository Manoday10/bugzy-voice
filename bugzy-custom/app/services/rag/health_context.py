"""
Health Context Extraction Module

This module extracts and formats health context information from user questions
for The Good Bug health chatbot.
"""

from typing import Dict, Any


class HealthContextExtractor:
    """Extract and parse health context from questions"""
    
    @staticmethod
    def extract_health_context(question: str) -> Dict[str, Any]:
        """Extract health-related information from the question - IMPROVED (PRIORITY 3 FIX)"""
        lines = question.strip().split('\n')
        
        health_context = {
            "health_conditions": "",
            "allergies": "",
            "medications": "",
            "supplements": "",
            "gut_health": "",
            "actual_question": question
        }
        
        question_lines = []
        
        for i, line in enumerate(lines):
            line_lower = line.lower().strip()
            
            # Improved parsing with multiple keyword variations
            if line_lower.startswith("health condition") or line_lower.startswith("condition"):
                health_context["health_conditions"] = line.split(":", 1)[1].strip() if ":" in line else ""
            elif line_lower.startswith("allergies") or line_lower.startswith("allergy"):
                health_context["allergies"] = line.split(":", 1)[1].strip() if ":" in line else ""
            elif line_lower.startswith("medications") or line_lower.startswith("medication"):
                health_context["medications"] = line.split(":", 1)[1].strip() if ":" in line else ""
            elif line_lower.startswith("supplements") or line_lower.startswith("supplement"):
                health_context["supplements"] = line.split(":", 1)[1].strip() if ":" in line else ""
            elif line_lower.startswith("gut health"):
                health_context["gut_health"] = line.split(":", 1)[1].strip() if ":" in line else ""
            elif line_lower.startswith("user's purchased product"):
                health_context["purchased_product"] = line.split(":", 1)[1].strip() if ":" in line else ""
            else:
                # This is part of the question
                question_lines.append(line)
        
        if question_lines:
            health_context["actual_question"] = "\n".join(question_lines).strip()
        
        return health_context
    
    @staticmethod
    def format_health_context_for_prompt(health_context: Dict[str, Any]) -> str:
        """Format health context for inclusion in prompts"""
        context_parts = []
        
        if health_context.get("health_conditions") and \
           health_context["health_conditions"].lower() not in ["none", "no", "nothing", "n/a", "na", ""]:
            context_parts.append(f"🏥 Health Conditions: {health_context['health_conditions']}")
        
        if health_context.get("allergies") and \
           health_context["allergies"].lower() not in ["none", "no", "nothing", "n/a", "na", ""]:
            context_parts.append(f"⚠️ Allergies: {health_context['allergies']}")
        
        if health_context.get("medications") and \
           health_context["medications"].lower() not in ["none", "no", "nothing", "n/a", "na", ""]:
            context_parts.append(f"💊 Current Medications: {health_context['medications']}")
        
        if health_context.get("supplements") and \
           health_context["supplements"].lower() not in ["none", "no", "nothing", "n/a", "na", ""]:
            context_parts.append(f"🌿 Current Supplements: {health_context['supplements']}")
        
        if health_context.get("gut_health") and \
           health_context["gut_health"].lower() not in ["none", "no", "nothing", "n/a", "na", ""]:
            context_parts.append(f"🦠 Gut Health Issues: {health_context['gut_health']}")
        
        if health_context.get("purchased_product"):
            context_parts.append(f"🛍️ Purchased Product: {health_context['purchased_product']}")
        
        if context_parts:
            return "📋 USER HEALTH PROFILE:\n" + "\n".join(context_parts) + "\n"
        
        return ""
