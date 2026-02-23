"""
Plot Palette - Custom Jinja2 Filters for Template Engine

This module provides custom filters for LLM prompt generation including
text manipulation, token operations, and data extraction.
"""

import logging
import random
import re
from collections import Counter
from typing import Any

logger = logging.getLogger(__name__)

# Pre-compiled regex to reject dangerous SSTI patterns before parsing
_DANGEROUS_PATTERNS = re.compile(
    r"__\w+__|"
    r"\battr\s*\(|\bgetattr\s*\(|\bsetattr\s*\(|"
    r"\bimport\s*\(|\beval\s*\(|\bexec\s*\(|\bopen\s*\(|"
    r"\bos\.",
    re.IGNORECASE,
)

# Pre-compiled regex patterns for hot-path functions
_SENTENCE_SPLIT_RE = re.compile(r"[.!?]+")
_WORD_RE = re.compile(r"\b\w+\b")
_STYLE_PATTERNS = {
    "poetic": re.compile(r"\b(poet|poetry|verse|lyrical)\b", re.IGNORECASE),
    "narrative": re.compile(r"\b(story|narrative|tale|chronicle)\b", re.IGNORECASE),
    "descriptive": re.compile(r"\b(describe|vivid|detailed)\b", re.IGNORECASE),
    "minimalist": re.compile(r"\b(minimal|sparse|concise|brief)\b", re.IGNORECASE),
    "verbose": re.compile(r"\b(elaborate|detailed|extensive)\b", re.IGNORECASE),
    "dramatic": re.compile(r"\b(drama|theatrical|intense)\b", re.IGNORECASE),
}


def random_sentence(text: str) -> str:
    """
    Extract a random sentence from text.

    Args:
        text: Input text with multiple sentences

    Returns:
        str: A randomly selected sentence
    """
    if not text:
        return ""

    sentences = _SENTENCE_SPLIT_RE.split(text)
    sentences = [s.strip() for s in sentences if s.strip()]

    return random.choice(sentences) if sentences else text


def writing_style(biography: str) -> str:
    """
    Extract writing style keywords from author biography.

    Args:
        biography: Author biography text

    Returns:
        str: Comma-separated style keywords
    """
    if not biography:
        return "general"

    style_keywords = []

    for style, pattern in _STYLE_PATTERNS.items():
        if pattern.search(biography):
            style_keywords.append(style)

    return ", ".join(style_keywords) if style_keywords else "general"


def truncate_tokens(text: str, max_tokens: int) -> str:
    """
    Truncate text to approximately N tokens.

    Uses rough estimate: 1 token ~= 4 characters.

    Args:
        text: Input text
        max_tokens: Maximum number of tokens

    Returns:
        str: Truncated text with '...' if truncated
    """
    if not text:
        return ""

    max_chars = max_tokens * 4
    if len(text) <= max_chars:
        return text

    # Truncate at word boundary
    truncated = text[:max_chars]
    last_space = truncated.rfind(" ")
    if last_space > 0:
        truncated = truncated[:last_space]

    return truncated + "..."


def extract_keywords(text: str, count: int = 5) -> list[str]:
    """
    Extract top N keywords from text using frequency analysis.

    Args:
        text: Input text
        count: Number of keywords to extract

    Returns:
        List[str]: Most frequent keywords
    """
    if not text:
        return []

    # Common stop words to filter out
    stop_words = {
        "the",
        "a",
        "an",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
        "from",
        "as",
        "is",
        "was",
        "are",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "should",
        "could",
        "may",
        "might",
        "this",
        "that",
        "these",
        "those",
        "it",
        "its",
    }

    # Extract words
    words = _WORD_RE.findall(text.lower())
    words = [w for w in words if w not in stop_words and len(w) > 3]

    # Count frequency
    word_freq = Counter(words)

    # Return top N
    return [word for word, _ in word_freq.most_common(count)]


def validate_template_syntax(template_def: dict[str, Any]) -> tuple[bool, str]:
    """
    Validate Jinja2 syntax in template definition.

    Args:
        template_def: Template definition dictionary with steps

    Returns:
        Tuple[bool, str]: (is_valid, error_message)
    """
    import jinja2

    try:
        env = jinja2.Environment(
            autoescape=jinja2.select_autoescape(default_for_string=True, default=True),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Register custom filters for validation
        env.filters.update(CUSTOM_FILTERS)

        # Validate each step's prompt
        for step in template_def.get("steps", []):
            prompt = step.get("prompt", "")
            if not prompt:
                return False, f"Step '{step.get('id', 'unknown')}' has empty prompt"

            # Check for dangerous SSTI patterns before parsing
            if _DANGEROUS_PATTERNS.search(prompt):
                return (
                    False,
                    f"Step '{step.get('id', 'unknown')}' contains forbidden pattern",
                )

            # Try to parse template
            try:
                env.from_string(prompt)
            except jinja2.TemplateSyntaxError as e:
                return (
                    False,
                    f"Template syntax error in step '{step.get('id', 'unknown')}': {str(e)}",
                )

        return True, "Valid template syntax"

    except jinja2.TemplateSyntaxError as e:
        return False, f"Template syntax error: {str(e)}"
    except Exception as e:
        logger.error(f"Template validation error: {str(e)}", exc_info=True)
        from .utils import sanitize_error_message

        return False, f"Template validation error: {sanitize_error_message(str(e))}"


# Register all custom filters
CUSTOM_FILTERS = {
    "random_sentence": random_sentence,
    "writing_style": writing_style,
    "truncate_tokens": truncate_tokens,
    "extract_keywords": extract_keywords,
}
