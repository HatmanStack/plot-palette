"""
Plot Palette - Template Engine for Multi-Step Generation

This module handles Jinja2-based template rendering and execution
for multi-step synthetic data generation workflows.
"""

import json
import logging
import os
import re
import sys
from typing import TYPE_CHECKING, Any, Dict, Optional, Set

import jinja2

# Add shared library to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../shared"))

from retry import CircuitBreakerOpen, get_circuit_breaker, retry_with_backoff
from template_filters import CUSTOM_FILTERS

if TYPE_CHECKING:
    from mypy_boto3_bedrock_runtime import BedrockRuntimeClient

logger = logging.getLogger(__name__)


class TemplateEngine:
    """Template engine for rendering and executing multi-step templates."""

    def __init__(self, dynamodb_client=None):
        """
        Initialize template engine with optional DynamoDB client.

        Args:
            dynamodb_client: Optional boto3 DynamoDB resource for template loading
        """
        self.dynamodb = dynamodb_client
        self.templates_table = None

        if self.dynamodb:
            try:
                import boto3

                if not dynamodb_client:
                    self.dynamodb = boto3.resource("dynamodb")
                table_name = os.environ.get("TEMPLATES_TABLE_NAME", "plot-palette-Templates")
                self.templates_table = self.dynamodb.Table(table_name)
                logger.info(f"DynamoDB template loader configured with table: {table_name}")
            except Exception as e:
                logger.warning(f"Failed to initialize DynamoDB template loader: {str(e)}")

        # Create Jinja2 environment with custom loader (no autoescape — prompts are plain text, not HTML)
        self.env = jinja2.Environment(  # nosec B701 — LLM prompts are plain text, not HTML
            loader=jinja2.FunctionLoader(self.load_template_string),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Register custom filters
        self.env.filters.update(CUSTOM_FILTERS)

        logger.info(
            "TemplateEngine initialized with custom filters and template composition support"
        )

    def load_template_string(self, template_name: str) -> Optional[str]:
        """
        Load template string from DynamoDB for Jinja2 includes.

        This method is called by Jinja2 when it encounters {% include 'template-name' %}

        Args:
            template_name: Template ID to load

        Returns:
            str: Template prompt content or None if not found
        """
        if not self.templates_table:
            logger.error("DynamoDB template loader not configured")
            return f"<!-- Template loader not configured: {template_name} -->"

        try:
            response = self.templates_table.get_item(
                Key={"template_id": template_name, "version": 1}
            )

            if "Item" not in response:
                logger.warning(f"Template not found for include: {template_name}")
                return f"<!-- Template not found: {template_name} -->"

            template_item = response["Item"]
            steps = template_item.get("template_definition", {}).get("steps", [])

            if not steps:
                logger.warning(f"Template {template_name} has no steps")
                return ""

            # For includes, concatenate all step prompts
            # This allows reusable fragments to be composed
            prompt_parts = []
            for step in steps:
                prompt = step.get("prompt", "")
                if prompt:
                    prompt_parts.append(prompt)

            result = "\n\n".join(prompt_parts)
            logger.info(f"Loaded template for include: {template_name}")
            return result

        except Exception as e:
            logger.error(f"Error loading template {template_name}: {str(e)}", exc_info=True)
            # Sanitize error to prevent information leakage in rendered output
            return f"<!-- Error loading template {template_name} -->"

    @staticmethod
    def _find_referenced_steps(prompt_text: str) -> Set[str]:
        """Parse steps.X.output references from prompt text."""
        return set(re.findall(r"steps\.(\w+)\.output", prompt_text))

    def render_step(self, step_def: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Render a single template step with context."""
        template = self.env.from_string(step_def["prompt"])
        return template.render(**context)

    def execute_template(
        self,
        template_def: Dict[str, Any],
        seed_data: Dict[str, Any],
        bedrock_client: "BedrockRuntimeClient",
    ) -> Dict[str, Any]:
        """Execute multi-step template with Bedrock calls."""
        context = seed_data.copy()
        results = {}

        steps = template_def.get("steps", [])
        if not steps:
            logger.warning("Template has no steps")
            return results

        for step in steps:
            step_id = step["id"]
            model_id = step.get("model", step.get("model_tier", "tier-1"))

            # Resolve model tier alias if needed
            if model_id.startswith("tier-") or model_id in ["cheap", "balanced", "premium"]:
                from constants import MODEL_TIERS

                model_id = MODEL_TIERS.get(model_id, model_id)

            try:
                # Build a render context with pruned steps (don't mutate original)
                render_context = dict(context)
                if "steps" in context and context["steps"]:
                    referenced = self._find_referenced_steps(step.get("prompt", ""))
                    render_context["steps"] = {
                        k: v for k, v in context["steps"].items() if k in referenced
                    }

                # Render prompt with pruned context
                prompt = self.render_step(step, render_context)

                # Call Bedrock
                logger.info(f"Calling Bedrock for step '{step_id}' with model '{model_id}'")
                response = self.call_bedrock(bedrock_client, model_id, prompt)

                # Store step result
                results[step_id] = {"prompt": prompt, "output": response, "model": model_id}

                # Add to context for next steps
                if "steps" not in context:
                    context["steps"] = {}
                if step_id not in context["steps"]:
                    context["steps"][step_id] = {}
                context["steps"][step_id]["output"] = response

                logger.info(f"Step '{step_id}' completed successfully")

            except CircuitBreakerOpen as e:
                logger.error(f"Circuit breaker open for step '{step_id}': {str(e)}")
                # Circuit breaker open - fail fast, don't continue
                results[step_id] = {
                    "error": "Service temporarily unavailable (circuit breaker open)",
                    "model": model_id,
                }
                # Don't continue with remaining steps if circuit is open
                break

            except Exception as e:
                logger.error(f"Error executing step '{step_id}': {str(e)}", exc_info=True)
                # Store error but continue with other steps
                results[step_id] = {"error": str(e), "model": model_id}

        return results

    def call_bedrock(self, client, model_id: str, prompt: str) -> str:
        """
        Call AWS Bedrock API with model-specific formatting.

        Uses retry with exponential backoff and per-model circuit breaker
        to handle transient failures and throttling.
        """
        cb_name = f"bedrock:{model_id}"
        cb = get_circuit_breaker(cb_name)
        if not cb.can_execute():
            raise CircuitBreakerOpen(f"Circuit breaker '{cb_name}' is open")

        try:
            result = self._invoke_bedrock(client, model_id, prompt)
            cb.record_success()
            return result
        except Exception:
            cb.record_failure()
            raise

    @retry_with_backoff(
        max_retries=3,
        base_delay=1.0,
        max_delay=30.0,
    )
    def _invoke_bedrock(self, client, model_id: str, prompt: str) -> str:
        """Invoke Bedrock model with retry logic (no circuit breaker)."""
        try:
            # Format request based on model family
            if "claude" in model_id.lower():
                # Claude models use Messages API format with content array
                request_body = {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 2000,
                    "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
                    "temperature": 0.7,
                    "top_k": 250,
                    "top_p": 0.999,
                }
            elif "llama" in model_id.lower():
                # Llama models use generation format
                request_body = {
                    "prompt": prompt,
                    "max_gen_len": 2000,
                    "temperature": 0.7,
                    "top_p": 0.9,
                }
            elif "mistral" in model_id.lower():
                # Mistral models
                request_body = {"prompt": prompt, "max_tokens": 2000, "temperature": 0.7}
            else:
                # Generic format
                request_body = {"prompt": prompt, "max_tokens": 2000}

            # Invoke model
            response = client.invoke_model(modelId=model_id, body=json.dumps(request_body))

            # Parse response
            response_body = json.loads(response["body"].read())

            # Extract text based on model family
            if "claude" in model_id.lower():
                # Claude returns content array
                return response_body["content"][0]["text"]
            elif "llama" in model_id.lower():
                return response_body.get("generation", "")
            elif "mistral" in model_id.lower():
                return response_body.get("outputs", [{}])[0].get("text", "")
            else:
                return response_body.get("text", response_body.get("completion", ""))

        except Exception as e:
            logger.error(f"Bedrock API error for model {model_id}: {str(e)}", exc_info=True)
            raise
