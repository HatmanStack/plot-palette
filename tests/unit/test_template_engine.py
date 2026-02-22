"""
Unit tests for template engine.

Tests Jinja2 template rendering, multi-step execution, custom filters,
and Bedrock API call formatting.
"""

import pytest
import json
from unittest.mock import MagicMock, patch, Mock

from backend.ecs_tasks.worker.template_engine import TemplateEngine
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
    validate_template_syntax,
)


class TestTemplateEngine:
    """Test TemplateEngine class."""

    def test_template_engine_initialization(self):
        """Test engine initialization without DynamoDB."""
        engine = TemplateEngine()
        assert engine.env is not None
        assert 'random_sentence' in engine.env.filters
        assert 'writing_style' in engine.env.filters

    def test_render_step_simple(self):
        """Test rendering a simple template step."""
        engine = TemplateEngine()
        step_def = {
            'id': 'test',
            'prompt': 'Generate a story about {{ author.name }}'
        }
        context = {'author': {'name': 'Jane Doe'}}

        rendered = engine.render_step(step_def, context)
        assert 'Jane Doe' in rendered
        assert 'Generate a story about Jane Doe' == rendered

    def test_render_step_with_nested_fields(self):
        """Test rendering with nested data fields."""
        engine = TemplateEngine()
        step_def = {
            'id': 'test',
            'prompt': 'Author: {{ author.name }}\nBio: {{ author.biography[:50] }}'
        }
        context = {
            'author': {
                'name': 'Jane Doe',
                'biography': 'A prolific writer known for her poetic style and narrative depth.'
            }
        }

        rendered = engine.render_step(step_def, context)
        assert 'Jane Doe' in rendered
        assert 'A prolific writer' in rendered

    def test_render_step_with_custom_filter(self):
        """Test rendering with custom Jinja2 filter."""
        engine = TemplateEngine()
        step_def = {
            'id': 'test',
            'prompt': 'Random sentence: {{ text | random_sentence }}'
        }
        context = {
            'text': 'First sentence. Second sentence. Third sentence.'
        }

        rendered = engine.render_step(step_def, context)
        assert 'Random sentence:' in rendered
        # Should contain one of the sentences
        assert 'sentence' in rendered.lower()

    def test_render_step_with_conditionals(self):
        """Test template with conditional logic."""
        engine = TemplateEngine()
        step_def = {
            'id': 'test',
            'prompt': '{% if author.genre == "poetry" %}Generate verse{% else %}Generate prose{% endif %}'
        }

        # Test poetry branch
        context = {'author': {'genre': 'poetry'}}
        rendered = engine.render_step(step_def, context)
        assert 'Generate verse' == rendered

        # Test prose branch
        context = {'author': {'genre': 'fiction'}}
        rendered = engine.render_step(step_def, context)
        assert 'Generate prose' == rendered

    def test_render_step_with_loops(self):
        """Test template with loops."""
        engine = TemplateEngine()
        step_def = {
            'id': 'test',
            'prompt': 'Authors: {% for author in authors %}{{ author.name }}{% if not loop.last %}, {% endif %}{% endfor %}'
        }
        context = {
            'authors': [
                {'name': 'Jane Doe'},
                {'name': 'John Smith'},
                {'name': 'Alice Johnson'}
            ]
        }

        rendered = engine.render_step(step_def, context)
        assert 'Authors: Jane Doe, John Smith, Alice Johnson' == rendered

    @patch('backend.ecs_tasks.worker.template_engine.TemplateEngine.call_bedrock')
    def test_execute_template_single_step(self, mock_bedrock):
        """Test executing single-step template."""
        mock_bedrock.return_value = "Generated question about Jane Doe"

        engine = TemplateEngine()
        template_def = {
            'steps': [
                {
                    'id': 'question',
                    'model': 'meta.llama3-1-8b-instruct-v1:0',
                    'prompt': 'Generate question about {{ author.name }}'
                }
            ]
        }
        seed_data = {'author': {'name': 'Jane Doe'}}
        bedrock_client = MagicMock()

        results = engine.execute_template(template_def, seed_data, bedrock_client)

        assert 'question' in results
        assert results['question']['output'] == "Generated question about Jane Doe"
        assert results['question']['model'] == 'meta.llama3-1-8b-instruct-v1:0'
        mock_bedrock.assert_called_once()

    @patch('backend.ecs_tasks.worker.template_engine.TemplateEngine.call_bedrock')
    def test_execute_template_multi_step(self, mock_bedrock):
        """Test executing multi-step template with context propagation."""
        mock_bedrock.side_effect = [
            "What inspired Jane Doe's writing?",
            "Jane Doe was inspired by her childhood experiences."
        ]

        engine = TemplateEngine()
        template_def = {
            'steps': [
                {
                    'id': 'question',
                    'model': 'meta.llama3-1-8b-instruct-v1:0',
                    'prompt': 'Generate question about {{ author.name }}'
                },
                {
                    'id': 'answer',
                    'model': 'anthropic.claude-3-5-sonnet-20241022-v2:0',
                    'prompt': 'Answer this question: {{ steps.question.output }}'
                }
            ]
        }
        seed_data = {'author': {'name': 'Jane Doe'}}
        bedrock_client = MagicMock()

        results = engine.execute_template(template_def, seed_data, bedrock_client)

        assert 'question' in results
        assert 'answer' in results
        assert results['question']['output'] == "What inspired Jane Doe's writing?"
        assert results['answer']['output'] == "Jane Doe was inspired by her childhood experiences."
        assert mock_bedrock.call_count == 2

    @patch('backend.ecs_tasks.worker.template_engine.TemplateEngine.call_bedrock')
    def test_execute_template_with_model_tier(self, mock_bedrock):
        """Test template execution with model tier resolution."""
        mock_bedrock.return_value = "Output"

        engine = TemplateEngine()
        template_def = {
            'steps': [
                {
                    'id': 'step1',
                    'model_tier': 'tier-1',
                    'prompt': 'Test prompt'
                }
            ]
        }
        seed_data = {}
        bedrock_client = MagicMock()

        results = engine.execute_template(template_def, seed_data, bedrock_client)

        assert 'step1' in results
        # Should resolve tier-1 to actual model
        assert 'llama' in results['step1']['model'].lower()

    @patch('backend.ecs_tasks.worker.template_engine.TemplateEngine.call_bedrock')
    def test_execute_template_error_handling(self, mock_bedrock):
        """Test error handling in template execution."""
        mock_bedrock.side_effect = Exception("Bedrock API error")

        engine = TemplateEngine()
        template_def = {
            'steps': [
                {
                    'id': 'step1',
                    'model': 'meta.llama3-1-8b-instruct-v1:0',
                    'prompt': 'Test'
                }
            ]
        }
        seed_data = {}
        bedrock_client = MagicMock()

        results = engine.execute_template(template_def, seed_data, bedrock_client)

        assert 'step1' in results
        assert 'error' in results['step1']
        assert 'Bedrock API error' in results['step1']['error']

    def test_call_bedrock_claude(self):
        """Test Bedrock call formatting for Claude models."""
        engine = TemplateEngine()
        mock_client = MagicMock()
        mock_response = {
            'body': Mock(read=lambda: json.dumps({
                'content': [{'text': 'Generated text'}]
            }).encode())
        }
        mock_client.invoke_model.return_value = mock_response

        result = engine.call_bedrock(
            mock_client,
            'anthropic.claude-3-5-sonnet-20241022-v2:0',
            'Test prompt'
        )

        assert result == 'Generated text'

        # Verify request format
        call_args = mock_client.invoke_model.call_args
        body = json.loads(call_args[1]['body'])
        assert body['messages'][0]['role'] == 'user'
        assert body['messages'][0]['content'][0]['text'] == 'Test prompt'
        assert 'anthropic_version' in body

    def test_call_bedrock_llama(self):
        """Test Bedrock call formatting for Llama models."""
        engine = TemplateEngine()
        mock_client = MagicMock()
        mock_response = {
            'body': Mock(read=lambda: json.dumps({
                'generation': 'Llama generated text'
            }).encode())
        }
        mock_client.invoke_model.return_value = mock_response

        result = engine.call_bedrock(
            mock_client,
            'meta.llama3-1-8b-instruct-v1:0',
            'Test prompt'
        )

        assert result == 'Llama generated text'

        # Verify request format
        call_args = mock_client.invoke_model.call_args
        body = json.loads(call_args[1]['body'])
        assert body['prompt'] == 'Test prompt'
        assert 'max_gen_len' in body

    def test_call_bedrock_mistral(self):
        """Test Bedrock call formatting for Mistral models."""
        engine = TemplateEngine()
        mock_client = MagicMock()
        mock_response = {
            'body': Mock(read=lambda: json.dumps({
                'outputs': [{'text': 'Mistral generated text'}]
            }).encode())
        }
        mock_client.invoke_model.return_value = mock_response

        result = engine.call_bedrock(
            mock_client,
            'mistral.mistral-7b-instruct-v0:2',
            'Test prompt'
        )

        assert result == 'Mistral generated text'


class TestCustomFilters:
    """Test custom Jinja2 filters."""

    def test_random_sentence(self):
        """Test random_sentence filter."""
        text = "First sentence. Second sentence. Third sentence."
        result = random_sentence(text)
        assert result in ['First sentence', 'Second sentence', 'Third sentence']

    def test_random_sentence_empty(self):
        """Test random_sentence with empty input."""
        assert random_sentence("") == ""

    def test_random_word(self):
        """Test random_word filter."""
        text = "apple banana cherry"
        result = random_word(text)
        assert result in ['apple', 'banana', 'cherry']

    def test_random_word_multiple(self):
        """Test random_word with count parameter."""
        text = "one two three four five"
        result = random_word(text, count=3)
        words = result.split()
        assert len(words) == 3

    def test_writing_style_poetic(self):
        """Test writing_style filter with poetic biography."""
        bio = "Jane Doe is a celebrated poet known for her lyrical verse."
        result = writing_style(bio)
        assert 'poetic' in result

    def test_writing_style_narrative(self):
        """Test writing_style filter with narrative biography."""
        bio = "John writes compelling stories and narrative chronicles."
        result = writing_style(bio)
        assert 'narrative' in result

    def test_writing_style_empty(self):
        """Test writing_style with empty input."""
        assert writing_style("") == 'general'

    def test_truncate_tokens(self):
        """Test truncate_tokens filter."""
        text = "This is a long text " * 100
        result = truncate_tokens(text, max_tokens=50)
        assert len(result) <= 50 * 4 + 3  # max_chars + '...'
        assert result.endswith('...')

    def test_truncate_tokens_short(self):
        """Test truncate_tokens with short text."""
        text = "Short text"
        result = truncate_tokens(text, max_tokens=100)
        assert result == text
        assert not result.endswith('...')

    def test_extract_keywords(self):
        """Test extract_keywords filter."""
        text = "Python programming language for data science and machine learning"
        keywords = extract_keywords(text, count=3)
        assert isinstance(keywords, list)
        assert len(keywords) <= 3
        assert 'python' in keywords or 'programming' in keywords

    def test_summarize_text(self):
        """Test summarize_text filter."""
        text = "First sentence. Second sentence. Third sentence. Fourth sentence."
        result = summarize_text(text, max_sentences=2)
        assert 'First sentence' in result
        assert 'Second sentence' in result
        assert 'Fourth sentence' not in result

    def test_capitalize_first(self):
        """Test capitalize_first filter."""
        text = "first sentence. second sentence. third sentence"
        result = capitalize_first(text)
        assert result == "First sentence. Second sentence. Third sentence"

    def test_remove_markdown(self):
        """Test remove_markdown filter."""
        text = "# Header\n**bold** and *italic* with `code`"
        result = remove_markdown(text)
        assert '#' not in result
        assert '**' not in result
        assert '*' not in result
        assert '`' not in result
        assert 'Header' in result
        assert 'bold' in result

    def test_json_safe(self):
        """Test json_safe filter."""
        obj = {'key': 'value', 'number': 42}
        result = json_safe(obj)
        assert '"key": "value"' in result
        assert '"number": 42' in result

    def test_json_safe_invalid(self):
        """Test json_safe with non-serializable object."""
        obj = lambda x: x  # Functions are not JSON serializable
        result = json_safe(obj)
        assert isinstance(result, str)


class TestTemplateSyntaxValidation:
    """Test template syntax validation."""

    def test_validate_template_syntax_valid(self):
        """Test validation of valid template."""
        template_def = {
            'steps': [
                {
                    'id': 'step1',
                    'prompt': 'Generate text about {{ author.name }}'
                }
            ]
        }
        is_valid, error = validate_template_syntax(template_def)
        assert is_valid is True
        assert error == "Valid template syntax"

    def test_validate_template_syntax_invalid_jinja(self):
        """Test validation of invalid Jinja2 syntax."""
        template_def = {
            'steps': [
                {
                    'id': 'step1',
                    'prompt': 'Bad template {{ unclosed'
                }
            ]
        }
        is_valid, error = validate_template_syntax(template_def)
        assert is_valid is False
        assert 'syntax error' in error.lower()

    def test_validate_template_syntax_empty_prompt(self):
        """Test validation of empty prompt."""
        template_def = {
            'steps': [
                {
                    'id': 'step1',
                    'prompt': ''
                }
            ]
        }
        is_valid, error = validate_template_syntax(template_def)
        assert is_valid is False
        assert 'empty prompt' in error.lower()

    def test_validate_template_syntax_with_filters(self):
        """Test validation of template with custom filters."""
        template_def = {
            'steps': [
                {
                    'id': 'step1',
                    'prompt': '{{ text | random_sentence | capitalize_first }}'
                }
            ]
        }
        is_valid, error = validate_template_syntax(template_def)
        assert is_valid is True


class TestSandboxedEnvironment:
    """Test that template engine uses SandboxedEnvironment."""

    def test_sandbox_rejects_dunder_access(self):
        """Test that sandboxed env raises SecurityError on dunder access."""
        from jinja2.sandbox import SecurityError

        engine = TemplateEngine()
        step_def = {
            'id': 'test',
            'prompt': '{{ "".__class__.__mro__ }}'
        }
        context = {}

        with pytest.raises(SecurityError):
            engine.render_step(step_def, context)

    def test_sandbox_allows_normal_templates(self):
        """Test that sandboxed env allows normal template rendering."""
        engine = TemplateEngine()
        step_def = {
            'id': 'test',
            'prompt': 'Hello {{ name }}, you are {{ age }} years old.'
        }
        context = {'name': 'Alice', 'age': 30}

        rendered = engine.render_step(step_def, context)
        assert rendered == 'Hello Alice, you are 30 years old.'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
