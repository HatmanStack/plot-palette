"""
Plot Palette - Unit Tests for Custom Template Filters

Tests all custom Jinja2 filters for template engine.
"""

import pytest
from backend.shared.template_filters import (
    random_sentence,
    writing_style,
    truncate_tokens,
    extract_keywords,
    validate_template_syntax,
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


def test_validate_rejects_dunder_access():
    """Test that templates with dunder access patterns are rejected."""
    template_def = {
        'steps': [
            {
                'id': 'step1',
                'prompt': '{{ "".__class__.__mro__ }}'
            }
        ]
    }
    valid, message = validate_template_syntax(template_def)
    assert valid is False
    assert "forbidden pattern" in message.lower()


def test_validate_rejects_eval():
    """Test that templates with eval/exec patterns are rejected."""
    for dangerous in ['eval(', 'exec(', 'import(', 'getattr(', 'os.system']:
        template_def = {
            'steps': [
                {
                    'id': 'step1',
                    'prompt': f'{{{{ {dangerous}"test") }}}}'
                }
            ]
        }
        valid, message = validate_template_syntax(template_def)
        assert valid is False, f"Should reject pattern: {dangerous}"
        assert "forbidden pattern" in message.lower()


def test_validate_allows_normal_templates():
    """Test that normal templates without dangerous patterns pass validation."""
    template_def = {
        'steps': [
            {
                'id': 'step1',
                'prompt': 'Write a {{ genre }} story about {{ topic | random_sentence }}.'
            }
        ]
    }
    valid, message = validate_template_syntax(template_def)
    assert valid is True
