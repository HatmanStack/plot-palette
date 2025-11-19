# Custom Filters Reference

Complete reference for all custom Jinja2 filters available in Plot Palette templates.

## Quick Reference

| Filter | Purpose | Example |
|--------|---------|---------|
| `random_sentence` | Extract random sentence | `{{ text \| random_sentence }}` |
| `random_word` | Extract random word(s) | `{{ text \| random_word(3) }}` |
| `writing_style` | Detect writing style | `{{ bio \| writing_style }}` |
| `truncate_tokens` | Truncate to token limit | `{{ text \| truncate_tokens(500) }}` |
| `extract_keywords` | Extract top keywords | `{{ text \| extract_keywords(5) }}` |
| `summarize_text` | Extract first N sentences | `{{ text \| summarize_text(3) }}` |
| `capitalize_first` | Capitalize sentences | `{{ text \| capitalize_first }}` |
| `remove_markdown` | Strip markdown | `{{ md \| remove_markdown }}` |
| `json_safe` | Convert to JSON string | `{{ obj \| json_safe }}` |

---

## Filter Details

### random_sentence

Extract a random sentence from text.

**Signature:** `random_sentence(text: str) -> str`

**Purpose:** Randomly select one sentence for variation in prompts.

**Example:**
```jinja2
{{ biography | random_sentence }}
```

**Input:**
```
"First sentence. Second sentence. Third sentence."
```

**Output:** (random)
```
"Second sentence"
```

**Use Cases:**
- Add variety to prompts
- Sample from long text
- Random context selection

---

### random_word

Extract random word(s) from text.

**Signature:** `random_word(text: str, count: int = 1) -> str`

**Parameters:**
- `count`: Number of words to extract (default: 1)

**Example:**
```jinja2
{{ keywords | random_word }}
{{ keywords | random_word(3) }}
```

**Input:**
```
"apple banana cherry date elderberry"
```

**Output:** (random)
```
"cherry"               # count=1
"banana date apple"    # count=3
```

**Use Cases:**
- Random keyword selection
- Prompt variation
- Sample vocabulary

---

### writing_style

Detect and extract writing style keywords from author biography.

**Signature:** `writing_style(biography: str) -> str`

**Returns:** Comma-separated style keywords or "general"

**Detected Styles:**
- `poetic` - poet, poetry, verse, lyrical
- `narrative` - story, narrative, tale, chronicle
- `descriptive` - describe, vivid, detailed
- `minimalist` - minimal, sparse, concise, brief
- `verbose` - elaborate, detailed, extensive
- `dramatic` - drama, theatrical, intense

**Example:**
```jinja2
{{ author.biography | writing_style }}
```

**Input:**
```
"A renowned poet known for her lyrical verse and dramatic theatrical performances."
```

**Output:**
```
"poetic, dramatic"
```

**Use Cases:**
- Adapt prompts to author style
- Style-aware content generation
- Personalized outputs

---

### truncate_tokens

Truncate text to approximately N tokens.

**Signature:** `truncate_tokens(text: str, max_tokens: int) -> str`

**Parameters:**
- `max_tokens`: Approximate maximum tokens (1 token ≈ 4 characters)

**Returns:** Truncated text with `...` suffix if truncated

**Example:**
```jinja2
{{ long_article | truncate_tokens(500) }}
{{ context | truncate_tokens(100) }}
```

**Input:**
```
Very long text...
```

**Output:**
```
"Truncated text respecting word boundaries..."
```

**Use Cases:**
- Stay within model context limits
- Cost optimization
- Focus on relevant portions

**Note:** This is a rough estimate. Actual tokenization may vary by model.

---

### extract_keywords

Extract top N keywords using frequency analysis.

**Signature:** `extract_keywords(text: str, count: int = 5) -> List[str]`

**Parameters:**
- `count`: Number of keywords to extract (default: 5)

**Returns:** List of most frequent keywords

**Filters Out:**
- Common stop words (the, a, an, and, or, etc.)
- Words shorter than 4 characters

**Example:**
```jinja2
{% for keyword in text | extract_keywords(3) %}
- {{ keyword }}
{% endfor %}
```

**Input:**
```
"Python programming is great. Python is versatile. Programming with Python is fun."
```

**Output:**
```
["python", "programming", "versatile"]
```

**Use Cases:**
- Topic extraction
- Content summarization
- Prompt focus

---

### summarize_text

Extract first N sentences as a summary.

**Signature:** `summarize_text(text: str, max_sentences: int = 3) -> str`

**Parameters:**
- `max_sentences`: Number of sentences to extract (default: 3)

**Example:**
```jinja2
{{ article | summarize_text(2) }}
```

**Input:**
```
"First sentence here. Second sentence here. Third sentence here. Fourth sentence."
```

**Output:**
```
"First sentence here. Second sentence here."
```

**Use Cases:**
- Quick summaries
- Extract opening context
- Reduce token usage

---

### capitalize_first

Capitalize the first letter of each sentence.

**Signature:** `capitalize_first(text: str) -> str`

**Example:**
```jinja2
{{ messy_text | capitalize_first }}
```

**Input:**
```
"first sentence. second sentence. third sentence."
```

**Output:**
```
"First sentence. Second sentence. Third sentence."
```

**Use Cases:**
- Fix formatting
- Standardize capitalization
- Clean up text

---

### remove_markdown

Strip markdown formatting from text.

**Signature:** `remove_markdown(text: str) -> str`

**Removes:**
- Headers (`## Header`)
- Bold (`**text**`)
- Italic (`*text*`)
- Links (`[text](url)`)
- Code blocks (` ```code``` `)
- Inline code (`` `code` ``)

**Example:**
```jinja2
{{ markdown_content | remove_markdown }}
```

**Input:**
```
"## Title\nThis is **bold** and *italic* text with [a link](http://example.com)."
```

**Output:**
```
"Title\nThis is bold and italic text with a link."
```

**Use Cases:**
- Extract plain text
- Clean formatted content
- Prepare for processing

---

### json_safe

Convert object to JSON-formatted string.

**Signature:** `json_safe(obj: Any) -> str`

**Example:**
```jinja2
{{ data_structure | json_safe }}
{{ metadata | json_safe }}
```

**Input:**
```python
{"name": "Alice", "age": 30, "hobbies": ["reading", "coding"]}
```

**Output:**
```json
{"name": "Alice", "age": 30, "hobbies": ["reading", "coding"]}
```

**Use Cases:**
- Embed data in prompts
- Structured data passing
- Debug output

---

## Chaining Filters

Filters can be chained together:

```jinja2
{# Extract keywords, then format as JSON #}
{{ text | extract_keywords(5) | json_safe }}

{# Truncate, then summarize #}
{{ long_text | truncate_tokens(1000) | summarize_text(3) }}

{# Remove markdown, then extract random sentence #}
{{ markdown | remove_markdown | random_sentence }}
```

## Filter Performance

**Fast Filters** (negligible overhead):
- `capitalize_first`
- `json_safe`
- `truncate_tokens`

**Moderate Filters** (regex-based):
- `random_sentence`
- `random_word`
- `summarize_text`
- `remove_markdown`
- `writing_style`

**Slower Filters** (processing-intensive):
- `extract_keywords` (frequency analysis)

**Recommendation:** Use filters liberally, but avoid nested loops with slow filters.

## Custom Filter Examples

### Example 1: Style-Adaptive Prompts

```jinja2
{% if author.biography %}
Write in {{ author.biography | writing_style }} style.
{% else %}
Write in general style.
{% endif %}
```

### Example 2: Context with Keywords

```jinja2
Key topics to cover:
{% for keyword in source_text | extract_keywords(5) %}
- {{ keyword }}
{% endfor %}

Context: {{ source_text | truncate_tokens(300) }}
```

### Example 3: Random Variation

```jinja2
{# Different prompt each time #}
Example: {{ examples | random_sentence }}

{# Multiple random words #}
Keywords: {{ keyword_pool | random_word(3) }}
```

### Example 4: Clean and Summarize

```jinja2
{# Chain filters for clean summary #}
{{ user_input | remove_markdown | summarize_text(2) | capitalize_first }}
```

## Error Handling

All filters handle edge cases gracefully:

```jinja2
{# Empty strings #}
{{ "" | random_sentence }}         {# Returns "" #}
{{ "" | extract_keywords }}        {# Returns [] #}

{# None values #}
{{ none_value | truncate_tokens(100) }}  {# Returns "" #}

{# Invalid data types #}
{{ 123 | writing_style }}          {# Converts to string #}
```

## See Also

- [Template Syntax Guide](./template-syntax-guide.md) - Full Jinja2 syntax
- [Template Examples](./template-examples.md) - Working examples
- [Best Practices](./best-practices.md) - Advanced techniques

## Questions?

- Check example templates: `backend/example_templates/`
- Sample templates: `backend/sample_templates/`
- Source code: `backend/shared/template_filters.py`
