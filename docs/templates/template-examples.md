# Template Examples

Working examples demonstrating template features and patterns.

## Quick Links

- **Sample Templates:** Production-ready templates in `backend/sample_templates/`
- **Example Templates:** Feature demonstrations in `backend/example_templates/`
- **Syntax Guide:** [template-syntax-guide.md](./template-syntax-guide.md)
- **Filters Reference:** [custom-filters-reference.md](./custom-filters-reference.md)

## Sample Templates (Production-Ready)

### 1. Creative Writing Story Generator

**Location:** `backend/sample_templates/creative_writing.yaml`

**Features:**
- Multi-step workflow (outline → story → summary)
- Smart model routing (8B → Sonnet → 8B)
- Custom filters (`writing_style`, `truncate_tokens`)

**Example Usage:**
```json
{
  "theme": "a mysterious letter from the past",
  "author": {
    "name": "Virginia Woolf",
    "style_description": "stream of consciousness, introspective, lyrical prose"
  },
  "word_count": 800
}
```

**Output:**
- **outline**: 3-5 plot points for the story
- **story**: Complete 800-word story matching author's style
- **summary**: 2-3 sentence summary

---

### 2. Question & Answer Generator

**Location:** `backend/sample_templates/question_answer.yaml`

**Features:**
- 4-step workflow (question → answer → follow-up → answer)
- Difficulty-based adaptation
- Token truncation for efficiency

**Example Usage:**
```json
{
  "source_text": "Long educational article about machine learning...",
  "difficulty_level": "medium"
}
```

**Output:**
- **question**: Medium-difficulty question about the text
- **answer**: Comprehensive answer with examples
- **follow_up**: Related follow-up question
- **follow_up_answer**: Answer to follow-up

**Cost Optimization:**
- Uses Llama 8B for questions (~10x cheaper)
- Claude Sonnet for detailed answers (quality)
- Llama 70B for follow-up answers (balanced)

---

### 3. Brainstorming Session

**Location:** `backend/sample_templates/brainstorm.yaml`

**Features:**
- Single-step, focused generation
- Structured output format
- Context-aware suggestions

**Example Usage:**
```json
{
  "topic": "sustainable packaging for e-commerce",
  "context": "Small business, 500 packages/month, cost-conscious, environmentally focused"
}
```

**Output:** 10 creative ideas, each with:
- Catchy title
- 2-3 sentence description
- Key benefit

---

### 4. Poetry Generator

**Location:** `backend/sample_templates/poem.yaml`

**Features:**
- Conditional logic for different forms
- Support for: haiku, sonnet, free verse, limerick
- Form-specific instructions

**Example Usage:**
```json
{
  "theme": "autumn in the mountains",
  "poem_style": "contemplative",
  "poem_form": "haiku"
}
```

**Output:** Poem following specified form and style

**Supported Forms:**
- **haiku**: 5-7-5 syllable structure
- **sonnet**: 14 lines, iambic pentameter, rhyme scheme
- **free verse**: Natural rhythm, vivid imagery
- **limerick**: AABBA rhyme, humorous
- **other**: General poetic form

---

### 5. Dialogue Generator

**Location:** `backend/sample_templates/dialogue.yaml`

**Features:**
- Multi-character support
- Personality-driven speech patterns
- Natural conversation flow

**Example Usage:**
```json
{
  "character1": {
    "name": "Dr. Elena Martinez",
    "personality": "Analytical, cautious, formal speech"
  },
  "character2": {
    "name": "Jake Chen",
    "personality": "Enthusiastic, optimistic, casual language"
  },
  "scenario": "Debating whether to pursue risky research"
}
```

**Output:** 8-12 exchanges showing distinct personalities and dynamics

---

## Example Templates (Feature Demonstrations)

### 6. Conditional Story

**Location:** `backend/example_templates/conditional_story.yaml`

**Demonstrates:** `if/elif/else` conditional logic

```yaml
{% if author.genre == "poetry" %}
  Write lyrical prose...
{% elif author.genre == "science fiction" %}
  Write sci-fi story...
{% else %}
  Write general story...
{% endif %}
```

---

### 7. Multi-Character Dialogue

**Location:** `backend/example_templates/multi_character_dialogue.yaml`

**Demonstrates:** `for` loops over character arrays

```yaml
{% for character in characters %}
- **{{ character.name }}**: {{ character.description }}
{% endfor %}
```

---

### 8. Adaptive Questions

**Location:** `backend/example_templates/adaptive_questions.yaml`

**Demonstrates:** Nested conditionals + filters

```yaml
{{ source_text | truncate_tokens(500) }}

{% if difficulty == "easy" %}
  Simple questions...
{% elif difficulty == "medium" %}
  Analytical questions...
{% else %}
  Complex questions...
{% endif %}

{% for keyword in source_text | extract_keywords(3) %}
- {{ keyword }}
{% endfor %}
```

---

### 9. Style Instructions Fragment

**Location:** `backend/example_templates/style_instructions_fragment.yaml`

**Demonstrates:** Reusable template fragments

```yaml
steps:
  - id: style
    model: none  # Fragment only
    prompt: |
      Write in {{ tone }} tone
      Target audience: {{ audience }}
```

---

### 10. Story with Style Include

**Location:** `backend/example_templates/story_with_style_include.yaml`

**Demonstrates:** Template composition with `{% include %}`

```yaml
prompt: |
  Write story about {{ topic }}

  {% include 'style-instructions' %}

  Length: {{ word_count }} words
```

---

### 11. Template with Macros

**Location:** `backend/example_templates/template_with_macros.yaml`

**Demonstrates:** Jinja2 macros for reusable components

```yaml
{% macro difficulty_instruction(level) %}
{% if level == "easy" %}
  Use simple vocabulary...
{% elif level == "medium" %}
  Use moderate complexity...
{% else %}
  Use advanced concepts...
{% endif %}
{% endmacro %}

{{ difficulty_instruction(difficulty) }}
```

---

## Common Patterns

### Pattern: Cheap → Expensive Pipeline

```yaml
steps:
  - id: outline
    model: meta.llama3-1-8b-instruct-v1:0  # Cheap
    prompt: Create outline...

  - id: expand
    model: anthropic.claude-3-5-sonnet-20241022-v2:0  # Expensive
    prompt: |
      Expand outline: {{ steps.outline.output }}
```

**Why:** Generate structure cheaply, use premium model for final output

---

### Pattern: Filter Chain

```yaml
{# Clean markdown, extract keywords, format as JSON #}
{{ user_input | remove_markdown | extract_keywords(5) | json_safe }}
```

---

### Pattern: Conditional with Default

```yaml
{% if custom_instructions %}
  {{ custom_instructions }}
{% else %}
  Use standard format with clear structure.
{% endif %}
```

---

### Pattern: Loop with Conditional

```yaml
{% for item in items %}
{% if item.priority == "high" %}
  **URGENT**: {{ item.description }}
{% else %}
  {{ item.description }}
{% endif %}
{% endfor %}
```

---

## Testing Examples

### Mock Mode Test

```bash
curl -X POST $API/templates/creative-writing-v1/test \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "sample_data": {
      "theme": "lost treasure",
      "author": {
        "name": "Test",
        "style_description": "dramatic"
      },
      "word_count": 500
    },
    "mock": true
  }'
```

**Response:**
```json
{
  "template_id": "creative-writing-v1",
  "mock": true,
  "result": {
    "outline": {
      "prompt": "Create a brief story outline...",
      "output": "[MOCK OUTPUT for step 'outline']",
      "mocked": true
    },
    ...
  }
}
```

---

### Real Bedrock Test

```bash
curl -X POST $API/templates/brainstorm-v1/test \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "sample_data": {
      "topic": "AI in education",
      "context": "K-12 schools, limited budget"
    },
    "mock": false
  }'
```

**Note:** Real mode incurs Bedrock costs

---

## Export/Import Examples

### Export Template

```bash
# Export as YAML
curl -H "Authorization: Bearer $TOKEN" \
  $API/templates/creative-writing-v1/export \
  -o my-template.yaml

# View exported file
cat my-template.yaml
```

---

### Import Template

```bash
# Prepare YAML
cat << 'EOF' > custom-template.yaml
template:
  id: my-custom-template
  name: "My Custom Template"
  steps:
    - id: generate
      model: meta.llama3-1-8b-instruct-v1:0
      prompt: "Generate {{ content_type }} about {{ topic }}"
EOF

# Import via API
curl -X POST $API/templates/import \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"yaml_content\": $(cat custom-template.yaml | jq -Rs .)}"
```

---

## Creating Your Own Templates

### Step 1: Start with a Sample

Copy an existing template:
```bash
cp backend/sample_templates/brainstorm.yaml my-template.yaml
```

### Step 2: Modify for Your Needs

Edit the YAML:
```yaml
template:
  id: my-template-v1
  name: "My Custom Template"
  description: "What it does"

  schema_requirements:
    - input_field
    - another_field

  steps:
    - id: step1
      model: meta.llama3-1-8b-instruct-v1:0
      prompt: |
        Your prompt here with {{ input_field }}
```

### Step 3: Test

```bash
# Upload template
curl -X POST $API/templates \
  -H "Authorization: Bearer $TOKEN" \
  -d @my-template.yaml

# Test with mock data
curl -X POST $API/templates/{template_id}/test \
  -d '{"sample_data": {...}, "mock": true}'
```

### Step 4: Iterate

Based on test results:
1. Refine prompts
2. Adjust model selection
3. Add filters for token efficiency
4. Test with real data (small batch)
5. Scale up

---

## Resources

- **Syntax Guide:** [template-syntax-guide.md](./template-syntax-guide.md)
- **Filters Reference:** [custom-filters-reference.md](./custom-filters-reference.md)
- **Best Practices:** [best-practices.md](./best-practices.md)
- **Sample Templates README:** `backend/sample_templates/README.md`
- **Example Templates README:** `backend/example_templates/README.md`

---

## Getting Help

**Template Issues:**
1. Check syntax: `POST /templates` will validate
2. Test with mock: `POST /templates/{id}/test` with `"mock": true`
3. Review examples: `backend/example_templates/`
4. Check documentation: `docs/templates/`

**Common Issues:**
- Missing required fields → Check `schema_requirements`
- Syntax errors → Validate Jinja2 syntax
- High costs → Use `truncate_tokens`, cheaper models for outlines
- Poor quality → Test different models, refine prompts

**Questions?**
- API docs: `docs/api/`
- GitHub issues: Project repository
- Sample code: `backend/sample_templates/`
