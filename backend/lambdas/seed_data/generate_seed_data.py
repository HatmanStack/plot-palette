"""
Plot Palette - Generate Seed Data Lambda Handler

POST /seed-data/generate endpoint that generates seed data records
from a template's schema requirements using Bedrock LLM.
"""

import json
import os
import re
import sys
from datetime import UTC, datetime
from typing import Any

# Add shared library to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../shared"))

from botocore.exceptions import ClientError
from lambda_responses import error_response, success_response
from utils import (
    calculate_bedrock_cost,
    estimate_tokens,
    extract_request_id,
    resolve_model_id,
    sanitize_error_message,
    set_correlation_id,
    setup_logger,
    validate_seed_data,
)

# Initialize logger
logger = setup_logger(__name__)

# Initialize AWS clients
from aws_clients import get_bedrock_client, get_dynamodb_resource, get_s3_client

dynamodb = get_dynamodb_resource()
bedrock_client = get_bedrock_client()
s3_client = get_s3_client()

templates_table = dynamodb.Table(os.environ.get("TEMPLATES_TABLE_NAME", "plot-palette-Templates"))

MAX_SEED_COUNT = 100


def build_prompt(
    schema_requirements: list[str],
    count: int,
    example_data: dict[str, Any] | None = None,
    instructions: str | None = None,
) -> str:
    """Build a prompt for seed data generation."""
    # Build field descriptions from schema requirements
    field_lines = []
    for field in schema_requirements:
        field_lines.append(f"  - {field} (string)")

    fields_section = "\n".join(field_lines)

    prompt = f"""Generate exactly {count} unique JSON objects. Each object must have the following structure:

Required fields:
{fields_section}
"""

    if example_data:
        prompt += f"""
Example record for reference:
{json.dumps(example_data, indent=2)}
"""

    if instructions:
        prompt += f"""
Additional instructions: {instructions}
"""

    prompt += """
Output ONLY a JSON array with no other text. Each record must contain all required fields with non-empty string values.
"""

    return prompt


def invoke_bedrock(model_id: str, prompt: str) -> str:
    """Invoke Bedrock model and return text response."""
    if "claude" in model_id.lower():
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
            "temperature": 0.7,
        }
    elif "llama" in model_id.lower():
        request_body = {
            "prompt": prompt,
            "max_gen_len": 4096,
            "temperature": 0.7,
            "top_p": 0.9,
        }
    elif "mistral" in model_id.lower():
        request_body = {"prompt": prompt, "max_tokens": 4096, "temperature": 0.7}
    else:
        request_body = {"prompt": prompt, "max_tokens": 4096}

    response = bedrock_client.invoke_model(
        modelId=model_id,
        body=json.dumps(request_body),
    )

    response_body = json.loads(response["body"].read())

    if "claude" in model_id.lower():
        content = response_body.get("content")
        if isinstance(content, list) and len(content) > 0:
            return next(
                (c.get("text", "") for c in content if isinstance(c, dict)),
                "",
            )
        return response_body.get("completion", "")
    elif "llama" in model_id.lower():
        return response_body.get("generation", "")
    elif "mistral" in model_id.lower():
        outputs = response_body.get("outputs")
        if isinstance(outputs, list) and len(outputs) > 0:
            return next(
                (o.get("text", "") for o in outputs if isinstance(o, dict)),
                "",
            )
        return ""
    else:
        return response_body.get("text", response_body.get("completion", ""))


def extract_json_array(text: str) -> list[dict[str, Any]]:
    """Extract JSON array from LLM output, handling markdown wrappers."""
    # Strip markdown code blocks
    cleaned = re.sub(r"```(?:json)?\s*", "", text).strip()
    cleaned = re.sub(r"```\s*$", "", cleaned).strip()

    # Try parsing full text
    try:
        result = json.loads(cleaned)
        if isinstance(result, list):
            return result
        return []
    except json.JSONDecodeError:
        pass

    # Try extracting content between [ and ]
    match = re.search(r"\[.*\]", cleaned, re.DOTALL)
    if match:
        try:
            result = json.loads(match.group())
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

    raise ValueError("Could not parse JSON array from LLM output")


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler for POST /seed-data/generate endpoint."""
    try:
        set_correlation_id(extract_request_id(event))

        user_id = event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]
        logger.info(json.dumps({"event": "generate_seed_data_request", "user_id": user_id}))

        try:
            body = json.loads(event["body"])
        except json.JSONDecodeError:
            return error_response(400, "Invalid JSON in request body")

        # Validate request
        template_id = body.get("template_id")
        if not template_id:
            return error_response(400, "Missing required field: template_id")

        count = body.get("count", 10)
        if not isinstance(count, int) or count < 1 or count > MAX_SEED_COUNT:
            return error_response(400, f"count must be between 1 and {MAX_SEED_COUNT}")

        model_tier = body.get("model_tier", "tier-1")
        example_data = body.get("example_data")
        instructions = body.get("instructions")

        # Fetch template to get schema requirements
        try:
            # Get latest version
            from boto3.dynamodb.conditions import Key

            template_response = templates_table.query(
                KeyConditionExpression=Key("template_id").eq(template_id),
                ScanIndexForward=False,
                Limit=1,
            )
            items = template_response.get("Items", [])
            if not items:
                # Fallback: try get_item with version 1
                template_response = templates_table.get_item(
                    Key={"template_id": template_id, "version": 1}
                )
                if "Item" not in template_response:
                    return error_response(404, "Template not found")
                template = template_response["Item"]
            else:
                template = items[0]
        except ClientError as e:
            logger.error(json.dumps({"event": "template_lookup_error", "error": str(e)}))
            return error_response(500, "Error looking up template")

        schema_requirements = template.get("schema_requirements", [])
        if not schema_requirements:
            return error_response(
                400,
                "Template has no schema_requirements. Cannot generate seed data.",
            )

        # Resolve model ID
        model_id = resolve_model_id(model_tier)

        # Build prompt
        prompt = build_prompt(schema_requirements, count, example_data, instructions)

        # Invoke Bedrock
        try:
            llm_output = invoke_bedrock(model_id, prompt)
        except Exception as e:
            logger.error(json.dumps({"event": "bedrock_invoke_error", "error": str(e)}))
            return error_response(500, "Failed to generate seed data from LLM")

        # Parse LLM output
        try:
            records = extract_json_array(llm_output)
        except ValueError:
            logger.error(
                json.dumps({"event": "json_parse_error", "output_preview": llm_output[:500]})
            )
            return error_response(
                500,
                "Failed to parse JSON from LLM output. The model did not return valid JSON.",
            )

        # Validate records against schema
        valid_records = []
        invalid_count = 0
        for record in records:
            if not isinstance(record, dict):
                invalid_count += 1
                continue
            is_valid, _ = validate_seed_data(record, schema_requirements)
            if is_valid:
                valid_records.append(record)
            else:
                invalid_count += 1

        if not valid_records:
            return error_response(
                500,
                f"All {len(records)} generated records were invalid against the schema.",
            )

        # Upload to S3 as JSONL
        timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        s3_key = f"seed-data/{user_id}/generated-{timestamp}.jsonl"
        bucket = os.environ.get("BUCKET_NAME", "")

        jsonl_content = "\n".join(json.dumps(r) for r in valid_records)

        try:
            s3_client.put_object(
                Bucket=bucket,
                Key=s3_key,
                Body=jsonl_content.encode("utf-8"),
                ContentType="application/jsonl",
            )
        except ClientError as e:
            logger.error(json.dumps({"event": "s3_upload_error", "error": str(e)}))
            return error_response(500, "Failed to upload generated seed data")

        # Estimate cost from prompt + output tokens
        try:
            input_tokens = estimate_tokens(prompt, model_id)
            output_tokens = estimate_tokens(llm_output, model_id)
            input_cost = calculate_bedrock_cost(input_tokens, model_id, is_input=True)
            output_cost = calculate_bedrock_cost(output_tokens, model_id, is_input=False)
            total_cost = round(input_cost + output_cost, 6)
        except (ValueError, KeyError):
            total_cost = 0.0

        logger.info(
            json.dumps(
                {
                    "event": "seed_data_generated",
                    "user_id": user_id,
                    "records_generated": len(valid_records),
                    "records_invalid": invalid_count,
                    "s3_key": s3_key,
                    "estimated_cost": total_cost,
                }
            )
        )

        return success_response(
            200,
            {
                "s3_key": s3_key,
                "records_generated": len(valid_records),
                "records_invalid": invalid_count,
                "total_cost": total_cost,
            },
        )

    except KeyError as e:
        logger.error(json.dumps({"event": "missing_field_error", "error": str(e)}))
        return error_response(400, f"Missing required field: {sanitize_error_message(str(e))}")

    except Exception as e:
        logger.error(json.dumps({"event": "unexpected_error", "error": str(e)}), exc_info=True)
        return error_response(500, "Internal server error")
