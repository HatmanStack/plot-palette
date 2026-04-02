"""
Plot Palette - Template Marketplace Search Lambda Handler

GET /templates/marketplace endpoint that searches and paginates
public templates for the marketplace browsing experience.
"""

import base64
import json
import os
import sys
from typing import Any

# Add shared library to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../shared"))

from boto3.dynamodb.conditions import Key  # noqa: E402
from botocore.exceptions import ClientError  # noqa: E402
from lambda_responses import error_response, success_response  # noqa: E402
from utils import (  # noqa: E402
    extract_request_id,
    sanitize_error_message,
    set_correlation_id,
    setup_logger,
)

# Initialize logger
logger = setup_logger(__name__)

# Initialize AWS clients
from aws_clients import get_dynamodb_resource  # noqa: E402

dynamodb = get_dynamodb_resource()
templates_table = dynamodb.Table(os.environ.get("TEMPLATES_TABLE_NAME", "plot-palette-Templates"))

MAX_LIMIT = 50
DEFAULT_LIMIT = 20


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Lambda handler for GET /templates/marketplace endpoint.

    Searches public templates with optional text query, sorting, and pagination.

    Query parameters:
        q: search string (optional, matches name and description)
        sort: popular, recent, name (default recent)
        limit: 1-50 (default 20)
        last_key: pagination token (base64 JSON)
    """
    try:
        set_correlation_id(extract_request_id(event))

        params = event.get("queryStringParameters") or {}
        query = params.get("q", "").strip()
        sort_by = params.get("sort", "recent")
        limit_str = params.get("limit", str(DEFAULT_LIMIT))
        last_key_b64 = params.get("last_key")

        # Validate limit
        try:
            limit = min(max(int(limit_str), 1), MAX_LIMIT)
        except (ValueError, TypeError):
            limit = DEFAULT_LIMIT

        if sort_by not in ("popular", "recent", "name"):
            return error_response(
                400,
                f"Invalid sort: {sanitize_error_message(sort_by)}. Must be one of: popular, recent, name",
            )

        logger.info(
            json.dumps(
                {
                    "event": "search_templates_request",
                    "query": query,
                    "sort": sort_by,
                    "limit": limit,
                }
            )
        )

        # Query public templates using GSI (is_public + created_at index)
        all_public: list[dict[str, Any]] = []
        query_last_key = None
        max_query_items = 1000  # Safety cap
        truncated = False

        while len(all_public) < max_query_items:
            query_kwargs: dict[str, Any] = {
                "IndexName": "is_public-created_at-index",
                "KeyConditionExpression": Key("is_public").eq("true"),
                "ScanIndexForward": False,  # Newest first
                "Limit": 100,
            }
            if query_last_key:
                query_kwargs["ExclusiveStartKey"] = query_last_key

            try:
                response = templates_table.query(**query_kwargs)
            except ClientError as e:
                logger.error(json.dumps({"event": "query_error", "error": str(e)}))
                return error_response(500, "Error searching templates")

            all_public.extend(response.get("Items", []))
            query_last_key = response.get("LastEvaluatedKey")
            if not query_last_key:
                break

        # Detect silent truncation
        if len(all_public) >= max_query_items and query_last_key:
            truncated = True
            logger.warning(
                json.dumps({"event": "search_results_truncated", "cap": max_query_items})
            )

        # Group by template_id, keep latest version only
        template_dict: dict[str, dict[str, Any]] = {}
        for template in all_public:
            tid = template.get("template_id")
            if not tid:
                continue
            version = template.get("version", 1)
            if tid not in template_dict or version > template_dict[tid].get("version", 0):
                template_dict[tid] = template

        results = list(template_dict.values())

        # Apply text search filter
        if query:
            query_lower = query.lower()
            results = [
                t
                for t in results
                if query_lower in t.get("name", "").lower()
                or query_lower in t.get("description", "").lower()
            ]

        # Sort results
        if sort_by == "name":
            results.sort(key=lambda t: t.get("name", "").lower())
        else:
            # "recent" and "popular" (MVP: popular == recent)
            # TODO: Add fork_count field for true popularity sorting
            results.sort(key=lambda t: t.get("created_at", ""), reverse=True)

        # Apply pagination
        start_idx = 0
        if last_key_b64:
            try:
                last_key_data = json.loads(base64.b64decode(last_key_b64))
                start_idx = max(0, int(last_key_data.get("offset", 0)))
            except (json.JSONDecodeError, ValueError, KeyError):
                pass

        paginated = results[start_idx : start_idx + limit]

        # Build next page token
        next_last_key = None
        if start_idx + limit < len(results):
            next_last_key = base64.b64encode(
                json.dumps({"offset": start_idx + limit}).encode()
            ).decode()

        # Format response: strip template_definition for security
        formatted = []
        for template in paginated:
            formatted.append(
                {
                    "template_id": template["template_id"],
                    "name": template.get("name", ""),
                    "description": template.get("description", ""),
                    "user_id": template.get("user_id", ""),
                    "version": template.get("version", 1),
                    "schema_requirements": template.get("schema_requirements", []),
                    "step_count": len(template.get("template_definition", {}).get("steps", [])),
                    "created_at": template.get("created_at", ""),
                }
            )

        logger.info(
            json.dumps(
                {
                    "event": "search_templates_success",
                    "total_public": len(template_dict),
                    "filtered": len(results),
                    "returned": len(formatted),
                }
            )
        )

        response_body: dict[str, Any] = {
            "templates": formatted,
            "count": len(formatted),
            "total": len(results),
            "truncated": truncated,
        }
        if next_last_key:
            response_body["last_key"] = next_last_key

        return success_response(200, response_body, default=str)

    except KeyError as e:
        logger.error(json.dumps({"event": "missing_field_error", "error": str(e)}))
        return error_response(400, f"Missing required field: {sanitize_error_message(str(e))}")

    except Exception as e:
        logger.error(json.dumps({"event": "unexpected_error", "error": str(e)}), exc_info=True)
        return error_response(500, "Internal server error")
