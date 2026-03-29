"""
Knowledge Completeness Checker Module

This module assesses the completeness of knowledge retrieved from documents
for answering user questions in The Good Bug health chatbot.
"""

from typing import List, Dict, Any
import re


class KnowledgeCompletenessChecker:
    def assess_knowledge_completeness(self, documents: List[Any], question: str, product_info: Dict) -> Dict[str, Any]:
        question_type = product_info.get("question_type", "general")
        product_name = product_info.get("product_name")
        
        if not product_name:
            return {
                "insufficient_knowledge": False,
                "confidence_impact": "none",
                "product_specific_docs_found": 0,
                "relevance_score": 0.5,
                "recommendation": "proceed"
            }
        
        product_specific_docs = 0
        total_relevance_score = 0
        high_quality_docs = 0
        
        for doc in documents:
            if self._doc_mentions_product(doc, product_name):
                product_specific_docs += 1
                relevance_score = self._calculate_info_relevance(doc, question_type, product_name)
                total_relevance_score += relevance_score
                if relevance_score > 0.7:
                    high_quality_docs += 1
        
        insufficient_knowledge = False
        confidence_impact = "none"
        
        if product_specific_docs == 0:
            insufficient_knowledge = True
            confidence_impact = "major"
        elif question_type in ["ingredients", "dosage", "timing"] and high_quality_docs == 0:
            insufficient_knowledge = True  
            confidence_impact = "moderate"
        elif total_relevance_score < 0.4:
            insufficient_knowledge = True
            confidence_impact = "moderate"
        elif question_type in ["ingredients", "dosage"] and total_relevance_score < 0.6:
            insufficient_knowledge = True
            confidence_impact = "moderate"
        
        return {
            "insufficient_knowledge": insufficient_knowledge,
            "confidence_impact": confidence_impact,
            "product_specific_docs_found": product_specific_docs,
            "relevance_score": total_relevance_score / max(len(documents), 1),
            "recommendation": "contact_expert" if insufficient_knowledge else "proceed",
            "high_quality_docs": high_quality_docs
        }
    
    def _doc_mentions_product(self, doc: Any, product_name: str) -> bool:
        content_lower = doc.page_content.lower()
        product_lower = product_name.lower()
        
        if product_lower in content_lower:
            return True
        
        abbrev_map = {
            "metabolically lean ams": ["ams", "advanced metabolic system", "metabolic system"],
            "metabolically lean supercharged": ["supercharged", "met lean supercharged"],
            "pcos balance": ["pcos", "pcod"],
            "ibs rescue": ["ibs c", "ibs constipation"],
            "ibs dnm": ["ibs d", "ibs m", "ibs diarrhea", "ibs mixed", "ibs d&m"],
            "gut balance": ["gut balance"],
            "bye bye bloat": ["bloat", "bloating"],
            "smooth move": ["constipation", "smooth move"],
            "good down there": ["feminine", "vaginal", "uti", "urinary"],
            "sleep and calm": ["sleep", "melatonin"],
            "first defense": ["immunity", "immune", "first defence"],
            "good to glow": ["skin", "glow", "hair", "nails"],
            "happy tummies": ["kids", "children"],
            "acidity aid": ["acidity", "heartburn"],
            "gut cleanse": ["cleanse", "detox"],
            "metabolic fiber boost": ["metabolic fiber"],
            "smooth move fiber boost": ["smooth fiber"],
            "prebiotic fiber boost": ["prebiotic fiber"],
            "water kefir": ["kefir"],
            "kombucha": ["kombucha"]
        }
        
        if product_lower in abbrev_map:
            return any(abbrev in content_lower for abbrev in abbrev_map[product_lower])
        
        return False
    
    def _calculate_info_relevance(self, doc: Any, question_type: str, product_name: str) -> float:
        content_lower = doc.page_content.lower()
        product_lower = product_name.lower()
        
        relevance_keywords = {
            "ingredients": ["ingredients", "contains", "composition", "blend", "formula", "made of", "includes"],
            "dosage": ["dosage", "serving", "scoop", "sachet", "how much", "take", "daily", "dose", "consumption"],
            "timing": ["timing", "when", "before", "after", "morning", "evening", "schedule", "time"],
            "benefits": ["benefits", "helps", "supports", "improves", "reduces", "good for", "relief"],
            "safety": ["safe", "side effects", "caution", "avoid", "consult", "interaction", "warning", "pregnant"],
            "comparison": ["difference", "vs", "versus", "compare", "better", "similar", "different"]
        }
        
        if question_type not in relevance_keywords:
            return 0.5
        
        keywords = relevance_keywords[question_type]
        keyword_matches = sum(1 for keyword in keywords if keyword in content_lower)
        base_relevance = min(keyword_matches / len(keywords), 1.0)
        
        if product_lower in content_lower:
            for keyword in keywords:
                if keyword in content_lower:
                    product_pos = content_lower.find(product_lower)
                    keyword_pos = content_lower.find(keyword)
                    if abs(product_pos - keyword_pos) < 200:
                        base_relevance = min(base_relevance + 0.3, 1.0)
                        break
        
        return base_relevance
