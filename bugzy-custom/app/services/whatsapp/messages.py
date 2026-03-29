"""
WhatsApp Message Formatting Utilities

This module contains functions for formatting and processing messages for WhatsApp.
Includes markdown removal, message splitting, and text formatting utilities.
"""

import re
import time


def remove_markdown(text: str) -> str:
    """
    Convert standard markdown formatting to WhatsApp-compatible format.
    - Converts **bold** to *bold* (WhatsApp uses single asterisks)
    - Removes markdown headers (# Header → Header)
    - Removes italic (_text_), strikethrough (~text~), code (`text`)
    - Keeps bold formatting but in WhatsApp format
    - Preserves emojis, bullets, and other special characters
    """
    if not text:
        return text
    
    # Remove markdown headers (# Header, ## Header, etc.) but keep the text
    # This handles headers at the start of lines
    text = re.sub(r'^#{1,6}\s+(.+)$', r'*\1*', text, flags=re.MULTILINE)
    
    # Convert double asterisks (Markdown bold) to single asterisks (WhatsApp bold)
    # **text** → *text*
    # Use a non-greedy match and allow any character except double asterisks
    text = re.sub(r'\*\*(.+?)\*\*', r'*\1*', text)
    
    # Remove underscores (italic) - WhatsApp uses underscores too, but we'll remove them
    # If you want to keep italics, comment out this line
    text = re.sub(r'_([^_]+)_', r'\1', text)
    
    # Remove tildes (strikethrough)
    text = re.sub(r'~([^~]+)~', r'\1', text)
    
    # Remove backticks (code/monospace)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    
    # Remove markdown links [text](url) → text
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    
    # Remove markdown images ![alt](url) → alt
    text = re.sub(r'!\[([^\]]*)\]\([^\)]+\)', r'\1', text)
    
    # Keep bullet points as-is (don't convert to dashes)
    # Bullets (•) are already WhatsApp-compatible, so we preserve them
    
    # Collapse multiple newlines (more than 2) to just 2
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()


def send_multiple_messages(user_id: str, response_text: str, send_fn):
    """
    Split response into multiple messages for better readability.
    
    Args:
        user_id: The recipient's WhatsApp ID
        response_text: The text to split and send
        send_fn: The function to use for sending messages (should accept user_id and message)
    """
    # Sanitize markdown (e.g. **bold** -> *bold*) to prevent WhatsApp formatting issues
    response_text = remove_markdown(response_text)
    
    sections = []

    # --- NEW RULE: If text is a long paragraph → split on "." into sentences
    if "." in response_text and "\n\n" not in response_text and "•" not in response_text:
        sentences = response_text.split(".")
        cleaned = []

        for s in sentences:
            s = s.strip()
            if s:
                cleaned.append(s + ".")   # restore removed "."

        # Insert \n\n between all sentences
        formatted_text = "\n\n".join(cleaned)

        # Split into final sections
        sections = formatted_text.split("\n\n")

    # --- OLD RULE #1: Split on "\n\n."
    elif "\n\n." in response_text:
        raw_parts = response_text.split("\n\n.")
        sections = []
        for i, part in enumerate(raw_parts):
            part = part.strip()
            if not part:
                continue

            if i == 0:
                sections.append(part)
            else:
                sections.append("." + part)

    # --- OLD RULE #2: Split by double newlines
    elif "\n\n" in response_text:
        sections = response_text.split("\n\n")

    # --- OLD RULE #3: Split by bullet points
    elif "•" in response_text:
        parts = response_text.split("•")
        sections = [parts[0]]
        for part in parts[1:]:
            sections.append("•" + part.strip())

    # --- OLD RULE #4: Long text fallback (sentence grouping)
    else:
        sentences = response_text.split(". ")
        if len(response_text) > 500:
            current_section = ""
            for sentence in sentences:
                if len(current_section + sentence) > 400:
                    if current_section:
                        sections.append(current_section.strip() + ".")
                    current_section = sentence
                else:
                    current_section += (". " + sentence if current_section else sentence)
            if current_section:
                sections.append(current_section.strip() + ".")
        else:
            sections = [response_text]

    # --- SEND WHATSAPP MESSAGES ---
    for i, section in enumerate(sections):
        if section.strip():
            send_fn(user_id, section.strip())
            if i < len(sections) - 1:
                time.sleep(1)