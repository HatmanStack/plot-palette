# Phase 5: Prompt Template Engine

## Phase Goal

Enhance the basic template engine from Phase 4 with advanced features including custom Jinja2 filters for LLM operations, conditional logic, loops, template composition, validation, and a sample template library. By the end of this phase, users can create sophisticated multi-step generation workflows with reusable components.

**Success Criteria:**
- Custom Jinja2 filters implemented (random_sentence, writing_style, truncate_tokens, etc.)
- Support for conditional logic and loops in templates
- Template composition (templates can reference other templates)
- Template validation before saving
- Sample template library (5+ production-ready templates)
- Template testing utility for dry-run execution
- Template import/export functionality
- Documentation for template syntax

**Estimated Tokens:** ~105,000

---

## Prerequisites

- **Phase 4** completed (basic template engine working in worker)
- **Phase 3** completed (template CRUD APIs)
- Understanding of Jinja2 templating
- Knowledge of LLM prompt engineering best practices

---

## Task 1: Custom Jinja2 Filters

### Goal

Implement custom Jinja2 filters tailored for LLM prompt generation including text manipulation, token operations, and data extraction.

### Files to Create

- `backend/shared/template_filters.py` - Custom filter implementations
- `tests/unit/test_template_filters.py` - Filter unit tests

### Prerequisites

- Phase 1 shared library structure
- Understanding of Jinja2 filter API

### Implementation Steps

1. **Create template_filters.py with custom filters:**
   ```python
   import random
   import re
   from typing import List, Any

   def random_sentence(text: str) -> str:
       """Extract a random sentence from text"""
       sentences = re.split(r'[.!?]+', text)
       sentences = [s.strip() for s in sentences if s.strip()]
       return random.choice(sentences) if sentences else text

   def random_word(text: str, count: int = 1) -> str:
       """Extract random word(s) from text"""
       words = text.split()
       if count == 1:
           return random.choice(words) if words else ""
       else:
           return ' '.join(random.sample(words, min(count, len(words))))

   def writing_style(biography: str) -> str:
       """Extract writing style keywords from author biography"""
       # Simple keyword extraction (can be enhanced with NLP)
       style_keywords = []

       style_patterns = {
           'poetic': r'\b(poet|poetry|verse|lyrical)\b',
           'narrative': r'\b(story|narrative|tale|chronicle)\b',
           'descriptive': r'\b(describe|vivid|detailed)\b',
           'minimalist': r'\b(minimal|sparse|concise|brief)\b',
           'verbose': r'\b(elaborate|detailed|extensive)\b',
           'dramatic': r'\b(drama|theatrical|intense)\b'
       }

       for style, pattern in style_patterns.items():
           if re.search(pattern, biography, re.IGNORECASE):
               style_keywords.append(style)

       return ', '.join(style_keywords) if style_keywords else 'general'

   def truncate_tokens(text: str, max_tokens: int) -> str:
       """Truncate text to approximately N tokens (rough estimate: 1 token ~= 4 chars)"""
       max_chars = max_tokens * 4
       if len(text) <= max_chars:
           return text

       # Truncate at word boundary
       truncated = text[:max_chars]
       last_space = truncated.rfind(' ')
       if last_space > 0:
           truncated = truncated[:last_space]

       return truncated + '...'

   def extract_keywords(text: str, count: int = 5) -> List[str]:
       """Extract top N keywords from text (simple frequency-based)"""
       # Remove common stop words
       stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}

       words = re.findall(r'\b\w+\b', text.lower())
       words = [w for w in words if w not in stop_words and len(w) > 3]

       # Count frequency
       from collections import Counter
       word_freq = Counter(words)

       # Return top N
       return [word for word, _ in word_freq.most_common(count)]

   def summarize_text(text: str, max_sentences: int = 3) -> str:
       """Extract first N sentences as summary"""
       sentences = re.split(r'[.!?]+', text)
       sentences = [s.strip() for s in sentences if s.strip()]
       return '. '.join(sentences[:max_sentences]) + '.'

   def capitalize_first(text: str) -> str:
       """Capitalize first letter of each sentence"""
       return '. '.join(s.capitalize() for s in text.split('. '))

   def remove_markdown(text: str) -> str:
       """Remove markdown formatting"""
       # Remove headers
       text = re.sub(r'#+\s+', '', text)
       # Remove bold
       text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
       # Remove italic
       text = re.sub(r'\*(.*?)\*', r'\1', text)
       # Remove links
       text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', text)
       return text

   def json_safe(obj: Any) -> str:
       """Convert object to JSON-safe string"""
       import json
       return json.dumps(obj, ensure_ascii=False)

   # Register all filters
   CUSTOM_FILTERS = {
       'random_sentence': random_sentence,
       'random_word': random_word,
       'writing_style': writing_style,
       'truncate_tokens': truncate_tokens,
       'extract_keywords': extract_keywords,
       'summarize_text': summarize_text,
       'capitalize_first': capitalize_first,
       'remove_markdown': remove_markdown,
       'json_safe': json_safe
   }
   ```

2. **Update template_engine.py (from Phase 4) to register filters:**
   ```python
   from backend.shared.template_filters import CUSTOM_FILTERS

   class TemplateEngine:
       def __init__(self):
           self.env = jinja2.Environment(
               autoescape=False,
               trim_blocks=True,
               lstrip_blocks=True
           )

           # Register custom filters
           self.env.filters.update(CUSTOM_FILTERS)
   ```

3. **Create unit tests:**
   ```python
   import pytest
   from backend.shared.template_filters import *

   def test_random_sentence():
       text = "First sentence. Second sentence. Third sentence."
       result = random_sentence(text)
       assert result in ["First sentence", "Second sentence", "Third sentence"]

   def test_writing_style():
       bio = "She was a renowned poet known for her lyrical verse"
       style = writing_style(bio)
       assert 'poetic' in style

   def test_truncate_tokens():
       text = "a " * 1000  # 1000 words
       result = truncate_tokens(text, 100)  # ~100 tokens = 400 chars
       assert len(result) < 500

   def test_extract_keywords():
       text = "Python programming is fun. Python is a great programming language."
       keywords = extract_keywords(text, 3)
       assert 'python' in keywords
       assert 'programming' in keywords
   ```

4. **Document filters in template syntax guide (create docs/template-syntax.md):**
   - List all filters with examples
   - Show usage in templates
   - Explain token estimation logic

### Verification Checklist

- [ ] All custom filters implemented
- [ ] Filters registered in TemplateEngine
- [ ] Filters work with Jinja2 syntax (e.g., `{{ text | random_sentence }}`)
- [ ] Unit tests pass for all filters
- [ ] Filters handle edge cases (empty strings, None values)
- [ ] Documentation created

### Testing Instructions

```bash
# Run unit tests
pytest tests/unit/test_template_filters.py -v

# Test in template
python3 -c "
from backend.ecs_tasks.worker.template_engine import TemplateEngine
engine = TemplateEngine()
template_str = '{{ text | random_sentence }}'
result = engine.env.from_string(template_str).render(text='First. Second. Third.')
print(result)
"
```

### Commit Message Template

```
feat(templates): add custom Jinja2 filters for LLM prompt generation

- Implement random_sentence, random_word filters for data sampling
- Add writing_style filter to extract style from biographies
- Add truncate_tokens filter with rough token estimation
- Implement extract_keywords, summarize_text for text manipulation
- Add capitalize_first, remove_markdown utility filters
- Register all filters in TemplateEngine
- Create unit tests for all filters
- Document filter usage in template syntax guide

Author: HatmanStack <82614182+HatmanStack@users.noreply.github.com>
```

**Estimated Tokens:** ~18,000

---

## Task 2: Conditional Logic and Loops

### Goal

Enhance template engine to support Jinja2 conditional statements and loops for dynamic prompt generation.

### Files to Modify

- `backend/ecs_tasks/worker/template_engine.py` - No code changes needed (Jinja2 supports this natively)
- Create example templates demonstrating conditionals and loops

### Prerequisites

- Task 1 completed (custom filters)
- Understanding of Jinja2 control structures

### Implementation Steps

1. **Create example templates with conditionals:**
   ```yaml
   # Template: Conditional Story Generation
   template:
     id: conditional-story
     name: "Conditional Story Generator"
     version: 1

     steps:
       - id: story
         model: claude-sonnet
         prompt: |
           {% if author.genre == "poetry" %}
           Write a lyrical short story in poetic prose about {{ theme }}.
           {% elif author.genre == "science fiction" %}
           Write a science fiction story about {{ theme }} set in the future.
           {% else %}
           Write a story about {{ theme }} in any style you prefer.
           {% endif %}

           Keep it under {{ max_words }} words.
   ```

2. **Create example templates with loops:**
   ```yaml
   # Template: Multi-Character Dialogue
   template:
     id: multi-character-dialogue
     name: "Multi-Character Dialogue Generator"

     steps:
       - id: dialogue
         model: llama-3.1-70b
         prompt: |
           Create a dialogue between the following characters:

           {% for character in characters %}
           - {{ character.name }}: {{ character.description }}
           {% endfor %}

           Topic: {{ topic }}

           Write 5-10 exchanges showing their different perspectives.
   ```

3. **Create template with nested logic:**
   ```yaml
   # Template: Adaptive Question Generation
   template:
     id: adaptive-questions
     name: "Adaptive Question Generator"

     steps:
       - id: questions
         model: llama-3.1-8b
         prompt: |
           Generate questions about the following text:

           {{ source_text | truncate_tokens(500) }}

           {% if difficulty == "easy" %}
           Generate 5 simple comprehension questions suitable for beginners.
           {% elif difficulty == "medium" %}
           Generate 5 analytical questions that require understanding of concepts.
           {% else %}
           Generate 5 complex critical thinking questions that require synthesis.
           {% endif %}

           {% if include_answers %}
           For each question, provide a detailed answer.
           {% endif %}
   ```

4. **Update template validation to check for syntax errors:**
   ```python
   def validate_template_syntax(template_def: dict) -> tuple[bool, str]:
       """Validate Jinja2 syntax in template"""
       try:
           engine = TemplateEngine()

           for step in template_def.get('steps', []):
               prompt = step.get('prompt', '')
               # Try to parse template
               engine.env.from_string(prompt)

           return True, "Valid template syntax"

       except jinja2.TemplateSyntaxError as e:
           return False, f"Template syntax error: {str(e)}"
       except Exception as e:
           return False, f"Template validation error: {str(e)}"
   ```

5. **Add validation to create_template Lambda (Phase 3):**
   ```python
   from backend.shared.template_filters import validate_template_syntax

   # In create_template handler:
   valid, error_message = validate_template_syntax(body['template_definition'])
   if not valid:
       return error_response(400, error_message)
   ```

### Verification Checklist

- [ ] Conditional statements (if/elif/else) work in templates
- [ ] Loops (for) work in templates
- [ ] Nested control structures work
- [ ] Template validation catches syntax errors
- [ ] Example templates provided
- [ ] Documentation updated with control structure examples

### Testing Instructions

```bash
# Test conditional template
python3 -c "
from backend.ecs_tasks.worker.template_engine import TemplateEngine
engine = TemplateEngine()

template_str = '''
{% if genre == \"poetry\" %}
Poetic style
{% else %}
Regular style
{% endif %}
'''

print(engine.env.from_string(template_str).render(genre='poetry'))
"

# Test loop template
python3 -c "
from backend.ecs_tasks.worker.template_engine import TemplateEngine
engine = TemplateEngine()

template_str = '''
{% for item in items %}
- {{ item }}
{% endfor %}
'''

print(engine.env.from_string(template_str).render(items=['A', 'B', 'C']))
"
```

### Commit Message Template

```
feat(templates): add support for conditionals and loops

- Enable Jinja2 if/elif/else conditionals in templates
- Enable for loops for dynamic prompt generation
- Create example templates demonstrating control structures
- Add template syntax validation to catch errors early
- Update create_template Lambda with validation
- Document conditional and loop syntax
- Add nested logic examples

Author: HatmanStack <82614182+HatmanStack@users.noreply.github.com>
```

**Estimated Tokens:** ~15,000

---

## Task 3: Template Composition and Reusability

### Goal

Allow templates to reference and include other templates, enabling modular prompt design and reusability.

### Files to Modify

- `backend/ecs_tasks/worker/template_engine.py` - Add template loading and composition

### Prerequisites

- Tasks 1-2 completed
- Understanding of Jinja2 include/import

### Implementation Steps

1. **Add template loader to TemplateEngine:**
   ```python
   import boto3

   class TemplateEngine:
       def __init__(self, dynamodb_client=None):
           self.dynamodb = dynamodb_client or boto3.resource('dynamodb')
           self.templates_table = self.dynamodb.Table(os.environ.get('TEMPLATES_TABLE_NAME', 'plot-palette-Templates'))

           # Create custom loader
           self.env = jinja2.Environment(
               loader=jinja2.FunctionLoader(self.load_template_string),
               autoescape=False,
               trim_blocks=True,
               lstrip_blocks=True
           )

           # Register custom filters
           self.env.filters.update(CUSTOM_FILTERS)

       def load_template_string(self, template_name: str) -> str:
           """Load template string from DynamoDB for Jinja2 includes"""
           try:
               response = self.templates_table.get_item(
                   Key={'template_id': template_name, 'version': 1}  # Use version 1 by default
               )

               if 'Item' in response:
                   # Return the prompt from first step (for simple includes)
                   # Or concatenate all steps
                   steps = response['Item']['template_definition'].get('steps', [])
                   if steps:
                       return steps[0].get('prompt', '')

               return f"Template {template_name} not found"

           except Exception as e:
               logger.error(f"Error loading template {template_name}: {str(e)}")
               return f"Error loading {template_name}"
   ```

2. **Create reusable template fragments:**
   ```yaml
   # Base template: Writing Style Instructions
   template:
     id: style-instructions
     name: "Writing Style Instructions"

     steps:
       - id: style
         model: none  # Fragment, not a full template
         prompt: |
           Use clear, concise language.
           Avoid jargon unless necessary.
           Write in {{ tone }} tone.
           Target audience: {{ audience }}.
   ```

3. **Create template that includes fragments:**
   ```yaml
   # Template: Story with Style
   template:
     id: story-with-style
     name: "Story Generator with Style Guidelines"

     steps:
       - id: story
         model: claude-sonnet
         prompt: |
           Write a short story about {{ topic }}.

           {% include 'style-instructions' %}

           Length: {{ word_count }} words.
   ```

4. **Add macro support for reusable prompt components:**
   ```yaml
   # Template with macros
   template:
     id: questions-with-macros
     name: "Question Generator with Reusable Macros"

     steps:
       - id: questions
         model: llama-3.1-8b
         prompt: |
           {% macro difficulty_instruction(level) %}
           {% if level == "easy" %}
           Use simple vocabulary and straightforward questions.
           {% elif level == "medium" %}
           Use moderate complexity with some analytical thinking required.
           {% else %}
           Use advanced concepts and require critical analysis.
           {% endif %}
           {% endmacro %}

           Generate questions about: {{ topic }}

           {{ difficulty_instruction(difficulty) }}

           Number of questions: {{ count }}
   ```

5. **Update template validation to check for missing includes:**
   ```python
   def validate_template_includes(template_def: dict, templates_table) -> tuple[bool, str]:
       """Check that all included templates exist"""
       import re

       try:
           missing_includes = []

           for step in template_def.get('steps', []):
               prompt = step.get('prompt', '')

               # Find all {% include 'template-name' %} references
               includes = re.findall(r"{%\s*include\s+'([^']+)'\s*%}", prompt)

               for include_name in includes:
                   # Check if template exists
                   response = templates_table.get_item(
                       Key={'template_id': include_name, 'version': 1}
                   )
                   if 'Item' not in response:
                       missing_includes.append(include_name)

           if missing_includes:
               return False, f"Missing included templates: {', '.join(missing_includes)}"

           return True, "All includes valid"

       except Exception as e:
           return False, f"Include validation error: {str(e)}"
   ```

### Verification Checklist

- [ ] TemplateEngine can load templates from DynamoDB
- [ ] Jinja2 include directive works
- [ ] Macros work for reusable components
- [ ] Validation checks for missing includes
- [ ] Example fragment templates created
- [ ] Example composite templates created
- [ ] Documentation explains composition

### Testing Instructions

```bash
# Create fragment template
curl -X POST $API_ENDPOINT/templates \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "name": "Style Fragment",
    "template_definition": {
      "steps": [{
        "id": "style",
        "prompt": "Use {{ tone }} tone."
      }]
    }
  }'

# Create template that includes fragment
curl -X POST $API_ENDPOINT/templates \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "name": "Story with Style",
    "template_definition": {
      "steps": [{
        "id": "story",
        "model": "claude-sonnet",
        "prompt": "Write a story.\n{% include \"style-fragment\" %}"
      }]
    }
  }'

# Test rendering
python3 -c "
from backend.ecs_tasks.worker.template_engine import TemplateEngine
engine = TemplateEngine()
template = engine.env.get_template('story-with-style')
print(template.render(tone='formal'))
"
```

### Commit Message Template

```
feat(templates): add template composition and reusability

- Implement DynamoDB-backed Jinja2 loader for includes
- Support {% include 'template-name' %} directive
- Enable macros for reusable prompt components
- Add validation for missing included templates
- Create example fragment templates
- Create example composite templates
- Document template composition patterns

Author: HatmanStack <82614182+HatmanStack@users.noreply.github.com>
```

**Estimated Tokens:** ~17,000

---

## Task 4: Sample Template Library

### Goal

Create a library of 5+ production-ready templates covering common use cases (creative writing, Q&A, brainstorming, etc.).

### Files to Create

- `backend/sample_templates/creative_writing.yaml`
- `backend/sample_templates/question_answer.yaml`
- `backend/sample_templates/brainstorm.yaml`
- `backend/sample_templates/poem.yaml`
- `backend/sample_templates/dialogue.yaml`
- `backend/sample_templates/README.md` - Template library documentation
- `infrastructure/scripts/load-sample-templates.sh` - Script to load templates into DynamoDB

### Prerequisites

- Tasks 1-3 completed (all template features)
- Understanding of common LLM use cases

### Implementation Steps

1. **Create creative_writing.yaml:**
   ```yaml
   template:
     id: creative-writing-v1
     name: "Creative Writing - Story Generator"
     description: "Generate creative short stories based on theme, style, and length"
     category: creative_writing
     is_public: true

     schema_requirements:
       - theme
       - author.name
       - author.style_description

     steps:
       - id: outline
         model: llama-3.1-8b
         prompt: |
           Create a brief story outline (3-5 plot points) for a {{ word_count }}-word story.

           Theme: {{ theme }}
           Style: {{ author.style_description | writing_style }}

           Output just the outline as numbered points.

       - id: story
         model: claude-sonnet
         prompt: |
           Write a complete short story based on this outline:

           {{ steps.outline.output }}

           Requirements:
           - Approximately {{ word_count }} words
           - {{ author.style_description | writing_style }} writing style
           - Theme: {{ theme }}
           - Include vivid descriptions and character development

       - id: summary
         model: llama-3.1-8b
         prompt: |
           Summarize this story in 2-3 sentences:

           {{ steps.story.output | truncate_tokens(500) }}
   ```

2. **Create question_answer.yaml:**
   ```yaml
   template:
     id: question-answer-v1
     name: "Question & Answer Generator"
     description: "Generate questions from source material with detailed answers"
     category: question_answer

     schema_requirements:
       - source_text
       - difficulty_level

     steps:
       - id: question
         model: llama-3.1-8b
         prompt: |
           Generate a {{ difficulty_level }} difficulty question based on this text:

           {{ source_text | truncate_tokens(500) }}

           The question should test understanding of key concepts.

       - id: answer
         model: claude-sonnet
         prompt: |
           Answer this question in detail:

           Question: {{ steps.question.output }}

           Source material:
           {{ source_text | truncate_tokens(500) }}

           Provide a comprehensive answer with examples if applicable.

       - id: follow_up
         model: llama-3.1-8b
         prompt: |
           Based on this Q&A, generate a relevant follow-up question:

           Original Question: {{ steps.question.output }}
           Answer: {{ steps.answer.output | truncate_tokens(300) }}

       - id: follow_up_answer
         model: llama-3.1-70b
         prompt: |
           Answer this follow-up question:

           {{ steps.follow_up.output }}

           Context from previous answer:
           {{ steps.answer.output | truncate_tokens(300) }}
   ```

3. **Create brainstorm.yaml:**
   ```yaml
   template:
     id: brainstorm-v1
     name: "Brainstorming Session"
     description: "Generate creative ideas and solutions for a given topic"
     category: brainstorm

     schema_requirements:
       - topic
       - context

     steps:
       - id: ideas
         model: llama-3.1-70b
         prompt: |
           Brainstorm 10 creative ideas related to: {{ topic }}

           Context: {{ context }}

           For each idea, provide:
           1. A catchy title
           2. A brief description (2-3 sentences)

           Focus on originality and practicality.
   ```

4. **Create poem.yaml:**
   ```yaml
   template:
     id: poem-v1
     name: "Poetry Generator"
     description: "Generate poems in various styles and forms"
     category: poem

     schema_requirements:
       - theme
       - poem_style
       - poem_form

     steps:
       - id: poem
         model: claude-sonnet
         prompt: |
           Write a {{ poem_form }} poem about {{ theme }}.

           Style: {{ poem_style }}

           {% if poem_form == "haiku" %}
           Follow the 5-7-5 syllable structure.
           {% elif poem_form == "sonnet" %}
           Write 14 lines with iambic pentameter.
           {% elif poem_form == "free verse" %}
           Use free verse with vivid imagery and metaphors.
           {% endif %}

           Make it evocative and memorable.
   ```

5. **Create dialogue.yaml:**
   ```yaml
   template:
     id: dialogue-v1
     name: "Dialogue Generator"
     description: "Create realistic dialogue between characters"
     category: dialogue

     schema_requirements:
       - character1.name
       - character1.personality
       - character2.name
       - character2.personality
       - scenario

     steps:
       - id: dialogue
         model: claude-sonnet
         prompt: |
           Create a dialogue between two characters in this scenario:

           {{ scenario }}

           Characters:
           1. {{ character1.name }}: {{ character1.personality }}
           2. {{ character2.name }}: {{ character2.personality }}

           Write 8-12 exchanges that reveal their personalities and advance the scenario.
           Use natural, realistic dialogue.
   ```

6. **Create load-sample-templates.sh:**
   ```bash
   #!/bin/bash
   set -e

   API_ENDPOINT=$1
   TOKEN=$2

   if [ -z "$API_ENDPOINT" ] || [ -z "$TOKEN" ]; then
       echo "Usage: ./load-sample-templates.sh <API_ENDPOINT> <TOKEN>"
       exit 1
   fi

   echo "Loading sample templates..."

   for template_file in backend/sample_templates/*.yaml; do
       if [ "$template_file" == "backend/sample_templates/README.md" ]; then
           continue
       fi

       echo "Loading $(basename $template_file)..."

       # Convert YAML to JSON and post to API
       python3 << EOF
   import yaml
   import json
   import requests

   with open('$template_file', 'r') as f:
       template = yaml.safe_load(f)

   response = requests.post(
       '$API_ENDPOINT/templates',
       headers={
           'Authorization': 'Bearer $TOKEN',
           'Content-Type': 'application/json'
       },
       json={
           'name': template['template']['name'],
           'description': template['template']['description'],
           'category': template['template'].get('category', 'general'),
           'is_public': template['template'].get('is_public', True),
           'template_definition': {
               'steps': template['template']['steps']
           }
       }
   )

   if response.status_code == 201:
       print(f"✓ Loaded {template['template']['name']}")
   else:
       print(f"✗ Failed to load {template['template']['name']}: {response.text}")
   EOF

   done

   echo "Sample templates loaded!"
   ```

7. **Create README.md for template library:**
   - Document each template's purpose
   - Show example seed data for each
   - Explain customization options

### Verification Checklist

- [ ] 5+ sample templates created
- [ ] Templates cover different use cases
- [ ] Templates use advanced features (filters, conditionals, composition)
- [ ] Schema requirements documented
- [ ] Load script works
- [ ] Templates marked as public
- [ ] README documents all templates

### Testing Instructions

```bash
# Load sample templates
chmod +x infrastructure/scripts/load-sample-templates.sh
./infrastructure/scripts/load-sample-templates.sh $API_ENDPOINT $TOKEN

# List public templates
curl $API_ENDPOINT/templates?public=true

# Create job with sample template
curl -X POST $API_ENDPOINT/jobs \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "template_id": "creative-writing-v1",
    "seed_data_path": "sample-datasets/themes.json",
    "budget_limit": 5.0,
    "num_records": 10
  }'
```

### Commit Message Template

```
feat(templates): add sample template library

- Create 5 production-ready templates (creative writing, Q&A, brainstorm, poem, dialogue)
- Implement multi-step workflows with smart model routing
- Use custom filters and conditional logic
- Add schema requirements for each template
- Create load script to import templates via API
- Document template library with usage examples
- Mark templates as public for all users

Author: HatmanStack <82614182+HatmanStack@users.noreply.github.com>
```

**Estimated Tokens:** ~20,000

---

(Continuing with remaining tasks...)

## Task 5: Template Testing and Dry-Run

### Goal

Implement a template testing utility that allows users to dry-run templates with sample data before creating jobs.

### Files to Create

- `backend/lambdas/templates/test_template.py` - Template testing Lambda
- `tests/integration/test_template_execution.py` - Integration tests

### Prerequisites

- Tasks 1-4 completed
- Access to Bedrock for actual API calls (or mock for testing)

### Implementation Steps

1. **Create POST /templates/{id}/test endpoint:**
   ```python
   import boto3
   from backend.ecs_tasks.worker.template_engine import TemplateEngine

   bedrock_client = boto3.client('bedrock-runtime')
   template_engine = TemplateEngine()

   def lambda_handler(event, context):
       """Test template with sample data (dry-run)"""
       try:
           user_id = event['requestContext']['authorizer']['jwt']['claims']['sub']
           template_id = event['pathParameters']['template_id']
           body = json.loads(event['body'])

           sample_data = body.get('sample_data', {})
           use_mock = body.get('mock', True)  # Use mock by default to avoid costs

           # Get template
           response = templates_table.get_item(
               Key={'template_id': template_id, 'version': 1}
           )

           if 'Item' not in response:
               return error_response(404, "Template not found")

           template = response['Item']

           # Check ownership or public
           if template['user_id'] != user_id and not template.get('is_public', False):
               return error_response(403, "Access denied")

           # Validate sample data has required fields
           schema_reqs = template.get('schema_requirements', [])
           missing_fields = []
           for field in schema_reqs:
               if not get_nested_field(sample_data, field):
                   missing_fields.append(field)

           if missing_fields:
               return error_response(400, f"Missing required fields: {', '.join(missing_fields)}")

           # Execute template
           if use_mock:
               result = execute_template_mock(template['template_definition'], sample_data)
           else:
               result = template_engine.execute_template(
                   template['template_definition'],
                   sample_data,
                   bedrock_client
               )

           return {
               "statusCode": 200,
               "headers": {"Content-Type": "application/json"},
               "body": json.dumps({
                   "template_id": template_id,
                   "sample_data": sample_data,
                   "result": result,
                   "mock": use_mock
               })
           }

       except Exception as e:
           logger.error(f"Error testing template: {str(e)}", exc_info=True)
           return error_response(500, "Internal server error")

   def execute_template_mock(template_def, seed_data):
       """Execute template with mocked Bedrock responses"""
       engine = TemplateEngine()
       results = {}

       for step in template_def.get('steps', []):
           step_id = step['id']

           # Render prompt
           prompt = engine.render_step(step, seed_data)

           # Mock response
           mock_output = f"[MOCK OUTPUT for step '{step_id}' with model '{step['model']}']"

           results[step_id] = {
               'prompt': prompt,
               'output': mock_output,
               'model': step['model'],
               'mocked': True
           }

           # Add to context for next steps
           seed_data[f'steps.{step_id}.output'] = mock_output

       return results
   ```

2. **Update API Gateway:**
   - Add POST /templates/{id}/test route
   - Attach JWT authorizer

3. **Create integration tests:**
   ```python
   def test_template_dry_run():
       # Create test template
       template_id = create_test_template()

       # Test with sample data
       response = requests.post(
           f"{api_endpoint}/templates/{template_id}/test",
           headers={'Authorization': f'Bearer {token}'},
           json={
               'sample_data': {
                   'theme': 'adventure',
                   'author': {'name': 'Test Author', 'style_description': 'dramatic'}
               },
               'mock': True
           }
       )

       assert response.status_code == 200
       result = response.json()
       assert 'result' in result
       assert len(result['result']) > 0  # Has step outputs
   ```

### Verification Checklist

- [ ] Test endpoint validates sample data against schema
- [ ] Mock mode works without calling Bedrock
- [ ] Real mode calls Bedrock (with cost warning)
- [ ] Returns rendered prompts and outputs
- [ ] Checks template ownership/public status
- [ ] Integration tests pass

### Testing Instructions

```bash
# Test template with mock
curl -X POST $API_ENDPOINT/templates/$TEMPLATE_ID/test \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "sample_data": {"theme": "space exploration"},
    "mock": true
  }'

# Test with real Bedrock call
curl -X POST $API_ENDPOINT/templates/$TEMPLATE_ID/test \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "sample_data": {"theme": "space exploration"},
    "mock": false
  }'
```

### Commit Message Template

```
feat(templates): add template testing and dry-run functionality

- Implement POST /templates/{id}/test endpoint
- Support mock mode for cost-free testing
- Validate sample data against template schema
- Return rendered prompts and outputs
- Add integration tests for template execution
- Enable testing before creating full jobs

Author: HatmanStack <82614182+HatmanStack@users.noreply.github.com>
```

**Estimated Tokens:** ~15,000

---

## Task 6: Template Import/Export

### Goal

Allow users to export templates as YAML files and import templates from files for sharing and backup.

### Files to Create

- `backend/lambdas/templates/export_template.py`
- `backend/lambdas/templates/import_template.py`

### Prerequisites

- Phase 3 template CRUD complete
- Understanding of YAML format

### Implementation Steps

1. **Create GET /templates/{id}/export endpoint:**
   ```python
   import yaml

   def lambda_handler(event, context):
       """Export template as YAML"""
       try:
           user_id = event['requestContext']['authorizer']['jwt']['claims']['sub']
           template_id = event['pathParameters']['template_id']

           # Get template
           response = templates_table.get_item(
               Key={'template_id': template_id, 'version': 1}
           )

           if 'Item' not in response:
               return error_response(404, "Template not found")

           template = response['Item']

           # Check ownership or public
           if template['user_id'] != user_id and not template.get('is_public', False):
               return error_response(403, "Access denied")

           # Convert to YAML format
           export_data = {
               'template': {
                   'id': template_id,
                   'name': template['name'],
                   'description': template.get('description', ''),
                   'category': template.get('category', 'general'),
                   'version': template['version'],
                   'schema_requirements': template.get('schema_requirements', []),
                   'steps': template['template_definition'].get('steps', [])
               }
           }

           yaml_content = yaml.dump(export_data, default_flow_style=False, sort_keys=False)

           return {
               "statusCode": 200,
               "headers": {
                   "Content-Type": "application/x-yaml",
                   "Content-Disposition": f'attachment; filename="{template_id}.yaml"'
               },
               "body": yaml_content
           }

       except Exception as e:
           logger.error(f"Error exporting template: {str(e)}", exc_info=True)
           return error_response(500, "Internal server error")
   ```

2. **Create POST /templates/import endpoint:**
   ```python
   def lambda_handler(event, context):
       """Import template from YAML"""
       try:
           user_id = event['requestContext']['authorizer']['jwt']['claims']['sub']
           body = json.loads(event['body'])

           yaml_content = body.get('yaml_content')
           if not yaml_content:
               return error_response(400, "yaml_content required")

           # Parse YAML
           template_data = yaml.safe_load(yaml_content)

           if 'template' not in template_data:
               return error_response(400, "Invalid template format")

           template = template_data['template']

           # Validate template syntax
           valid, error_msg = validate_template_syntax({'steps': template.get('steps', [])})
           if not valid:
               return error_response(400, error_msg)

           # Create new template (generate new ID)
           template_id = generate_template_id()

           new_template = {
               'template_id': template_id,
               'version': 1,
               'name': template.get('name', 'Imported Template'),
               'description': template.get('description', ''),
               'category': template.get('category', 'general'),
               'user_id': user_id,
               'template_definition': {'steps': template.get('steps', [])},
               'schema_requirements': template.get('schema_requirements', []),
               'created_at': datetime.utcnow().isoformat(),
               'is_public': False  # Imported templates are private by default
           }

           templates_table.put_item(Item=new_template)

           return {
               "statusCode": 201,
               "headers": {"Content-Type": "application/json"},
               "body": json.dumps({
                   "template_id": template_id,
                   "message": "Template imported successfully"
               })
           }

       except yaml.YAMLError as e:
           return error_response(400, f"Invalid YAML: {str(e)}")
       except Exception as e:
           logger.error(f"Error importing template: {str(e)}", exc_info=True)
           return error_response(500, "Internal server error")
   ```

3. **Update API Gateway:**
   - Add GET /templates/{id}/export
   - Add POST /templates/import

### Verification Checklist

- [ ] Export returns valid YAML
- [ ] Export includes all template data
- [ ] Import validates YAML syntax
- [ ] Import validates template syntax
- [ ] Import creates new template with new ID
- [ ] Imported templates are private by default
- [ ] Both endpoints check authorization

### Testing Instructions

```bash
# Export template
curl -H "Authorization: Bearer $TOKEN" \
  $API_ENDPOINT/templates/$TEMPLATE_ID/export \
  -o template.yaml

# View exported YAML
cat template.yaml

# Import template
curl -X POST $API_ENDPOINT/templates/import \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"yaml_content\": $(cat template.yaml | jq -Rs .)}"
```

### Commit Message Template

```
feat(templates): add import/export functionality

- Implement GET /templates/{id}/export to download as YAML
- Implement POST /templates/import to create from YAML
- Validate YAML syntax and template structure
- Generate new template ID on import
- Set imported templates as private by default
- Enable template sharing and backup

Author: HatmanStack <82614182+HatmanStack@users.noreply.github.com>
```

**Estimated Tokens:** ~12,000

---

## Task 7: Template Documentation

### Goal

Create comprehensive documentation for template syntax, features, and best practices.

### Files to Create

- `docs/templates/template-syntax-guide.md`
- `docs/templates/custom-filters-reference.md`
- `docs/templates/template-examples.md`
- `docs/templates/best-practices.md`

### Prerequisites

- All Phase 5 tasks completed

### Implementation Steps

1. **Create template-syntax-guide.md:**
   - Basic template structure
   - Step definitions
   - Model selection
   - Variable interpolation
   - Conditional logic (if/elif/else)
   - Loops (for)
   - Include directive
   - Macros

2. **Create custom-filters-reference.md:**
   - List all custom filters
   - Syntax for each filter
   - Parameters and return types
   - Usage examples
   - Performance considerations

3. **Create template-examples.md:**
   - Simple template (single step)
   - Multi-step template
   - Template with conditionals
   - Template with loops
   - Template with filters
   - Composite template (includes)
   - Template with macros

4. **Create best-practices.md:**
   - Prompt engineering tips
   - When to use which model
   - Token optimization
   - Cost reduction strategies
   - Error handling
   - Testing templates before deployment
   - Versioning strategies

### Verification Checklist

- [ ] All template features documented
- [ ] Examples are correct and tested
- [ ] Documentation is clear and comprehensive
- [ ] Best practices based on real usage
- [ ] Linked from main README

### Commit Message Template

```
docs(templates): add comprehensive template documentation

- Create template syntax guide with all features
- Document all custom filters with examples
- Add template examples covering all use cases
- Write best practices for prompt engineering and cost optimization
- Link documentation from main README

Author: HatmanStack <82614182+HatmanStack@users.noreply.github.com>
```

**Estimated Tokens:** ~8,000

---

## Phase 5 Verification

### Success Criteria

- [ ] All custom filters implemented and tested
- [ ] Conditionals and loops work in templates
- [ ] Template composition via includes works
- [ ] 5+ sample templates in library
- [ ] Template testing endpoint functional
- [ ] Import/export functionality works
- [ ] Comprehensive documentation complete
- [ ] All integration tests pass

### Estimated Total Cost

- Testing templates (mock mode): $0
- Testing templates (real Bedrock calls): ~$0.05 per test
- Sample template library loaded: $0 (one-time operation)

---

## Next Steps

With advanced template features complete, proceed to **Phase 6: React Frontend Application**.

Phase 6 will build the user interface for:
- Job management dashboard
- Template editor with live preview
- Seed data upload interface
- Real-time progress monitoring
- Cost tracking visualization
- Authentication UI (login/signup)

---

**Navigation:**
- [← Back to README](./README.md)
- [← Previous: Phase 4](./Phase-4.md)
- [Next: Phase 6 - React Frontend Application →](./Phase-6.md)
