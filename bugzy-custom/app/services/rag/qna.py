"""
Enhanced Product-Specific TGB RAG API with Guardrails
Version 7.0.0

This module implements a comprehensive RAG (Retrieval-Augmented Generation) system
for The Good Bug health chatbot with the following features:

1. Product-specific information retrieval
2. Health context awareness
3. CTAS Emergency Detection (Canadian Triage and Acuity Scale)
4. Medical Guardrails (Prescription drugs, Disease management, High-risk conditions)
5. Model-specific prompt optimization (Llama, Mistral, Qwen)

Based on TGB AI Chatbot Guardrails Document.
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional, List
import os
from dotenv import load_dotenv
from contextlib import asynccontextmanager
import re
import logging
import sys

load_dotenv()

# Import from new modules
from app.services.rag.emergency_detection import EmergencyDetector, CTASLevel
from app.services.rag.medical_guardrails import MedicalGuardrails
from app.services.rag.health_context import HealthContextExtractor
from app.services.rag.product_validator import ProductSpecificValidator
from app.services.rag.knowledge_checker import KnowledgeCompletenessChecker
from app.services.rag.qa_chain import OptimizedProductSpecificRetrievalQA
from app.services.rag.models import QuestionRequest, QuestionResponse, GutHealthResponse, response_parser
from app.services.rag.utils import (
    categorize_question,
    extract_final_answer,
    format_text_for_readability,
    final_answer_cleanup,
    load_vector_store
)
from app.services.rag.optimized_prompts_with_guardrails import get_model_specific_prompt, GUARDRAIL_RESPONSES
from app.services.llm.bedrock_llm import BedrockLLM

logger = logging.getLogger(__name__)


# ============================================================================
# Environment and Configuration
# ============================================================================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
INDEX_NAME = os.getenv("PINECONE_INDEX_NAME")  # Use env var with fallback

# Global variables for vector store and QA chain
vector_store = None
retriever = None
qa_chain = None
llm = None


# ============================================================================
# FastAPI Application Setup
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    global vector_store, retriever, qa_chains, llm
    
    logger.info("🚀 Starting up Enhanced Product-Specific RAG API with Guardrails...")
    
    vector_store = load_vector_store()
    if vector_store is None:
        raise RuntimeError("Failed to connect to Pinecone index")
    
    logger.info("✅ Connected to Pinecone vector store")
    
    retriever = vector_store.as_retriever(search_kwargs={"k": 8})
    llm = BedrockLLM(temperature=0.1, max_tokens=3072)
    
    logger.info("✅ Enhanced Product-Specific RAG system initialized")
    logger.info("✅ Loaded %s products", len(ProductSpecificValidator().known_compositions))
    logger.info("✅ Health context integration enabled")
    logger.info("✅ CTAS Emergency Detection enabled")
    logger.info("✅ Medical Guardrails enabled")
    
    yield
    
    logger.info("👋 Shutting down Enhanced RAG API...")


app = FastAPI(
    title="Enhanced Product-Specific TGB RAG API with Guardrails",
    description="Product-specific RAG API with comprehensive product knowledge base, health context integration, CTAS emergency detection, and medical guardrails",
    version="7.0.0",
    lifespan=lifespan
)


# ============================================================================
# Response Generation Function
# ============================================================================

async def get_optimized_response(question: str, model_type: str = "llama") -> dict:
    """Get optimized response based on model type with health context and guardrails"""
    try:
        logger.info("Processing question with %s optimization: %s...", model_type, question[:100])
        
        qa_chain = OptimizedProductSpecificRetrievalQA.from_chain_type(
            llm=llm,
            chain_type="stuff",
            retriever=retriever,
            model_type=model_type,
            return_source_documents=True
        )
        
        result = qa_chain.invoke({"query": question})
        
        logger.info("Model type: %s", model_type)
        logger.info("Product identified: %s", result.get('product_identified'))
        logger.info("Health context considered: %s", result.get('health_context_considered'))
        logger.info("Guardrail triggered: %s", result.get('guardrail_triggered'))
        if result.get('guardrail_triggered'):
            logger.info("Guardrail type: %s", result.get('guardrail_type'))
            if result.get('ctas_level'):
                logger.info("CTAS Level: %s", result.get('ctas_level'))
        
        # If guardrail was triggered, return early
        if result.get('guardrail_triggered'):
            return {
                "question": question,
                "answer": result["result"],
                "confidence": "High",
                "category": result.get('guardrail_type', 'guardrail'),
                "knowledge_status": "complete",
                "model_type": model_type,
                "health_context_considered": True,
                "health_warnings": result.get("health_warnings", []),
                "guardrail_triggered": True,
                "guardrail_type": result.get('guardrail_type'),
                "ctas_level": result.get('ctas_level')
            }
        
        raw_answer = result["result"]
        knowledge_completeness = result.get("knowledge_completeness", {})
        health_warnings = result.get("health_warnings", [])
        
        try:
            cleaned_for_parsing = re.sub(r'\*\*(.*?)\*\*', r'\1', raw_answer)
            cleaned_for_parsing = re.sub(r'\*(.*?)\*', r'\1', cleaned_for_parsing)
            
            parsed_response = response_parser.parse(cleaned_for_parsing)
            
            formatted_answer = format_text_for_readability(parsed_response.answer)
            formatted_answer = final_answer_cleanup(formatted_answer)
            
            question_category = parsed_response.category or categorize_question(question)
            
            confidence = parsed_response.confidence
            knowledge_status = "complete"
            
            if knowledge_completeness.get("insufficient_knowledge", False):
                knowledge_status = "incomplete"
                if knowledge_completeness.get("confidence_impact") == "major":
                    confidence = "Low"
                elif knowledge_completeness.get("confidence_impact") == "moderate" and confidence == "High":
                    confidence = "Medium"
            
            response_data = {
                "question": question,
                "answer": formatted_answer,
                "confidence": confidence,
                "category": question_category,
                "knowledge_status": knowledge_status,
                "model_type": model_type,
                "health_context_considered": result.get("health_context_considered", False),
                "health_warnings": health_warnings if health_warnings else None,
                "guardrail_triggered": False,
                "guardrail_type": None,
                "ctas_level": None
            }
            
        except Exception as parse_error:
            logger.error("Parsing error: %s", parse_error)
            logger.debug("Raw answer (first 200 chars): %s", raw_answer[:200])
            
            formatted_answer = format_text_for_readability(raw_answer)
            formatted_answer = final_answer_cleanup(formatted_answer)
            
            if not formatted_answer or len(formatted_answer.strip()) < 20:
                formatted_answer = "I'd be happy to help! Please contact our gut coaches at nutritionist@seventurns.in or call +91 8040282085 for detailed guidance. 💚"
            
            question_category = categorize_question(question)
            knowledge_status = "incomplete" if knowledge_completeness.get("insufficient_knowledge") else "complete"
            
            response_data = {
                "question": question,
                "answer": formatted_answer,
                "confidence": "Medium",
                "category": question_category,
                "knowledge_status": knowledge_status,
                "model_type": model_type,
                "health_context_considered": result.get("health_context_considered", False),
                "health_warnings": health_warnings if health_warnings else None,
                "guardrail_triggered": False,
                "guardrail_type": None,
                "ctas_level": None
            }
        
        return response_data
        
    except Exception as e:
        raise Exception(f"Error processing question with {model_type}: {str(e)}")


# ============================================================================
# API Endpoints
# ============================================================================

@app.post("/ask", response_model=QuestionResponse)
async def ask(request: QuestionRequest):
    """
    Enhanced product-specific question answering with comprehensive product knowledge, 
    health context, CTAS emergency detection, and medical guardrails.
    
    Question format can include health context:
    Health conditions: <conditions>
    Allergies: <allergies>
    Medications: <medications>
    Supplements: <supplements>
    Gut health: <gut health issues>
    
    <actual question>
    
    GUARDRAILS:
    - Emergency Detection (CTAS Levels 1-3): Automatically detects medical emergencies
    - Prescription Drug Queries: Redirects to healthcare providers
    - Disease Management: Redirects to doctors
    - High-Risk Conditions: Provides appropriate warnings
    """
    question = request.question.strip()
    model_type = request.model_type or "llama"
    
    if not question:
        raise HTTPException(status_code=400, detail="No question provided")
    
    if model_type not in ["llama", "mistral", "qwen", "general"]:
        raise HTTPException(status_code=400, detail="Invalid model_type. Choose: llama, mistral, qwen, or general")
    
    try:
        response = await get_optimized_response(question, model_type)
        return JSONResponse(content=response)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Sorry, I couldn't process your question: {str(e)}"
        )


@app.get("/health")
async def health_check():
    """Health check with product database, health context, and guardrails info"""
    validator = ProductSpecificValidator()
    return {
        "status": "healthy",
        "service": "Enhanced Product-Specific TGB RAG API with Guardrails",
        "version": "7.0.0",
        "supported_models": ["llama", "mistral", "qwen", "general"],
        "products_loaded": len(validator.known_compositions),
        "product_aliases": len(validator.product_aliases),
        "features": {
            "health_context_integration": True,
            "contraindication_checking": True,
            "personalized_recommendations": True,
            "ctas_emergency_detection": True,
            "medical_guardrails": True,
            "prescription_drug_filtering": True,
            "disease_management_filtering": True
        },
        "guardrails": {
            "emergency_detection": "CTAS Levels 1-3 (Resuscitation, Emergent, Urgent)",
            "prescription_drugs": "Redirects to healthcare providers",
            "disease_management": "Redirects to doctors",
            "high_risk_conditions": [
                "Nutrition: kidney/liver disease, severe GI disorders, metabolic disorders, immunosuppressive therapy",
                "Fitness: cardiac conditions, respiratory conditions, uncontrolled diabetes",
                "Surgery: recent surgery, post-bariatric, GI resections",
                "Injury: fractures, ligament tears, spinal issues",
                "Medication: anticoagulants, immunosuppressants, antiepileptics, narrow therapeutic index drugs"
            ]
        }
    }


@app.get("/products")
async def get_products():
    """Get list of all supported products"""
    validator = ProductSpecificValidator()
    products = list(validator.known_compositions.keys())
    
    product_details = {}
    for product in products:
        info = validator.known_compositions[product]
        product_details[product] = {
            "has_ingredients": "confirmed_ingredients" in info,
            "has_dosage": "dosage" in info,
            "has_timing": "timing" in info,
            "has_benefits": "benefits" in info,
            "has_warnings": "warnings" in info,
            "has_contraindications": "contraindications" in info
        }
    
    return {
        "total_products": len(products),
        "products": products,
        "product_details": product_details
    }


@app.get("/product/{product_name}")
async def get_product_info(product_name: str):
    """Get detailed information about a specific product"""
    validator = ProductSpecificValidator()
    
    product_info = None
    actual_product_name = None
    
    for key in validator.known_compositions.keys():
        if key.lower() == product_name.lower():
            product_info = validator.known_compositions[key]
            actual_product_name = key
            break
    
    if not product_info:
        for alias, canonical_name in validator.product_aliases.items():
            if alias.lower() == product_name.lower():
                product_info = validator.known_compositions.get(canonical_name)
                actual_product_name = canonical_name
                break
    
    if not product_info:
        raise HTTPException(status_code=404, detail=f"Product '{product_name}' not found")
    
    return {
        "product_name": actual_product_name,
        "information": product_info
    }


@app.get("/models")
async def get_supported_models():
    """Get information about supported model optimizations"""
    return {
        "supported_models": {
            "llama": {
                "description": "Optimized for Llama family models",
                "features": ["structured reasoning", "step-by-step examples", "clear formatting", "health context awareness", "guardrails integration"]
            },
            "mistral": {
                "description": "Optimized for Mistral family models", 
                "features": ["instruction following", "structured responses", "reasoning framework", "health context awareness", "guardrails integration"]
            },
            "qwen": {
                "description": "Optimized for Qwen family models",
                "features": ["bullet points", "chain of thought", "few-shot examples", "health context awareness", "guardrails integration"]
            },
            "general": {
                "description": "General optimization for other models",
                "features": ["broad compatibility", "standard formatting", "health context awareness", "guardrails integration"]
            }
        }
    }


@app.get("/guardrails")
async def get_guardrails_info():
    """Get detailed information about all guardrails"""
    guardrails = MedicalGuardrails()
    
    return {
        "guardrails_version": "1.0.0",
        "based_on": "TGB AI Chatbot Guardrails Document",
        "emergency_detection": {
            "description": "CTAS-based emergency detection system",
            "ctas_levels": {
                "Level 1 - Resuscitation": "Immediate life-threatening conditions",
                "Level 2 - Emergent": "Potentially life-threatening",
                "Level 3 - Urgent": "Could progress to serious"
            },
            "action": "Immediate emergency response directing to emergency services"
        },
        "prescription_drugs": {
            "description": "Filters queries about prescription medications",
            "action": "Redirects user to healthcare provider",
            "response": guardrails.prescription_drug_response
        },
        "disease_management": {
            "description": "Filters queries about treating/curing diseases",
            "action": "Redirects user to doctor",
            "response": guardrails.disease_management_response
        },
        "high_risk_conditions": {
            "nutrition": {
                "conditions": guardrails.high_risk_conditions["nutrition"]["conditions"],
                "response": guardrails.high_risk_conditions["nutrition"]["response"]
            },
            "fitness": {
                "conditions": guardrails.high_risk_conditions["fitness"]["conditions"],
                "response": guardrails.high_risk_conditions["fitness"]["response"]
            },
            "surgery": {
                "conditions": guardrails.high_risk_conditions["surgery"]["conditions"],
                "response": guardrails.high_risk_conditions["surgery"]["response"]
            },
            "injury": {
                "conditions": guardrails.high_risk_conditions["injury"]["conditions"],
                "response": guardrails.high_risk_conditions["injury"]["response"]
            },
            "medication": {
                "conditions": guardrails.high_risk_conditions["medication"]["conditions"],
                "response": guardrails.high_risk_conditions["medication"]["response"]
            }
        },
        "mental_health": {
            "description": "Special handling for mental health emergencies",
            "action": "Provides crisis resources and mental health support contacts"
        }
    }


@app.get("/")
async def root():
    """Root endpoint with comprehensive system information"""
    validator = ProductSpecificValidator()
    return {
        "message": "Welcome to The Good Bug Enhanced Product-Specific RAG API with Guardrails",
        "version": "7.0.0",
        "description": "Advanced RAG system with comprehensive product knowledge base, health profile integration, CTAS emergency detection, and medical guardrails",
        "key_features": {
            "product_database": f"{len(validator.known_compositions)} products with detailed information",
            "product_filtering": "Returns only product-specific information",
            "model_optimization": "Tailored prompts for Qwen, Llama, Mistral",
            "chain_of_thought": "Step-by-step reasoning for complex questions",
            "knowledge_assessment": "Intelligent expert referrals",
            "comprehensive_coverage": "Ingredients, dosage, timing, benefits, safety, comparisons",
            "health_context": "Considers user health conditions, allergies, medications, supplements, gut health",
            "contraindication_checking": "Automatic detection of potential product-health interactions",
            "personalized_recommendations": "Tailored advice based on health profile",
            "ctas_emergency_detection": "Canadian Triage and Acuity Scale emergency detection",
            "medical_guardrails": "Prescription drug filtering, disease management filtering, high-risk condition warnings"
        },
        "guardrails": [
            "CTAS Emergency Detection (Levels 1-3)",
            "Prescription Drug Filtering",
            "Disease Management Filtering",
            "High-Risk Condition Warnings (Nutrition, Fitness, Surgery, Injury, Medication)",
            "Mental Health Crisis Support"
        ],
        "endpoints": {
            "POST /ask": "Ask questions with model-specific optimization, health context, and guardrails",
            "GET /products": "View all supported products",
            "GET /product/{name}": "Get detailed product information",
            "GET /models": "View supported model optimizations",
            "GET /guardrails": "View all guardrails and their configurations",
            "GET /health": "System health and capabilities"
        },
        "docs": "/docs"
    }


if __name__ == '__main__':
    import uvicorn
    import sys
    
    # Initialize logging configuration only when running standalone
    logging.basicConfig(
        level=logging.INFO,
        format="[RAG] %(levelname)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True
    )
    logger.info("🚀 RAG service logger initialized (Standalone)")
    
    uvicorn.run(
        app,
        host='0.0.0.0',
        port=8000,
        log_level="info"
    )