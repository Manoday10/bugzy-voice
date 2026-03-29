# prompt_store.py
"""Load prompt templates from prompts/free_form/."""
from pathlib import Path
from functools import lru_cache

BASE_DIR = Path(__file__).parent
PROMPTS_DIR = BASE_DIR


@lru_cache(maxsize=128)
def load_prompt(relative_path: str) -> str:
    """Load a prompt template from prompts/free_form/."""
    full_path = PROMPTS_DIR / relative_path
    if not full_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {full_path}")
    return full_path.read_text(encoding="utf-8")
