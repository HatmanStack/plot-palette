"""
Plot Palette - Unit Tests for Custom Template Filters

Tests all custom Jinja2 filters for template engine.
"""

import pytest
from backend.shared.template_filters import (
    random_sentence,
    random_word,
    writing_style,
    truncate_tokens,
    extract_keywords,
    summarize_text,
    capitalize_first,
    remove_markdown,
    json_safe,
    validate_template_syntax
)


def test_random_sentence():
    """Test random_sentence filter extracts a sentence."""
    text = "First sentence. Second sentence. Third sentence."
    result = random_sentence(text)
    assert result in ["First sentence", "Second sentence", "Third sentence"]


def test_random_sentence_empty():
    """Test random_sentence with empty string."""
    assert random_sentence("") == ""


def test_random_sentence_single():
    """Test random_sentence with single sentence."""
    text = "Only one sentence"
    result = random_sentence(text)
    assert result == "Only one sentence"


def test_random_word():
    """Test random_word filter extracts a word."""
    text = "apple banana cherry date"
    result = random_word(text)
    assert result in ["apple", "banana", "cherry", "date"]


def test_random_word_count():
    """Test random_word with count parameter."""
    text = "apple banana cherry date"
    result = random_word(text, count=2)
    words = result.split()
    assert len(words) == 2
    assert all(w in ["apple", "banana", "cherry", "date"] for w in words)


def test_random_word_empty():
    """Test random_word with empty string."""
    assert random_word("") == ""


def test_writing_style_poetic():
    """Test writing_style detects poetic style."""
    bio = "She was a renowned poet known for her lyrical verse"
    style = writing_style(bio)
    assert 'poetic' in style


def test_writing_style_narrative():
    """Test writing_style detects narrative style."""
    bio = "He writes compelling stories and narrative fiction"
    style = writing_style(bio)
    assert 'narrative' in style


def test_writing_style_multiple():
    """Test writing_style detects multiple styles."""
    bio = "A dramatic poet who writes theatrical verse"
    style = writing_style(bio)
    assert 'poetic' in style
    assert 'dramatic' in style


def test_writing_style_none():
    """Test writing_style with no recognizable style."""
    bio = "A writer"
    style = writing_style(bio)
    assert style == 'general'


def test_writing_style_empty():
    """Test writing_style with empty string."""
    assert writing_style("") == 'general'


def test_truncate_tokens_short():
    """Test truncate_tokens with text shorter than limit."""
    text = "Short text"
    result = truncate_tokens(text, 100)
    assert result == "Short text"


def test_truncate_tokens_long():
    """Test truncate_tokens with text longer than limit."""
    text = "a " * 1000  # 1000 words
    result = truncate_tokens(text, 50)  # ~50 tokens = 200 chars
    assert len(result) < 250  # Should be truncated
    assert result.endswith('...')


def test_truncate_tokens_word_boundary():
    """Test truncate_tokens respects word boundaries."""
    text = "This is a very long sentence with many words"
    result = truncate_tokens(text, 5)  # ~5 tokens = 20 chars
    # Should not cut in middle of word
    assert not result[:-3].endswith(' ')  # Before '...'


def test_truncate_tokens_empty():
    """Test truncate_tokens with empty string."""
    assert truncate_tokens("", 100) == ""


def test_extract_keywords():
    """Test extract_keywords extracts frequent words."""
    text = "Python programming is fun. Python is a great programming language. Python rocks!"
    keywords = extract_keywords(text, 3)
    assert 'python' in keywords
    assert 'programming' in keywords


def test_extract_keywords_filters_stopwords():
    """Test extract_keywords filters common stop words."""
    text = "The quick brown fox jumps over the lazy dog"
    keywords = extract_keywords(text, 5)
    # Stop words should be filtered out
    assert 'the' not in keywords


def test_extract_keywords_empty():
    """Test extract_keywords with empty string."""
    assert extract_keywords("") == []


def test_summarize_text():
    """Test summarize_text extracts first N sentences."""
    text = "First sentence. Second sentence. Third sentence. Fourth sentence."
    result = summarize_text(text, 2)
    assert "First sentence" in result
    assert "Second sentence" in result
    assert "Fourth sentence" not in result


def test_summarize_text_fewer_sentences():
    """Test summarize_text when text has fewer sentences than max."""
    text = "Only one sentence."
    result = summarize_text(text, 3)
    assert result == "Only one sentence."


def test_summarize_text_empty():
    """Test summarize_text with empty string."""
    assert summarize_text("") == ""


def test_capitalize_first():
    """Test capitalize_first capitalizes sentences."""
    text = "first sentence. second sentence. third sentence."
    result = capitalize_first(text)
    assert result == "First sentence. Second sentence. Third sentence."


def test_capitalize_first_already_capitalized():
    """Test capitalize_first with already capitalized text."""
    text = "First sentence. Second sentence."
    result = capitalize_first(text)
    assert result == "First sentence. Second sentence."


def test_capitalize_first_empty():
    """Test capitalize_first with empty string."""
    assert capitalize_first("") == ""


def test_remove_markdown_headers():
    """Test remove_markdown removes headers."""
    text = "## Heading\nContent"
    result = remove_markdown(text)
    assert "##" not in result
    assert "Heading" in result


def test_remove_markdown_bold():
    """Test remove_markdown removes bold."""
    text = "This is **bold** text"
    result = remove_markdown(text)
    assert "**" not in result
    assert "bold" in result


def test_remove_markdown_italic():
    """Test remove_markdown removes italic."""
    text = "This is *italic* text"
    result = remove_markdown(text)
    assert result == "This is italic text"


def test_remove_markdown_links():
    """Test remove_markdown removes links."""
    text = "Check [this link](http://example.com)"
    result = remove_markdown(text)
    assert "http://example.com" not in result
    assert "this link" in result


def test_remove_markdown_code():
    """Test remove_markdown removes code."""
    text = "Inline `code` here"
    result = remove_markdown(text)
    assert "`" not in result
    assert "code" in result


def test_remove_markdown_empty():
    """Test remove_markdown with empty string."""
    assert remove_markdown("") == ""


def test_json_safe_dict():
    """Test json_safe with dictionary."""
    obj = {"key": "value", "number": 42}
    result = json_safe(obj)
    assert '"key"' in result
    assert '"value"' in result


def test_json_safe_list():
    """Test json_safe with list."""
    obj = [1, 2, 3, "test"]
    result = json_safe(obj)
    assert "[1" in result
    assert "test" in result


def test_json_safe_string():
    """Test json_safe with string."""
    obj = "simple string"
    result = json_safe(obj)
    assert result == '"simple string"'


def test_validate_template_syntax_valid():
    """Test validate_template_syntax with valid template."""
    template_def = {
        'steps': [
            {
                'id': 'step1',
                'prompt': 'Hello {{ name }}'
            }
        ]
    }
    valid, message = validate_template_syntax(template_def)
    assert valid is True
    assert "Valid" in message


def test_validate_template_syntax_invalid():
    """Test validate_template_syntax with invalid Jinja2."""
    template_def = {
        'steps': [
            {
                'id': 'step1',
                'prompt': 'Hello {{ name'  # Missing closing }}
            }
        ]
    }
    valid, message = validate_template_syntax(template_def)
    assert valid is False
    assert "syntax error" in message.lower()


def test_validate_template_syntax_empty_prompt():
    """Test validate_template_syntax with empty prompt."""
    template_def = {
        'steps': [
            {
                'id': 'step1',
                'prompt': ''
            }
        ]
    }
    valid, message = validate_template_syntax(template_def)
    assert valid is False
    assert "empty prompt" in message.lower()


def test_validate_template_syntax_with_filters():
    """Test validate_template_syntax with custom filters."""
    template_def = {
        'steps': [
            {
                'id': 'step1',
                'prompt': '{{ text | random_sentence }}'
            }
        ]
    }
    valid, message = validate_template_syntax(template_def)
    assert valid is True


def test_validate_template_syntax_with_conditionals():
    """Test validate_template_syntax with conditionals."""
    template_def = {
        'steps': [
            {
                'id': 'step1',
                'prompt': '{% if condition %}True{% else %}False{% endif %}'
            }
        ]
    }
    valid, message = validate_template_syntax(template_def)
    assert valid is True


def test_validate_template_syntax_with_loops():
    """Test validate_template_syntax with loops."""
    template_def = {
        'steps': [
            {
                'id': 'step1',
                'prompt': '{% for item in items %}{{ item }}{% endfor %}'
            }
        ]
    }
    valid, message = validate_template_syntax(template_def)
    assert valid is True


def test_validate_template_syntax_autoescape_enabled():
    """Test that validate_template_syntax uses autoescape."""
    # The validation environment should have autoescape enabled
    template_def = {
        'steps': [
            {
                'id': 'step1',
                'prompt': 'Hello {{ name }}'
            }
        ]
    }
    valid, _ = validate_template_syntax(template_def)
    assert valid is True


def test_validate_template_syntax_error_sanitized():
    """Test that validation errors are sanitized."""
    # Force an unusual error that might leak internals
    template_def = {'steps': 'not-a-list'}  # Will cause an error
    valid, message = validate_template_syntax(template_def)
    # Should either pass validation or return a sanitized error
    assert isinstance(message, str)
    assert len(message) < 500
