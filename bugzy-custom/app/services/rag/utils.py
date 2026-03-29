"""
Utility Functions Module

This module contains utility functions for The Good Bug health chatbot RAG API,
including text processing, categorization, and vector store loading.
"""

import re
import os
import logging
from typing import Tuple
try:
    from langchain_pinecone import PineconeVectorStore
except ImportError:  # pragma: no cover
    PineconeVectorStore = None
from langchain_huggingface import HuggingFaceEmbeddings
from app.services.llm.bedrock_llm import BedrockLLM

from dotenv import load_dotenv

load_dotenv()   

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
INDEX_NAME = os.getenv("PINECONE_INDEX_NAME")  # Use env var with fallback

logger = logging.getLogger(__name__)


def categorize_question(question: str) -> str:
    """Enhanced categorization with more precise categories"""
    question_lower = question.lower()
    
    if any(word in question_lower for word in ["ingredient", "contain", "composition", "what's in", "made of", "formula"]):
        return "product_ingredients"
    elif any(word in question_lower for word in ["timing", "when", "schedule", "time", "before", "after"]):
        return "product_timing"
    elif any(word in question_lower for word in ["dosage", "how much", "serving", "take", "dose"]):
        return "product_dosage"
    elif any(word in question_lower for word in ["benefit", "help", "effect", "work", "good for", "use"]):
        return "product_benefits"
    elif any(word in question_lower for word in ["difference", "vs", "versus", "compare"]):
        return "product_comparison"
    elif any(word in question_lower for word in ["safe", "side effect", "pregnant", "diabetes", "caution"]):
        return "product_safety"
    elif any(word in question_lower for word in ["track", "delivery", "shipping", "order status", "arrive", "shipped"]):
        return "shipping"
    else:
        return 'product_general'


def extract_final_answer(text: str) -> str:
    """Extract only the final answer from the response"""
    final_answer_patterns = [
        r'FINAL RESPONSE:\s*(.*)',
        r'FINAL ANSWER:\s*(.*)',
    ]
    
    for pattern in final_answer_patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            text = match.group(1).strip()
            break
    
    reasoning_with_headers = [
        r'REASONING PROCESS:.*?(?=FINAL RESPONSE:|FINAL ANSWER:|$)',
        r'THINKING PROCESS:.*?(?=FINAL RESPONSE:|FINAL ANSWER:|$)',
        r'STEP-BY-STEP REASONING:.*?(?=FINAL RESPONSE:|FINAL ANSWER:|$)',
        r'CHAIN OF THOUGHT:.*?(?=FINAL RESPONSE:|FINAL ANSWER:|$)',
    ]
    
    for pattern in reasoning_with_headers:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.DOTALL)
    
    return text.strip()


def format_text_for_readability(text: str) -> str:
    """Enhanced text formatting"""
    text = extract_final_answer(text)
    text = re.sub(r'^\s*(?:Assistant|Response|Answer):\s*', '', text)
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)
    return text.strip()


def final_answer_cleanup(text: str) -> str:
    """Final cleanup to ensure no reasoning/thinking process remains"""
    reasoning_line_patterns = [
        r'^THINKING:.*$',
        r'^REASONING:.*$',
        r'^ANALYSIS:.*$',
        r'^CONSIDERATION:.*$',
    ]
    
    for pattern in reasoning_line_patterns:
        text = re.sub(pattern, '', text, flags=re.MULTILINE | re.IGNORECASE)
    
    text = re.sub(r'\{[^}]*"answer"[^}]*\}', '', text, flags=re.DOTALL)
    text = re.sub(r'(?:confidence|category|knowledge_status):\s*\w+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
    text = re.sub(r'^\s+|\s+$', '', text, flags=re.MULTILINE)
    
    return text.strip()


def load_vector_store():
    """Load vector store with enhanced error handling and fallback"""
    if PineconeVectorStore is None:
        # Fallback dummy store
        class DummyRetriever:
            def get_relevant_documents(self, query: str):
                return []
        class DummyVectorStore:
            def as_retriever(self, *args, **kwargs):
                return DummyRetriever()
        logger.warning("⚠️ PineconeVectorStore not available – using dummy in‑memory store")
        return DummyVectorStore()
    try:
        from langchain_huggingface import HuggingFaceEmbeddings
        embedding_model = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)
        vector_store = PineconeVectorStore(
            index_name=INDEX_NAME,
            embedding=embedding_model
        )
        return vector_store
    except Exception as e:
        logger.error("Failed to connect to Pinecone index: %s", e)
        return None
