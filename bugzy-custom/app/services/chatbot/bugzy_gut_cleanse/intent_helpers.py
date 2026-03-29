"""Yes/no intent helpers shared by Gut Cleanse router and voice nodes (no router import)."""

import re


def _contains_word(text: str, word: str) -> bool:
    """True if `word` appears as a standalone token (case-insensitive)."""
    if not text or not word:
        return False
    return bool(
        re.search(rf"(?<!\w){re.escape(word)}(?!\w)", text, flags=re.IGNORECASE)
    )


def _is_affirmative(text: str) -> bool:
    """Conservative yes-intent detection for preference prompts."""
    t = (text or "").strip().lower()
    if not t:
        return False
    if _contains_word(t, "yes") or _contains_word(t, "yeah") or _contains_word(t, "yep"):
        return True
    if _contains_word(t, "sure") or _contains_word(t, "ok") or _contains_word(t, "okay"):
        return True
    if "let's go" in t or "lets go" in t:
        return True
    if ("create" in t or "make" in t or "build" in t) and "plan" in t:
        return True
    return False


def _is_negative_or_defer(text: str) -> bool:
    """Conservative no/defer detection for preference prompts."""
    t = (text or "").strip().lower()
    if not t:
        return False
    if _contains_word(t, "no") or _contains_word(t, "nah") or _contains_word(t, "nope"):
        return True
    if "later" in t or "not now" in t or "maybe later" in t or "not today" in t:
        return True
    if _contains_word(t, "skip") or _contains_word(t, "pass") or _contains_word(t, "busy"):
        return True
    if "don't" in t or "dont" in t:
        return True
    return False
