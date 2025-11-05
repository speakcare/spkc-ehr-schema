"""Text sanitization utilities for removing HTML tags and JSON-breaking characters."""

import re
from typing import Any


def sanitize_for_json(text: Any) -> Any:
    """
    Remove HTML tags and JSON-breaking characters; pass through non-strings unchanged.
    
    This function sanitizes text by:
    1. Removing HTML tags
    2. Removing JSON-breaking characters (quotes, backslashes, brackets, braces)
    3. Removing control characters (newlines, tabs, etc.)
    4. Normalizing whitespace
    
    Args:
        text: The text to sanitize. Non-string values are returned unchanged.
    
    Returns:
        Sanitized text with special characters removed, or the original value if not a string.
    
    Examples:
        >>> sanitize_for_json('If "yes" then proceed')
        'If yes then proceed'
        >>> sanitize_for_json('<b>Bold text</b>')
        'Bold text'
        >>> sanitize_for_json(123)
        123
        >>> sanitize_for_json(None)
        None
    """
    if not isinstance(text, str):
        return text
    
    # Step 1: Remove HTML tags
    clean_text = re.sub(r"<[^>]+>", "", text)
    
    # Step 2: Remove JSON-breaking characters
    # Replace double quotes with empty string
    clean_text = clean_text.replace('"', '')
    
    # Replace backslashes with space
    clean_text = clean_text.replace('\\', ' ')
    
    # Remove control characters (newlines, tabs, carriage returns, etc.)
    clean_text = re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', clean_text)
    
    # Remove single quotes
    clean_text = clean_text.replace("'", "")
    
    # Remove brackets and braces that can confuse parsers
    clean_text = re.sub(r'[\[\]{}]', '', clean_text)
    
    # Step 3: Normalize whitespace
    return " ".join(clean_text.split())

