"""
Plot Palette - Custom Jinja2 Filters for Template Engine

This module provides custom filters for LLM prompt generation including
text manipulation, token operations, and data extraction.
"""

import json
import logging
import random
import re
from collections import Counter
from typing import Any, List, Tuple

from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


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

    sentences = re.split(r"[.!?]+", text)
    sentences = [s.strip() for s in sentences if s.strip()]

    return random.choice(sentences) if sentences else text


def random_word(text: str, count: int = 1) -> str:
    """
    Extract random word(s) from text.

    Args:
        text: Input text
        count: Number of words to extract

    Returns:
        str: Randomly selected word(s)
    """
    if not text:
        return ""

    words = text.split()
    if not words:
        return ""

    if count == 1:
        return random.choice(words)
    else:
        selected = random.sample(words, min(count, len(words)))
        return " ".join(selected)


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

    style_patterns = {
        "poetic": r"\b(poet|poetry|verse|lyrical)\b",
        "narrative": r"\b(story|narrative|tale|chronicle)\b",
        "descriptive": r"\b(describe|vivid|detailed)\b",
        "minimalist": r"\b(minimal|sparse|concise|brief)\b",
        "verbose": r"\b(elaborate|detailed|extensive)\b",
        "dramatic": r"\b(drama|theatrical|intense)\b",
    }

    for style, pattern in style_patterns.items():
        if re.search(pattern, biography, re.IGNORECASE):
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


def extract_keywords(text: str, count: int = 5) -> List[str]:
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
    words = re.findall(r"\b\w+\b", text.lower())
    words = [w for w in words if w not in stop_words and len(w) > 3]

    # Count frequency
    word_freq = Counter(words)

    # Return top N
    return [word for word, _ in word_freq.most_common(count)]


def summarize_text(text: str, max_sentences: int = 3) -> str:
    """
    Extract first N sentences as summary.

    Args:
        text: Input text
        max_sentences: Number of sentences to extract

    Returns:
        str: Summary with first N sentences
    """
    if not text:
        return ""

    sentences = re.split(r"[.!?]+", text)
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        return text

    return ". ".join(sentences[:max_sentences]) + "."


def capitalize_first(text: str) -> str:
    """
    Capitalize first letter of each sentence.

    Args:
        text: Input text

    Returns:
        str: Text with capitalized sentences
    """
    if not text:
        return ""

    return ". ".join(s.strip().capitalize() for s in text.split(". "))


def remove_markdown(text: str) -> str:
    """
    Remove markdown formatting from text.

    Args:
        text: Markdown-formatted text

    Returns:
        str: Plain text without markdown
    """
    if not text:
        return ""

    # Remove headers
    text = re.sub(r"#+\s+", "", text)
    # Remove bold
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    # Remove italic
    text = re.sub(r"\*(.*?)\*", r"\1", text)
    # Remove links
    text = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", text)
    # Remove code blocks
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    # Remove inline code
    text = re.sub(r"`(.*?)`", r"\1", text)

    return text


def json_safe(obj: Any) -> str:
    """
    Convert object to JSON-safe string.

    Args:
        obj: Any Python object

    Returns:
        str: JSON-formatted string
    """
    try:
        return json.dumps(obj, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(obj)


def validate_template_syntax(template_def: dict) -> Tuple[bool, str]:
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


def validate_template_includes(template_def: dict, templates_table) -> Tuple[bool, str]:
    """
    Validate that all included templates exist in DynamoDB.

    Args:
        template_def: Template definition dictionary with steps
        templates_table: boto3 DynamoDB Table resource

    Returns:
        Tuple[bool, str]: (is_valid, error_message)
    """
    try:
        # Collect all include names across all steps
        all_includes = set()

        for step in template_def.get("steps", []):
            prompt = step.get("prompt", "")

            # Find all {% include 'template-name' %} references
            all_includes.update(re.findall(r"{%\s*include\s+'([^']+)'\s*%}", prompt))
            all_includes.update(re.findall(r'{%\s*include\s+"([^"]+)"\s*%}', prompt))

        if not all_includes:
            return True, "No includes to validate"

        # Batch lookup in chunks of 100 (DynamoDB BatchGetItem limit)
        found_ids = set()
        include_list = list(all_includes)

        for i in range(0, len(include_list), 100):
            chunk = include_list[i : i + 100]

            try:
                for name in chunk:
                    resp = templates_table.get_item(Key={"template_id": name, "version": 1})
                    if "Item" in resp:
                        found_ids.add(name)
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "")
                if error_code in (
                    "ThrottlingException",
                    "InternalServerError",
                    "ServiceUnavailable",
                    "ProvisionedThroughputExceededException",
                ):
                    raise  # Propagate infrastructure errors
                logger.error(f"Error checking include: {str(e)}")

        missing_includes = all_includes - found_ids
        if missing_includes:
            return False, f"Missing included templates: {', '.join(sorted(missing_includes))}"

        return True, "All includes valid"

    except ClientError as e:
        # Propagate infrastructure errors (throttling, internal server errors)
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code in (
            "ThrottlingException",
            "InternalServerError",
            "ServiceUnavailable",
            "ProvisionedThroughputExceededException",
        ):
            raise
        logger.error(f"Include validation error: {str(e)}", exc_info=True)
        from .utils import sanitize_error_message

        return False, f"Include validation error: {sanitize_error_message(str(e))}"
    except Exception as e:
        logger.error(f"Include validation error: {str(e)}", exc_info=True)
        from .utils import sanitize_error_message

        return False, f"Include validation error: {sanitize_error_message(str(e))}"


# Register all custom filters
CUSTOM_FILTERS = {
    "random_sentence": random_sentence,
    "random_word": random_word,
    "writing_style": writing_style,
    "truncate_tokens": truncate_tokens,
    "extract_keywords": extract_keywords,
    "summarize_text": summarize_text,
    "capitalize_first": capitalize_first,
    "remove_markdown": remove_markdown,
    "json_safe": json_safe,
}
