# Sample Template Library

Production-ready templates for common LLM synthetic data generation use cases.

## Templates

### 1. Creative Writing (`creative_writing.yaml`)

**Purpose:** Generate creative short stories with structured approach

**Features:**
- Multi-step workflow (outline → story → summary)
- Smart model routing (cheap for outline/summary, premium for story)
- Custom filters (`writing_style`, `truncate_tokens`)
- Style adaptation based on author biography

**Example Seed Data:**
```json
{
  "theme": "a lost letter rediscovered after decades",
  "author": {
    "name": "Virginia Woolf",
    "style_description": "Known for stream of consciousness and lyrical introspective prose"
  },
  "word_count": 800
}
```

**Expected Output:**
- `outline`: 3-5 plot points
- `story`: Complete ~800 word story
- `summary`: 2-3 sentence summary

---

### 2. Question & Answer (`question_answer.yaml`)

**Purpose:** Generate educational Q&A pairs from source material

**Features:**
- 4-step workflow (question → answer → follow-up → follow-up answer)
- Difficulty-based question generation
- Follow-up questions for deeper learning
- Source material truncation for token efficiency

**Example Seed Data:**
```json
{
  "source_text": "Long article or textbook passage here...",
  "difficulty_level": "medium"
}
```

**Expected Output:**
- `question`: Difficulty-appropriate question
- `answer`: Comprehensive answer with examples
- `follow_up`: Related follow-up question
- `follow_up_answer`: Answer to follow-up

**Use Cases:**
- Educational content creation
- Study guide generation
- Training data for tutoring systems

---

### 3. Brainstorming (`brainstorm.yaml`)

**Purpose:** Generate creative ideas and solutions

**Features:**
- 10 diverse ideas per run
- Context-aware suggestions
- Structured format (title + description + benefit)
- Balance of creativity and feasibility

**Example Seed Data:**
```json
{
  "topic": "sustainable packaging alternatives for e-commerce",
  "context": "Small business shipping 500 packages/month, looking to reduce environmental impact while keeping costs reasonable"
}
```

**Expected Output:**
- 10 creative ideas with:
  - Catchy title
  - 2-3 sentence description
  - Key benefit

---

### 4. Poetry (`poem.yaml`)

**Purpose:** Generate poems in various forms and styles

**Features:**
- Conditional logic based on poem form
- Support for: haiku, sonnet, free verse, limerick, and more
- Form-specific instructions (syllable counts, rhyme schemes, meter)
- Emphasis on imagery and emotional resonance

**Example Seed Data:**
```json
{
  "theme": "autumn in the mountains",
  "poem_style": "contemplative",
  "poem_form": "haiku"
}
```

**Supported Forms:**
- `haiku`: 5-7-5 syllable structure
- `sonnet`: 14 lines, iambic pentameter, rhyme scheme
- `free verse`: Natural rhythm, vivid imagery
- `limerick`: AABBA, humorous, 5 lines
- `other`: General poetic form

---

### 5. Dialogue (`dialogue.yaml`)

**Purpose:** Create realistic conversations between characters

**Features:**
- Multi-character support (extensible via loops)
- Personality-driven dialogue
- Natural speech patterns
- Subtext and character dynamics

**Example Seed Data:**
```json
{
  "character1": {
    "name": "Dr. Elena Martinez",
    "personality": "Analytical, cautious, speaks precisely and formally"
  },
  "character2": {
    "name": "Jake Chen",
    "personality": "Enthusiastic, optimistic, uses casual language and humor"
  },
  "scenario": "They're debating whether to pursue a risky but potentially groundbreaking research direction"
}
```

**Expected Output:**
- 8-12 exchanges showing:
  - Distinct voices
  - Character dynamics
  - Natural flow
  - Scenario advancement

---

## Loading Templates

### Via Script

```bash
# Make script executable
chmod +x infrastructure/scripts/load-sample-templates.sh

# Run script
./infrastructure/scripts/load-sample-templates.sh \
  https://your-api-endpoint.com \
  your-auth-token
```

### Manually via API

```bash
# Example: Load creative writing template
curl -X POST https://your-api.com/templates \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Creative Writing - Story Generator",
    "description": "Generate creative short stories...",
    "category": "creative_writing",
    "is_public": true,
    "template_definition": {
      "steps": [...]
    }
  }'
```

## Using Templates

### 1. List Available Templates

```bash
curl https://your-api.com/templates?public=true \
  -H "Authorization: Bearer $TOKEN"
```

### 2. Test Template with Sample Data

```bash
curl -X POST https://your-api.com/templates/{template_id}/test \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "sample_data": {
      "theme": "space exploration",
      "author": {"name": "Test", "style_description": "dramatic"},
      "word_count": 500
    },
    "mock": true
  }'
```

### 3. Create Generation Job

```bash
curl -X POST https://your-api.com/jobs \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "template_id": "creative-writing-v1",
    "seed_data_path": "s3://bucket/seed-data.json",
    "budget_limit": 10.0,
    "num_records": 100
  }'
```

## Customization

All templates can be:
- **Cloned and modified** for specific needs
- **Combined** using template includes
- **Extended** with additional steps
- **Adapted** by changing model selections

## Model Selection

Templates use smart model routing:

- **Llama 3.1 8B** (`meta.llama3-1-8b-instruct-v1:0`): Simple tasks, outlines, summaries
- **Llama 3.1 70B** (`meta.llama3-1-70b-instruct-v1:0`): Moderate complexity, analytical tasks
- **Claude 3.5 Sonnet** (`anthropic.claude-3-5-sonnet-20241022-v2:0`): Complex generation, creative writing

This routing optimizes for cost while maintaining quality.

## Best Practices

1. **Test First**: Use mock mode to verify template behavior before creating jobs
2. **Start Small**: Generate 10-20 samples first to validate quality
3. **Monitor Costs**: Set appropriate budget limits
4. **Iterate**: Refine templates based on output quality
5. **Document**: Add clear descriptions and example seed data

## Support

- Template syntax guide: `docs/templates/template-syntax-guide.md`
- Custom filters reference: `docs/templates/custom-filters-reference.md`
- Full documentation: `docs/templates/`

---

**Note:** These templates are marked `is_public: true` and will be available to all users in your Plot Palette instance.
