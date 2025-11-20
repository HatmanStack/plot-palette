# Template Syntax Guide

Complete guide to writing prompt templates in Plot Palette using Jinja2.

## Table of Contents

- [Basic Structure](#basic-structure)
- [Variables](#variables)
- [Filters](#filters)
- [Conditionals](#conditionals)
- [Loops](#loops)
- [Template Composition](#template-composition)
- [Macros](#macros)
- [Comments](#comments)
- [Best Practices](#best-practices)

## Basic Structure

Every template consists of metadata and one or more steps:

```yaml
template:
  id: my-template-v1
  name: "My Template"
  description: "What this template does"
  category: general
  is_public: false

  schema_requirements:
    - field1
    - field2.nested

  steps:
    - id: step1
      model: meta.llama3-1-8b-instruct-v1:0
      prompt: |
        Your prompt here...
```

### Metadata Fields

- **id**: Unique identifier (used for includes)
- **name**: Human-readable name
- **description**: What the template does
- **category**: Grouping (creative_writing, question_answer, etc.)
- **is_public**: Whether template is available to all users
- **schema_requirements**: Required fields in seed data

### Step Fields

- **id**: Step identifier (used to reference outputs)
- **model**: AWS Bedrock model ID or tier alias
- **prompt**: Jinja2 template string

## Variables

Access seed data using `{{ variable }}` syntax:

```jinja2
Hello, {{ name }}!

Author: {{ author.name }}
Biography: {{ author.biography }}
```

### Accessing Nested Fields

```jinja2
{{ character.personality.traits }}
{{ settings.environment.weather }}
```

### Step Outputs

Reference previous step outputs:

```jinja2
Previous step said: {{ steps.step1.output }}

Summary of outline: {{ steps.outline.output }}
```

## Filters

Filters modify variables using `|` syntax:

```jinja2
{{ text | filter_name }}
{{ text | filter1 | filter2 }}
{{ text | filter_with_param(10) }}
```

### Available Filters

See [Custom Filters Reference](./custom-filters-reference.md) for complete list.

**Common filters:**

```jinja2
{# Extract random sentence #}
{{ biography | random_sentence }}

{# Detect writing style #}
{{ author.biography | writing_style }}

{# Truncate to approximate token count #}
{{ long_text | truncate_tokens(500) }}

{# Extract keywords #}
{% for keyword in text | extract_keywords(5) %}
- {{ keyword }}
{% endfor %}

{# Summarize to N sentences #}
{{ article | summarize_text(3) }}
```

## Conditionals

Use `{% if %}` for conditional logic:

```jinja2
{% if difficulty == "easy" %}
Generate simple questions.
{% elif difficulty == "medium" %}
Generate analytical questions.
{% else %}
Generate complex questions.
{% endif %}
```

### Comparison Operators

- `==` equal
- `!=` not equal
- `<`, `>`, `<=`, `>=` comparisons
- `in` membership test
- `not` negation

```jinja2
{% if age >= 18 %}Adult{% endif %}
{% if name in ["Alice", "Bob"] %}Found{% endif %}
{% if not is_complete %}Incomplete{% endif %}
```

### Combining Conditions

```jinja2
{% if genre == "poetry" and style == "modern" %}
Modern poetry style
{% endif %}

{% if difficulty == "easy" or difficulty == "medium" %}
Beginner friendly
{% endif %}
```

## Loops

Iterate over lists with `{% for %}`:

```jinja2
{% for character in characters %}
- **{{ character.name }}**: {{ character.description }}
{% endfor %}
```

### Loop Variables

```jinja2
{% for item in items %}
{{ loop.index }}. {{ item }}  {# 1-indexed #}
{{ loop.index0 }}. {{ item }} {# 0-indexed #}
{% if loop.first %}First item!{% endif %}
{% if loop.last %}Last item!{% endif %}
{% endfor %}
```

### Loop with Conditional

```jinja2
{% for author in authors %}
{% if author.active %}
- {{ author.name }} ({{ author.genre }})
{% endif %}
{% endfor %}
```

## Template Composition

### Including Templates

Reuse template fragments with `{% include %}`:

```jinja2
{# Include fragment template #}
{% include 'style-instructions' %}

{# Fragment will be rendered with current context #}
```

**Fragment template** (style-instructions):
```yaml
template:
  id: style-instructions
  name: "Style Instructions Fragment"
  steps:
    - id: style
      prompt: |
        Write in {{ tone }} tone for {{ audience }} audience.
```

**Main template**:
```yaml
template:
  id: story-with-style
  name: "Story with Style"
  steps:
    - id: story
      prompt: |
        Write a story about {{ topic }}.

        {% include 'style-instructions' %}
```

### Requirements for Includes

1. Fragment template must exist in DynamoDB
2. Fragment must have same schema variables (or be provided in context)
3. Use fragment's template ID in include statement

## Macros

Define reusable template functions:

```jinja2
{# Define macro #}
{% macro difficulty_instruction(level) %}
{% if level == "easy" %}
Use simple language.
{% elif level == "medium" %}
Use moderate complexity.
{% else %}
Use advanced concepts.
{% endif %}
{% endmacro %}

{# Use macro #}
{{ difficulty_instruction(difficulty) }}

{# Use macro multiple times #}
For section 1: {{ difficulty_instruction("easy") }}
For section 2: {{ difficulty_instruction("hard") }}
```

### Macros with Multiple Parameters

```jinja2
{% macro format_question(number, question, answer) %}
**Q{{ number }}:** {{ question }}

**A{{ number }}:** {{ answer }}
{% endmacro %}

{{ format_question(1, "What is AI?", "Artificial Intelligence") }}
```

## Comments

Comments are not included in rendered output:

```jinja2
{# This is a comment #}

{#
  Multi-line
  comment
#}

{% if condition %}  {# Inline comment #}
  Content
{% endif %}
```

## Best Practices

### 1. Keep Prompts Focused

```jinja2
{# Good: Clear, single purpose #}
Generate 5 questions about {{ topic }}.

{# Avoid: Multiple tasks in one prompt #}
Generate questions, then answer them, then create a summary...
```

### 2. Use Filters for Text Processing

```jinja2
{# Good: Truncate long text #}
{{ article | truncate_tokens(500) }}

{# Avoid: Sending very long text #}
{{ entire_book }}
```

### 3. Provide Context in Prompts

```jinja2
{# Good: Clear context #}
Based on this biography:
{{ author.biography | summarize_text(3) }}

Generate a story in their style.

{# Avoid: Vague references #}
Generate a story.
```

### 4. Use Conditionals for Flexibility

```jinja2
{# Good: Adapt to different scenarios #}
{% if has_outline %}
Expand this outline: {{ outline }}
{% else %}
Create a story from scratch about {{ topic }}.
{% endif %}
```

### 5. Document Schema Requirements

Always list required fields in metadata:

```yaml
schema_requirements:
  - topic
  - author.name
  - author.style
  - word_count
```

### 6. Test Templates Before Deploying

Use the test endpoint:

```bash
curl -X POST $API/templates/{id}/test \
  -d '{"sample_data": {...}, "mock": true}'
```

### 7. Use Multi-Step for Complex Workflows

```yaml
steps:
  - id: outline
    model: meta.llama3-1-8b-instruct-v1:0
    prompt: Create outline...

  - id: expand
    model: anthropic.claude-3-5-sonnet-20241022-v2:0
    prompt: |
      Expand this outline:
      {{ steps.outline.output }}
```

### 8. Optimize Model Selection

- **Llama 3.1 8B**: Outlines, summaries, simple transformations
- **Llama 3.1 70B**: Analytical tasks, moderate complexity
- **Claude Sonnet**: Creative writing, complex reasoning

### 9. Handle Missing Data Gracefully

```jinja2
{% if author.biography %}
Style: {{ author.biography | writing_style }}
{% else %}
Style: General
{% endif %}
```

### 10. Use Meaningful Step IDs

```yaml
# Good
- id: story_outline
- id: full_story
- id: summary

# Avoid
- id: step1
- id: step2
```

## Complete Example

```yaml
template:
  id: comprehensive-example-v1
  name: "Comprehensive Example"
  description: "Demonstrates all features"
  category: example

  schema_requirements:
    - topic
    - difficulty
    - characters

  steps:
    - id: analysis
      model: meta.llama3-1-8b-instruct-v1:0
      prompt: |
        {# Comment: Analyze the topic first #}

        {% macro difficulty_note(level) %}
        {% if level == "easy" %}Beginner-friendly{% else %}Advanced{% endif %}
        {% endmacro %}

        Analyze: {{ topic }}
        Difficulty: {{ difficulty_note(difficulty) }}

        Characters:
        {% for char in characters %}
        - {{ char.name }}: {{ char.role }}
        {% endfor %}

        {# Include style guidelines #}
        {% include 'style-instructions' %}

    - id: generate
      model: anthropic.claude-3-5-sonnet-20241022-v2:0
      prompt: |
        Based on this analysis:
        {{ steps.analysis.output | truncate_tokens(300) }}

        {% if difficulty == "easy" %}
        Create simple, accessible content.
        {% else %}
        Create sophisticated, nuanced content.
        {% endif %}

        Key points:
        {% for keyword in steps.analysis.output | extract_keywords(3) %}
        - {{ keyword }}
        {% endfor %}
```

## Next Steps

- [Custom Filters Reference](./custom-filters-reference.md) - All available filters
- [Template Examples](./template-examples.md) - Complete working examples
- [Best Practices](./best-practices.md) - Advanced techniques

## Support

Questions? Check:
- Sample templates: `backend/sample_templates/`
- Example templates: `backend/example_templates/`
- API documentation: `docs/api/`
