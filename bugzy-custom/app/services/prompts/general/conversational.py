"""
Conversation AI Module

This module handles conversational AI responses using LLM.
"""

from app.services.llm.bedrock_llm import ChatBedRockLLM

# Initialize LLM
llm = ChatBedRockLLM()


def get_conversational_response(prompt: str, context: str = "", user_name: str = "", max_lines: int = None) -> str:
    """Get a short, conversational response from LLM."""
    name_instruction = (
        f" Use user's name {user_name} if provided for more personalization."
        if user_name else ""
    )
    # Determine length constraint
    if max_lines:
        length_constraint = f"Keep response to {max_lines} lines maximum."
    else:
        length_constraint = "Keep response to 2-3 lines maximum."
    full_prompt = (
        f"{prompt}\n\n"
        f"Context: {context}\n\n"
        f"{length_constraint} "
        "Make it warm, empathetic and conversational. "
        "Use appropriate emojis. "
        "Do not start with greeting messages like 'Hey', 'Hello', 'Hi', etc. "
        "Do not end with closing messages like 'Thanks', 'Bye', 'See you later', etc. "
        "Do not end with or contain any question, inquiry, or asking intent. "
        "Ensure the final sentence concludes as a statement only."
        f"{name_instruction}"
    )
    response = llm.invoke(full_prompt)
    return response.content.strip()