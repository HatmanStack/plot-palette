"""
Plot Palette - Template Engine for Multi-Step Generation

This module handles Jinja2-based template rendering and execution
for multi-step synthetic data generation workflows.
"""

import jinja2
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class TemplateEngine:
    """Template engine for rendering and executing multi-step templates."""

    def __init__(self):
        self.env = jinja2.Environment(
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True
        )
        logger.info("TemplateEngine initialized")

    def render_step(self, step_def: Dict, context: Dict[str, Any]) -> str:
        """Render a single template step with context."""
        template = self.env.from_string(step_def['prompt'])
        return template.render(**context)

    def execute_template(self, template_def: Dict, seed_data: Dict, bedrock_client) -> Dict:
        """Execute multi-step template with Bedrock calls."""
        context = seed_data.copy()
        results = {}

        steps = template_def.get('steps', [])
        if not steps:
            logger.warning("Template has no steps")
            return results

        for step in steps:
            step_id = step['id']
            model_id = step.get('model', step.get('model_tier', 'tier-1'))

            # Resolve model tier alias if needed
            if model_id.startswith('tier-') or model_id in ['cheap', 'balanced', 'premium']:
                from backend.shared.constants import MODEL_TIERS
                model_id = MODEL_TIERS.get(model_id, model_id)

            try:
                # Render prompt with current context
                prompt = self.render_step(step, context)

                # Call Bedrock
                logger.info(f"Calling Bedrock for step '{step_id}' with model '{model_id}'")
                response = self.call_bedrock(bedrock_client, model_id, prompt)

                # Store step result
                results[step_id] = {
                    'prompt': prompt,
                    'output': response,
                    'model': model_id
                }

                # Add to context for next steps
                if 'steps' not in context:
                    context['steps'] = {}
                if step_id not in context['steps']:
                    context['steps'][step_id] = {}
                context['steps'][step_id]['output'] = response

                logger.info(f"Step '{step_id}' completed successfully")

            except Exception as e:
                logger.error(f"Error executing step '{step_id}': {str(e)}", exc_info=True)
                # Store error but continue with other steps
                results[step_id] = {
                    'error': str(e),
                    'model': model_id
                }

        return results

    def call_bedrock(self, client, model_id: str, prompt: str) -> str:
        """Call AWS Bedrock API with model-specific formatting."""
        try:
            # Format request based on model family
            if 'claude' in model_id.lower():
                # Claude models use Messages API format
                request_body = {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 2000,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "temperature": 0.7
                }
            elif 'llama' in model_id.lower():
                # Llama models use generation format
                request_body = {
                    "prompt": prompt,
                    "max_gen_len": 2000,
                    "temperature": 0.7,
                    "top_p": 0.9
                }
            elif 'mistral' in model_id.lower():
                # Mistral models
                request_body = {
                    "prompt": prompt,
                    "max_tokens": 2000,
                    "temperature": 0.7
                }
            else:
                # Generic format
                request_body = {
                    "prompt": prompt,
                    "max_tokens": 2000
                }

            # Invoke model
            response = client.invoke_model(
                modelId=model_id,
                body=json.dumps(request_body)
            )

            # Parse response
            response_body = json.loads(response['body'].read())

            # Extract text based on model family
            if 'claude' in model_id.lower():
                # Claude returns content array
                return response_body['content'][0]['text']
            elif 'llama' in model_id.lower():
                return response_body.get('generation', '')
            elif 'mistral' in model_id.lower():
                return response_body.get('outputs', [{}])[0].get('text', '')
            else:
                return response_body.get('text', response_body.get('completion', ''))

        except Exception as e:
            logger.error(f"Bedrock API error for model {model_id}: {str(e)}", exc_info=True)
            raise
