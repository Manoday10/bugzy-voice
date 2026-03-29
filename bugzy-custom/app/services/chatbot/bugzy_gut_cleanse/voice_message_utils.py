"""Extract assistant text from voice/graph message lists (dict or LangChain message objects)."""

from __future__ import annotations

from typing import Any, Iterator


def gut_normalize_assistant_text(raw: Any) -> str:
    """Flatten content from a message object to a single string."""
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw.strip()
    if isinstance(raw, list):
        parts: list[str] = []
        for item in raw:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and "text" in item:
                parts.append(str(item.get("text", "")))
            else:
                parts.append(str(item))
        return " ".join(parts).strip()
    return str(raw).strip()


def gut_iter_assistant_contents(messages: list[Any] | None) -> Iterator[str]:
    """Yield assistant message texts from newest to oldest."""
    for m in reversed(messages or []):
        if isinstance(m, dict):
            if m.get("role") == "assistant":
                t = gut_normalize_assistant_text(m.get("content"))
                if t:
                    yield t
            continue
        mtype = getattr(m, "type", None)
        if mtype == "human":
            continue
        if mtype in ("ai", "assistant"):
            t = gut_normalize_assistant_text(getattr(m, "content", None))
            if t:
                yield t
            continue
        r = getattr(m, "role", None)
        if r in ("assistant", "ai"):
            t = gut_normalize_assistant_text(getattr(m, "content", None))
            if t:
                yield t


def gut_last_assistant_content(messages: list[Any] | None) -> str:
    """Return the most recent non-empty assistant text, or ""."""
    for t in gut_iter_assistant_contents(messages):
        if t:
            return t
    return ""


def gut_age_prompt_already_spoken(messages: list[Any] | None, voiced_age_q: str) -> bool:
    """True if any assistant turn in history contains the 18+ voice prompt."""
    needle = (voiced_age_q or "").strip().lower()
    needle2 = "18 years or older"
    if not needle and not needle2:
        return False
    for t in gut_iter_assistant_contents(messages):
        low = t.lower()
        if needle and needle in low:
            return True
        if needle2 in low:
            return True
    return False


def gut_should_append_age_seed(messages: list[Any] | None, question: str) -> bool:
    """False if an assistant message already contains the 18+ prompt."""
    return not gut_age_prompt_already_spoken(messages, question)
