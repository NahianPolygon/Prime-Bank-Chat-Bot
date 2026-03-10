"""
Text cleanup utilities for removing model artifacts and formatting issues.
"""

import re


def clean_response(text: str) -> str:
    """
    Clean LLM output by removing model thinking markers, artifacts, and formatting.
    
    Args:
        text: Raw LLM response
        
    Returns:
        Cleaned text
    """
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = re.sub(r"\*\*\[.*?\]\*\*\s*\n?", "", text)
    text = re.sub(r"\[[^\]]*[—\-][^\]]*\]\s*\n?", "", text)
    text = re.sub(r"\[(Opening|Closing|Instructions?|Rules?)[^\]]*\]\s*\n?",
                  "", text, flags=re.IGNORECASE)
    text = re.sub(r"^\s*---\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def is_valid_retrieval(text: str | None, min_length: int = 80) -> bool:
    """
    Validate that retrieved data looks legitimate.
    
    Args:
        text: Retrieved text to validate
        min_length: Minimum acceptable text length
        
    Returns:
        True if text appears valid, False if empty or sentinel
    """
    if not text:
        return False
    # Check for sentinel indicating no products found
    if "NO_PRODUCTS_FOUND" in text:
        return False
    if len(text.strip()) < min_length:
        return False
    if re.match(r"^\s*Action:", text.strip()):
        return False
    return True
