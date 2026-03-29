"""
QA Chain Module

This module contains the core QA chain logic with product-specific retrieval
for The Good Bug health chatbot.
"""

from typing import List, Dict, Any, Optional
import re
from langchain_core.prompts import PromptTemplate
import logging

logger = logging.getLogger(__name__)

# Import from other modules
from app.services.rag.emergency_detection import EmergencyDetector, CTASLevel
from app.services.rag.medical_guardrails import MedicalGuardrails
from app.services.rag.health_context import HealthContextExtractor
from app.services.rag.product_validator import ProductSpecificValidator
from app.services.rag.knowledge_checker import KnowledgeCompletenessChecker
from app.services.rag.models import response_parser
from app.services.rag.optimized_prompts_with_guardrails import get_model_specific_prompt


class OptimizedProductSpecificRetrievalQA:
    def __init__(self, llm, retriever, model_type="llama", return_source_documents=True):
        self.llm = llm
        self.retriever = retriever
        self.model_type = model_type
        self.return_source_documents = return_source_documents
        self.product_validator = ProductSpecificValidator()
        self.knowledge_checker = KnowledgeCompletenessChecker()
        self.health_extractor = HealthContextExtractor()
        self.emergency_detector = EmergencyDetector()
        self.medical_guardrails = MedicalGuardrails()
        self.prompt_template = get_model_specific_prompt(model_type)

    @classmethod
    def from_chain_type(cls, llm, chain_type, retriever, model_type="llama", return_source_documents=True, chain_type_kwargs=None):
        return cls(llm=llm, retriever=retriever, model_type=model_type, return_source_documents=return_source_documents)

    def invoke(self, inputs):
        question = inputs.get("query") if isinstance(inputs, dict) else str(inputs)
        
        # Extract health context
        health_context = self.health_extractor.extract_health_context(question)
        actual_question = health_context["actual_question"]
        
        # =====================================================
        # GUARDRAIL CHECK 1: Emergency Detection (CTAS)
        # =====================================================
        is_emergency, ctas_level, emergency_category, emergency_response = \
            self.emergency_detector.detect_emergency(actual_question)
        
        if is_emergency:
            return {
                "result": emergency_response,
                "product_identified": None,
                "knowledge_completeness": {"insufficient_knowledge": False},
                "model_type": self.model_type,
                "health_context_considered": True,
                "health_warnings": [],
                "guardrail_triggered": True,
                "guardrail_type": "emergency",
                "ctas_level": ctas_level.value if ctas_level else None,
                "emergency_category": emergency_category
            }
        
        # =====================================================
        # GUARDRAIL CHECK 2: Medical Guardrails
        # =====================================================
        guardrail_triggered, guardrail_type, guardrail_response = \
            self.medical_guardrails.check_guardrails(actual_question, health_context)
        
        # FIX PRIORITY 1: Include high-risk conditions and order tracking in guardrail check
        if guardrail_triggered and (guardrail_type in ["prescription_drug", "disease_management", "order_tracking"] 
                                   or guardrail_type.startswith("high_risk_")):
            return {
                "result": guardrail_response,
                "product_identified": None,
                "knowledge_completeness": {"insufficient_knowledge": False},
                "model_type": self.model_type,
                "health_context_considered": True,
                "health_warnings": [],
                "guardrail_triggered": True,
                "guardrail_type": guardrail_type
            }
        
        # =====================================================
        # NORMAL PROCESSING (with high-risk warnings appended)
        # =====================================================
        
        product_info = self._extract_product_info(actual_question, health_context)
        
        health_warnings = []
        if product_info["product_name"]:
            health_warnings = self.product_validator.check_health_contraindications(
                product_info["product_name"], 
                health_context
            )
        
        condition_warnings = self.medical_guardrails.get_condition_specific_warning(health_context)
        health_warnings.extend(condition_warnings)
        
        documents = self._retrieve_product_specific_docs(actual_question, product_info)
        filtered_documents = self._filter_product_specific_docs(documents, product_info)
        
        knowledge_assessment = self.knowledge_checker.assess_knowledge_completeness(
            filtered_documents, actual_question, product_info
        )
        
        context = self._create_product_focused_context(
            filtered_documents, product_info, knowledge_assessment, health_context, health_warnings
        )
        
        knowledge_status = self._format_knowledge_assessment(knowledge_assessment)
        
        prompt = PromptTemplate(
            template=self.prompt_template,
            input_variables=["context", "question", "knowledge_assessment", "format_instructions"],
        )
        
        formatted_prompt = prompt.format(
            context=context,
            question=actual_question, 
            knowledge_assessment=knowledge_status,
            format_instructions=self._get_format_instructions()
        )
        
        response = self.llm.invoke(formatted_prompt)
        text = getattr(response, "content", None) or str(response)
        text = self._clean_model_response(text)
        
        if health_warnings:
            text = text + "\n\n" + "\n".join(health_warnings)
        
        output = {
            "result": text,
            "product_identified": product_info.get("product_name"),
            "knowledge_completeness": knowledge_assessment,
            "model_type": self.model_type,
            "health_context_considered": bool(any([
                health_context.get("health_conditions"),
                health_context.get("allergies"),
                health_context.get("medications"),
                health_context.get("supplements"),
                health_context.get("gut_health")
            ])),
            "health_warnings": health_warnings,
            "guardrail_triggered": False
        }
        
        if self.return_source_documents:
            output["source_documents"] = filtered_documents
        
        return output
    
    def _extract_product_info(self, question: str, health_context: Dict = None) -> Dict[str, Any]:
        # Use actual_question from health_context if available to avoid matching context headers
        search_text = health_context.get("actual_question", question) if health_context else question
        question_lower = search_text.lower()
        identified_product = None
        max_length = 0
        
        for alias, product_name in self.product_validator.product_aliases.items():
            if alias in question_lower and len(alias) > max_length:
                identified_product = product_name
                max_length = len(alias)
        
        # If no product found in question, check purchased product context
        if not identified_product and health_context and health_context.get("purchased_product"):
            purchased = health_context.get("purchased_product")
            # Extract basic product name if it has extra info (like " (Ordered on...")
            purchased_clean = purchased.split("(")[0].strip()
            
            # Verify it's a valid product
            for alias, product_name in self.product_validator.product_aliases.items():
                if alias in purchased_clean.lower():
                     identified_product = product_name
                     logger.info("Using purchased product context: %s", identified_product)
                     break
        
        return {
            "product_name": identified_product,
            "question_type": self._classify_question_type(question),
            "product_info": self.product_validator.get_product_info(identified_product) if identified_product else None
        }
    
    def _classify_question_type(self, question: str) -> str:
        question_lower = question.lower()
        
        if any(word in question_lower for word in ["ingredient", "contain", "composition", "what's in", "made of", "formula"]):
            return "ingredients"
        elif any(word in question_lower for word in ["dosage", "how much", "serving", "take", "dose", "how many"]):
            return "dosage"
        elif any(word in question_lower for word in ["timing", "when", "schedule", "time", "before", "after"]):
            return "timing"
        elif any(word in question_lower for word in ["benefit", "help", "effect", "work", "good for", "use"]):
            return "benefits"
        elif any(word in question_lower for word in ["side effect", "safe", "interaction", "caution", "warning", "pregnant", "diabetes"]):
            return "safety"
        elif any(word in question_lower for word in ["difference", "vs", "versus", "compare", "better"]):
            return "comparison"
        else:
            return "general"
    
    def _retrieve_product_specific_docs(self, question: str, product_info: Dict) -> List[Any]:
        if product_info["product_name"]:
            enhanced_queries = [
                f"{product_info['product_name']} {question}",
                f"TGB-{product_info['product_name'].replace(' ', '')} {product_info['question_type']}",
                f"{product_info['product_name']} ingredients dosage benefits",
                question
            ]
            
            all_documents = []
            for query in enhanced_queries:
                try:
                    docs = self.retriever.invoke(query, search_kwargs={"k": 4})
                    all_documents.extend(docs)
                except:
                    continue
            
            unique_docs = self._remove_duplicate_docs(all_documents)
            return unique_docs[:10]
        else:
            return self.retriever.invoke(question, search_kwargs={"k": 6})
    
    def _filter_product_specific_docs(self, docs: List[Any], product_info: Dict) -> List[Any]:
        if not product_info["product_name"]:
            return docs
        
        product_name = product_info["product_name"]
        product_specific_docs = []
        
        for doc in docs:
            if self._is_product_specific_doc(doc, product_name):
                product_specific_docs.append(doc)
        
        if not product_specific_docs:
            return docs[:3]
        
        return product_specific_docs[:6]
    
    def _remove_duplicate_docs(self, docs: List[Any]) -> List[Any]:
        unique_docs = []
        seen_content = set()
        
        for doc in docs:
            content_hash = doc.page_content[:150].strip().lower()
            if content_hash not in seen_content:
                seen_content.add(content_hash)
                unique_docs.append(doc)
        
        return unique_docs
    
    def _is_product_specific_doc(self, doc: Any, product_name: str) -> bool:
        content_lower = doc.page_content.lower()
        product_lower = product_name.lower()
        
        if product_lower in content_lower:
            return True
        
        for alias, canonical_name in self.product_validator.product_aliases.items():
            if canonical_name == product_name and alias in content_lower:
                return True
        
        product_code = f"tgb-{product_lower.replace(' ', '').replace('-', '')}"
        if product_code in content_lower:
            return True
        
        return False
    
    def _create_product_focused_context(
        self, documents: List[Any], product_info: Dict, knowledge_assessment: Dict,
        health_context: Dict[str, Any], health_warnings: List[str]
    ) -> str:
        context_parts = []
        
        health_profile = self.health_extractor.format_health_context_for_prompt(health_context)
        if health_profile:
            context_parts.append(health_profile)
        
        if health_warnings:
            context_parts.append("🚨 IMPORTANT HEALTH CONSIDERATIONS:")
            for warning in health_warnings:
                context_parts.append(warning)
            context_parts.append("")
        
        if product_info["product_name"]:
            context_parts.append(f"🎯 PRODUCT: {product_info['product_name']}")
            context_parts.append(f"📋 QUESTION TYPE: {product_info['question_type']}")
            
            if product_info.get("product_info"):
                structured_info = self._format_structured_product_info(
                    product_info["product_name"], 
                    product_info["product_info"],
                    product_info["question_type"]
                )
                if structured_info:
                    context_parts.append(structured_info)
        
        if knowledge_assessment["insufficient_knowledge"]:
            context_parts.append("⚠️ KNOWLEDGE STATUS: LIMITED - Refer to gut coaches for complete information")
        
        for i, doc in enumerate(documents[:6], 1):
            doc_content = self._clean_document_content(doc.page_content)
            context_parts.append(f"SOURCE {i}:\n{doc_content}")
        
        return "\n\n".join(context_parts)
    
    def _format_structured_product_info(self, product_name: str, product_info: Dict, question_type: str) -> str:
        lines = [f"\n📦 VERIFIED {product_name.upper()} INFORMATION:"]
        
        if question_type == "ingredients" and "confirmed_ingredients" in product_info:
            lines.append("✅ Confirmed Ingredients:")
            for ingredient in product_info["confirmed_ingredients"]:
                lines.append(f"  • {ingredient}")
            if "confirmed_not_included" in product_info:
                lines.append("❌ Does NOT contain:")
                for ingredient in product_info["confirmed_not_included"]:
                    lines.append(f"  • {ingredient}")
        elif question_type == "dosage":
            if "dosage" in product_info:
                lines.append(f"💊 Dosage: {product_info['dosage']}")
            if "serving_size" in product_info:
                lines.append(f"📏 Serving Size: {product_info['serving_size']}")
            if "fiber_amount" in product_info:
                lines.append(f"🌾 Fiber Content: {product_info['fiber_amount']}")
            if "cfu_count" in product_info:
                lines.append(f"🦠 CFU Count: {product_info['cfu_count']}")
        elif question_type == "timing" and "timing" in product_info:
            lines.append(f"⏰ Best Time: {product_info['timing']}")
        elif question_type == "benefits" and "benefits" in product_info:
            lines.append("✨ Key Benefits:")
            for benefit in product_info["benefits"][:5]:
                lines.append(f"  • {benefit}")
        elif question_type == "safety":
            if "warnings" in product_info:
                lines.append("⚠️ Important Warnings:")
                for warning in product_info["warnings"]:
                    lines.append(f"  • {warning}")
            if "contraindications" in product_info:
                lines.append("⚠️ Contraindications:")
                for contraindication in product_info["contraindications"]:
                    lines.append(f"  • {contraindication}")
            if "age_limit" in product_info:
                lines.append(f"👤 Age Limit: {product_info['age_limit']}")
        
        return "\n".join(lines) if len(lines) > 1 else ""
    
    def _clean_document_content(self, content: str) -> str:
        content = re.sub(r'\s+', ' ', content)
        content = re.sub(r'[^\w\s.,!?():•\-–—]', ' ', content)
        content = re.sub(r'([•▪▫○])\s*', r'\1 ', content)
        content = re.sub(r' +', ' ', content)
        return content.strip()
    
    def _format_knowledge_assessment(self, assessment: Dict) -> str:
        if assessment["insufficient_knowledge"]:
            return f"""
KNOWLEDGE ASSESSMENT: INSUFFICIENT
• Confidence Impact: {assessment['confidence_impact']}
• Recommendation: {assessment['recommendation']}  
• Product-specific docs found: {assessment['product_specific_docs_found']}
• Relevance score: {assessment['relevance_score']:.2f}

ACTION REQUIRED: Provide available information and suggest contacting gut coaches for comprehensive guidance.
"""
        else:
            return """
KNOWLEDGE ASSESSMENT: SUFFICIENT
• Information appears complete for this question
• Proceed with providing accurate response from verified sources
• Consider user's health profile when providing recommendations
"""
    
    def _get_format_instructions(self) -> str:
        base_instructions = """
REQUIRED OUTPUT FORMAT - YOU MUST RETURN VALID JSON:

Return your response as a JSON object with these exact fields:
{
  "answer": "Complete response with emojis and warm tone, ONLY include information specific to the asked product",
  "confidence": "High/Medium/Low",
  "category": "Type of question (ingredients/dosage/timing/benefits/safety/comparison/general)",
  "knowledge_status": "complete/incomplete"
}

CRITICAL JSON FORMATTING RULES:
1. Output MUST be valid JSON - use double quotes for strings
2. Do NOT use markdown formatting (**, *, etc.) inside the JSON strings
3. Escape special characters properly in JSON strings
4. The "answer" field should contain plain text with emojis, NO markdown

CONTENT INSTRUCTIONS:
1. Answer ONLY about the specific product mentioned in the question
2. DO NOT include information about other products
3. Consider the user's health profile when providing recommendations
4. If health warnings are present, acknowledge them in your response
5. Be empathetic and supportive, especially when discussing health concerns
6. NEVER end your answer with a question - always end with a statement, affirmation, or clear directive
7. Avoid ending with phrases like "What do you think?", "Does this help?", "Ready to try?"
"""
        
        if self.model_type in ["llama", "mistral"]:
            return base_instructions + "\n\nIMPORTANT: Think through your response, but output ONLY the JSON object."
        elif self.model_type == "qwen":
            return base_instructions + "\n\nIMPORTANT: Think carefully, but output ONLY the JSON object."
        else:
            return base_instructions + "\n\nIMPORTANT: Output ONLY the JSON object, nothing else."
    
    def _clean_model_response(self, response: str) -> str:
        response = re.sub(r'^Assistant:\s*', '', response)
        response = re.sub(r'^\[INST\].*?\[/INST\]', '', response, flags=re.DOTALL)
        response = re.sub(r'<\|.*?\|>', '', response)
        
        reasoning_markers = [
            r'REASONING PROCESS:.*?(?=FINAL RESPONSE:|FINAL ANSWER:)',
            r'THINKING PROCESS:.*?(?=FINAL RESPONSE:|FINAL ANSWER:)',
            r'ANALYSIS:.*?(?=FINAL RESPONSE:|FINAL ANSWER:)',
            r'STEP-BY-STEP REASONING:.*?(?=FINAL RESPONSE:|FINAL ANSWER:)',
            r'CHAIN OF THOUGHT:.*?(?=FINAL RESPONSE:|FINAL ANSWER:)',
        ]
        
        for marker in reasoning_markers:
            response = re.sub(marker, '', response, flags=re.DOTALL | re.IGNORECASE)
        
        final_answer_patterns = [
            r'FINAL RESPONSE:\s*(.*)',
            r'FINAL ANSWER:\s*(.*)',
        ]
        
        for pattern in final_answer_patterns:
            match = re.search(pattern, response, re.DOTALL | re.IGNORECASE)
            if match:
                response = match.group(1).strip()
                break
        
        return response.strip()
