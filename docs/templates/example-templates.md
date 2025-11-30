# Example Templates

This directory contains example templates demonstrating advanced Jinja2 features in Plot Palette.

## Templates

### 1. Conditional Story Generator (`conditional_story.yaml`)

**Features Demonstrated:**
- `if/elif/else` conditional logic
- Genre-based prompt adaptation
- Variable interpolation

**Usage:**
```json
{
  "author": {
    "genre": "poetry"
  },
  "theme": "autumn leaves",
  "max_words": 500
}
```

### 2. Multi-Character Dialogue (`multi_character_dialogue.yaml`)

**Features Demonstrated:**
- `for` loops over arrays
- Nested object access in loops
- Dynamic list rendering

**Usage:**
```json
{
  "characters": [
    {
      "name": "Alice",
      "description": "A curious scientist",
      "personality": "analytical and questioning"
    },
    {
      "name": "Bob",
      "description": "A creative artist",
      "personality": "imaginative and emotional"
    }
  ],
  "topic": "the nature of creativity",
  "num_exchanges": 8
}
```

### 3. Adaptive Questions (`adaptive_questions.yaml`)

**Features Demonstrated:**
- Nested conditionals
- Custom filters (`truncate_tokens`, `extract_keywords`)
- Filter chaining
- Multiple conditional branches

**Usage:**
```json
{
  "source_text": "Long article text here...",
  "difficulty": "medium",
  "include_answers": true
}
```

## Testing Examples

You can test these templates using the template testing API:

```bash
# Create the template
curl -X POST $API_ENDPOINT/templates \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d @backend/example_templates/conditional_story.yaml

# Test with sample data
curl -X POST $API_ENDPOINT/templates/{template_id}/test \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "sample_data": {
      "author": {"genre": "poetry"},
      "theme": "autumn",
      "max_words": 300
    },
    "mock": true
  }'
```

## Key Jinja2 Features

### Conditionals

```jinja2
{% if condition %}
  ...
{% elif other_condition %}
  ...
{% else %}
  ...
{% endif %}
```

### Loops

```jinja2
{% for item in items %}
  {{ item.property }}
{% endfor %}
```

### Filters

```jinja2
{{ text | custom_filter }}
{{ text | filter1 | filter2(param) }}
```

### Comments

```jinja2
{# This is a comment #}
```

## Available Custom Filters

- `random_sentence` - Extract random sentence from text
- `random_word` - Extract random word(s)
- `writing_style` - Detect writing style from biography
- `truncate_tokens` - Truncate to approximate token count
- `extract_keywords` - Extract top keywords by frequency
- `summarize_text` - Extract first N sentences
- `capitalize_first` - Capitalize first letter of sentences
- `remove_markdown` - Strip markdown formatting
- `json_safe` - Convert to JSON string

See `docs/templates/custom-filters-reference.md` for full documentation.
