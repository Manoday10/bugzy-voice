"""
Pydantic Models Module

This module contains Pydantic models for API requests and responses
for The Good Bug health chatbot RAG API.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from langchain_core.output_parsers import PydanticOutputParser


class QuestionRequest(BaseModel):
    question: str = Field(..., description="The question to ask (may include health context)", min_length=1)
    model_type: Optional[str] = Field(default="llama", description="Model type: llama, mistral, qwen, or general")

class GutHealthResponse(BaseModel):
    answer: str = Field(description="Product-specific answer with step-by-step reasoning")
    confidence: str = Field(description="High, Medium, or Low based on knowledge completeness")
    category: Optional[str] = Field(description="Category of question", default=None)
    knowledge_status: Optional[str] = Field(description="Status of knowledge completeness", default="complete")

class QuestionResponse(BaseModel):
    question: str
    answer: str
    confidence: str
    category: str
    knowledge_status: str
    model_type: str
    health_context_considered: bool
    health_warnings: Optional[List[str]] = None
    guardrail_triggered: Optional[bool] = None
    guardrail_type: Optional[str] = None
    ctas_level: Optional[int] = None


# Output parser
response_parser = PydanticOutputParser(pydantic_object=GutHealthResponse)

