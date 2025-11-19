# Template Best Practices

Advanced techniques and patterns for creating effective prompt templates.

## Table of Contents

- [Prompt Engineering](#prompt-engineering)
- [Model Selection](#model-selection)
- [Cost Optimization](#cost-optimization)
- [Token Management](#token-management)
- [Multi-Step Workflows](#multi-step-workflows)
- [Error Handling](#error-handling)
- [Testing](#testing)
- [Performance](#performance)
- [Maintenance](#maintenance)

## Prompt Engineering

### 1. Be Specific and Explicit

**Bad:**
```jinja2
Write something about {{ topic }}.
```

**Good:**
```jinja2
Write a 500-word analytical essay about {{ topic }}.

Include:
1. Clear thesis statement
2. Three supporting arguments
3. Conclusion with implications

Use formal academic tone.
```

### 2. Provide Examples (Few-Shot Learning)

```jinja2
Generate a product description for {{ product }}.

Examples of good descriptions:
- Product A: "Innovative design meets functionality..."
- Product B: "Transform your workspace with..."

Now generate for {{ product }}:
```

### 3. Use Structured Output Requests

```jinja2
Generate questions in this format:

Q1: [Question text]
A1: [Answer text]
Difficulty: [easy/medium/hard]

Q2: [Question text]
...
```

### 4. Leverage Context Window Effectively

```jinja2
{# Put most important context first #}
**Primary Source:**
{{ main_document | truncate_tokens(1000) }}

**Supporting Context:**
{{ additional_info | truncate_tokens(200) }}

**Task:**
Analyze the primary source...
```

## Model Selection

### Smart Model Routing

Different models excel at different tasks:

#### Llama 3.1 8B (`meta.llama3-1-8b-instruct-v1:0`)

**Best For:**
- Outlines and summaries
- Simple transformations
- Classification tasks
- Keyword extraction
- Quick brainstorming

**Cost:** ~$0.30 per 1M input tokens

**Example:**
```yaml
- id: outline
  model: meta.llama3-1-8b-instruct-v1:0
  prompt: Create a 5-point outline for {{ topic }}
```

#### Llama 3.1 70B (`meta.llama3-1-70b-instruct-v1:0`)

**Best For:**
- Analytical tasks
- Moderate complexity writing
- Question generation
- Multi-step reasoning
- Balanced cost/quality

**Cost:** ~$2.65 per 1M input tokens

**Example:**
```yaml
- id: analysis
  model: meta.llama3-1-70b-instruct-v1:0
  prompt: Analyze the themes in {{ text }}
```

#### Claude 3.5 Sonnet (`anthropic.claude-3-5-sonnet-20241022-v2:0`)

**Best For:**
- Creative writing
- Complex reasoning
- Nuanced understanding
- High-quality final outputs
- Long-form content

**Cost:** ~$3.00 per 1M input tokens

**Example:**
```yaml
- id: story
  model: anthropic.claude-3-5-sonnet-20241022-v2:0
  prompt: Write a compelling story about {{ theme }}
```

### Cost vs Quality Trade-offs

**Strategy 1: Cheap → Expensive Pipeline**
```yaml
steps:
  - id: brainstorm
    model: meta.llama3-1-8b-instruct-v1:0  # $0.30/M
    prompt: Generate 10 story ideas about {{ theme }}

  - id: select_best
    model: meta.llama3-1-70b-instruct-v1:0  # $2.65/M
    prompt: Evaluate these ideas and select the best one

  - id: write_story
    model: anthropic.claude-3-5-sonnet-20241022-v2:0  # $3.00/M
    prompt: Develop this idea into a full story
```

**Strategy 2: Parallel Generation + Selection**
```yaml
steps:
  - id: version_a
    model: meta.llama3-1-70b-instruct-v1:0
    prompt: Write story version A

  - id: version_b
    model: meta.llama3-1-70b-instruct-v1:0
    prompt: Write story version B

  - id: refine
    model: anthropic.claude-3-5-sonnet-20241022-v2:0
    prompt: |
      Combine the best elements from:
      Version A: {{ steps.version_a.output }}
      Version B: {{ steps.version_b.output }}
```

## Cost Optimization

### 1. Truncate Long Context

```jinja2
{# Instead of full text #}
{{ long_document }}

{# Use truncation #}
{{ long_document | truncate_tokens(500) }}
```

**Savings:** Up to 90% on input tokens for long documents

### 2. Summarize Before Processing

```jinja2
{# Instead of passing full biography #}
Author background: {{ biography }}

{# Use summary #}
Author background: {{ biography | summarize_text(3) }}
```

### 3. Extract Only Relevant Information

```jinja2
{# Instead of full article #}
Source: {{ article }}

{# Use keywords and summary #}
Key topics: {{ article | extract_keywords(5) | json_safe }}
Summary: {{ article | summarize_text(2) }}
```

### 4. Reuse Outlines and Summaries

```yaml
steps:
  - id: outline
    model: meta.llama3-1-8b-instruct-v1:0  # Cheap
    prompt: Create outline for {{ theme }}

  - id: section1
    model: anthropic.claude-3-5-sonnet-20241022-v2:0
    prompt: |
      Outline: {{ steps.outline.output }}
      Write section 1

  - id: section2
    model: anthropic.claude-3-5-sonnet-20241022-v2:0
    prompt: |
      Outline: {{ steps.outline.output }}  {# Reuse! #}
      Write section 2
```

### 5. Use Conditionals to Skip Unnecessary Steps

```jinja2
{% if needs_outline %}
  Create detailed outline first...
{% else %}
  Write directly from {{ prompt }}
{% endif %}
```

## Token Management

### Understand Token Costs

**Approximate ratios:**
- 1 token ≈ 4 characters (English)
- 100 tokens ≈ 75 words
- 1000 tokens ≈ 750 words

### Monitor Token Usage

Use `truncate_tokens` filter to control input size:

```jinja2
{# Guarantee < 500 tokens #}
{{ source | truncate_tokens(500) }}

{# For longer context #}
{{ document | truncate_tokens(2000) }}
```

### Optimize Prompt Length

**Bad:** (Wasteful)
```jinja2
This is a prompt that asks you to generate content.
I want you to write something creative and interesting
about the following topic. Make sure it's well-written
and engaging. Here's the topic: {{ topic }}
```

**Good:** (Concise)
```jinja2
Write creative, engaging content about {{ topic }}.
```

## Multi-Step Workflows

### Pattern 1: Outline → Expand → Refine

```yaml
steps:
  - id: outline
    model: meta.llama3-1-8b-instruct-v1:0
    prompt: Create 5-point outline for {{ topic }}

  - id: expand
    model: anthropic.claude-3-5-sonnet-20241022-v2:0
    prompt: |
      Expand this outline into full content:
      {{ steps.outline.output }}

  - id: refine
    model: anthropic.claude-3-5-sonnet-20241022-v2:0
    prompt: |
      Refine this content for clarity and style:
      {{ steps.expand.output }}
```

### Pattern 2: Generate → Critique → Improve

```yaml
steps:
  - id: draft
    model: meta.llama3-1-70b-instruct-v1:0
    prompt: Write first draft about {{ topic }}

  - id: critique
    model: anthropic.claude-3-5-sonnet-20241022-v2:0
    prompt: |
      Critique this draft:
      {{ steps.draft.output | truncate_tokens(800) }}

      List 3-5 specific improvements.

  - id: revised
    model: anthropic.claude-3-5-sonnet-20241022-v2:0
    prompt: |
      Original: {{ steps.draft.output | truncate_tokens(600) }}
      Critique: {{ steps.critique.output }}

      Write improved version addressing the critique.
```

### Pattern 3: Parallel → Merge

```yaml
steps:
  - id: technical
    model: meta.llama3-1-70b-instruct-v1:0
    prompt: Write technical explanation of {{ concept }}

  - id: simple
    model: meta.llama3-1-8b-instruct-v1:0
    prompt: Write simple explanation of {{ concept }}

  - id: merged
    model: anthropic.claude-3-5-sonnet-20241022-v2:0
    prompt: |
      Combine these explanations into balanced content:

      Technical: {{ steps.technical.output | truncate_tokens(300) }}
      Simple: {{ steps.simple.output | truncate_tokens(300) }}
```

## Error Handling

### Handle Missing Data

```jinja2
{% if author.biography %}
  Style: {{ author.biography | writing_style }}
{% else %}
  Style: General
{% endif %}

{% if source_text %}
  Context: {{ source_text | truncate_tokens(500) }}
{% else %}
  Generate from scratch about {{ topic }}
{% endif %}
```

### Provide Fallback Values

```jinja2
Word count: {{ word_count | default(500) }}
Tone: {{ tone | default("neutral") }}
Audience: {{ audience | default("general public") }}
```

### Validate in Schema Requirements

```yaml
schema_requirements:
  - topic          # Required
  - difficulty     # Required
  - word_count     # Required
  # Optional fields don't need to be listed
```

## Testing

### Test Before Deploying

Always test templates with sample data:

```bash
curl -X POST $API/templates/{id}/test \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "sample_data": {
      "topic": "test",
      "difficulty": "medium"
    },
    "mock": true
  }'
```

### Test Edge Cases

```json
{
  "empty_string": "",
  "very_long_text": "...10000 words...",
  "special_characters": "Test with émojis 🎉 and symbols",
  "missing_optional": null
}
```

### Iterate on Real Data

1. Start with mock mode (free)
2. Test with 1-2 real Bedrock calls
3. Generate 10-20 samples
4. Review quality
5. Refine template
6. Scale up

## Performance

### Minimize Step Count

**Bad:** (Too many steps)
```yaml
steps:
  - id: step1
    prompt: Extract keywords
  - id: step2
    prompt: Expand keywords
  - id: step3
    prompt: Format expanded keywords
  - id: step4
    prompt: Add context to formatted keywords
```

**Good:** (Combined)
```yaml
steps:
  - id: process
    prompt: |
      Extract and expand keywords from {{ text }}
      Format as bullet points with context.
```

### Cache Common Fragments

Use `{% include %}` for repeated instructions:

```yaml
# Fragment: style-guide
steps:
  - prompt: |
      Use professional tone.
      Target business audience.
      Keep under 500 words.
```

```yaml
# Main template
steps:
  - prompt: |
      Write about {{ topic }}
      {% include 'style-guide' %}
```

### Batch Similar Requests

Instead of:
```yaml
# Separate jobs for each item
```

Use:
```yaml
# One job with loop in template
{% for item in items %}
Generate content for {{ item }}
---
{% endfor %}
```

## Maintenance

### Version Your Templates

```yaml
id: creative-writing-v1  # Not creative-writing
id: creative-writing-v2  # New version
```

### Document Changes

```yaml
description: |
  v2 Changes:
  - Added style adaptation
  - Improved outline structure
  - Better cost optimization
```

### Keep Templates Focused

One template = One clear purpose

**Bad:** Mega-template doing everything
**Good:** Specialized templates, composable

### Regular Review

- Monitor output quality
- Check token usage
- Update model selections as new models release
- Refine prompts based on results

## Common Patterns

### Pattern: Adaptive Difficulty

```jinja2
{% if difficulty == "easy" %}
  Use simple language appropriate for beginners.
  Explain all technical terms.
  Provide concrete examples.
{% elif difficulty == "medium" %}
  Use moderate complexity.
  Assume basic familiarity.
  Balance theory and practice.
{% else %}
  Use advanced concepts.
  Assume expert audience.
  Focus on nuance and edge cases.
{% endif %}
```

### Pattern: Dynamic Length

```jinja2
Write a {{ word_count }}-word {{ content_type }} about {{ topic }}.

Structure:
{% if word_count < 300 %}
- Brief introduction
- Main point
- Quick conclusion
{% elif word_count < 1000 %}
- Introduction with context
- 2-3 main points
- Supporting evidence
- Thoughtful conclusion
{% else %}
- Detailed introduction
- 5-7 main sections
- Deep analysis
- Comprehensive conclusion
{% endif %}
```

### Pattern: Style Inheritance

```jinja2
{% if author.biography %}
  {% set style = author.biography | writing_style %}
  Write in {{ style }} style, matching {{ author.name }}'s approach.
{% else %}
  Write in {{ default_style | default("neutral") }} style.
{% endif %}
```

## Resources

- [Template Syntax Guide](./template-syntax-guide.md)
- [Custom Filters Reference](./custom-filters-reference.md)
- [Template Examples](./template-examples.md)
- Sample Templates: `backend/sample_templates/`
- Example Templates: `backend/example_templates/`

## Questions?

- Test templates: `POST /templates/{id}/test`
- View samples: `backend/sample_templates/README.md`
- Check costs: Monitor job cost tracking in dashboard
