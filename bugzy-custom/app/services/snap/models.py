"""
Pydantic Models for Snap Vision Analysis

This module contains the Pydantic schemas for validating and structuring
vision analysis outputs for different food image categories.
"""

from pydantic import BaseModel
from typing import List, Dict


class CategoryAOutput(BaseModel):
    """Schema for Category A: Prepared Food / Meals"""
    category: str
    detected_items: List[str]
    protein_g: str
    carbs_g: str
    fats_g: str
    calorie_range: str
    fiber_g: str
    probiotics: str
    prebiotics: str
    digestive_spices: str
    health_assessment: str
    gut_health_integration: str
    suggestions: List[str]
    raw_llm_output: str
    final_structured_text: str


class CategoryBOutput(BaseModel):
    """Schema for Category B: Raw Ingredients / Vegetables"""
    category: str
    identified_ingredients: List[str]
    categorized_ingredients: Dict[str, List[str]]
    nutritional_potential: Dict[str, str]
    key_vitamins_minerals: List[str]
    healthy_recipes: List[str]
    general_pro_tips: List[str]
    raw_llm_output: str
    final_structured_text: str


class CategoryCOutput(BaseModel):
    """Schema for Category C: Non-Food Items"""
    category: str
    message: str
    raw_llm_output: str
    final_structured_text: str
