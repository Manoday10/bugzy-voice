# prompt_store.py
"""
Simple prompt loader for markdown prompt templates.
Prompts are stored in prompts/ directory and cached in memory.
"""
from pathlib import Path
from functools import lru_cache

# Base directory setup
BASE_DIR = Path(__file__).parent
PROMPTS_DIR = BASE_DIR

@lru_cache(maxsize=128)
def load_prompt(relative_path: str) -> str:
    """
    Load a prompt template from the prompts/ directory.
    
    Args:
        relative_path: Path relative to prompts/ directory
                      Example: "health_qna/system_health_qna_v1.md"
    
    Returns:
        str: The prompt template content as a string
        
    Example:
        template = load_prompt("health_qna/system_health_qna_v1.md")
        prompt = template.format(user_context="...", user_question="...")
    """
    full_path = PROMPTS_DIR / relative_path
    
    if not full_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {full_path}")
    
    return full_path.read_text(encoding="utf-8")