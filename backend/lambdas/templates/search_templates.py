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

from boto3.dynamodb.conditions import Attr  # noqa: E402
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

        user_id = event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]

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
            return error_response(400, f"Invalid sort: {sanitize_error_message(sort_by)}. Must be one of: popular, recent, name")

        logger.info(
            json.dumps({
                "event": "search_templates_request",
                "user_id": user_id,
                "query": query,
                "sort": sort_by,
                "limit": limit,
            })
        )

        # Scan for public templates (DynamoDB FilterExpression)
        all_public: list[dict[str, Any]] = []
        scan_last_key = None
        max_scan_items = 1000  # Safety cap on scan

        while len(all_public) < max_scan_items:
            # TODO: Replace scan with GSI query (is_public + created_at index)
            scan_kwargs: dict[str, Any] = {
                "FilterExpression": Attr("is_public").eq(True),
                "Limit": 100,
            }
            if scan_last_key:
                scan_kwargs["ExclusiveStartKey"] = scan_last_key

            try:
                response = templates_table.scan(**scan_kwargs)
            except ClientError as e:
                logger.error(json.dumps({"event": "scan_error", "error": str(e)}))
                return error_response(500, "Error searching templates")

            all_public.extend(response.get("Items", []))
            scan_last_key = response.get("LastEvaluatedKey")
            if not scan_last_key:
                break

        # Group by template_id, keep latest version only
        template_dict: dict[str, dict[str, Any]] = {}
        for template in all_public:
            tid = template["template_id"]
            version = template.get("version", 1)
            if tid not in template_dict or version > template_dict[tid].get("version", 0):
                template_dict[tid] = template

        results = list(template_dict.values())

        # Apply text search filter
        if query:
            query_lower = query.lower()
            results = [
                t for t in results
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
                start_idx = last_key_data.get("offset", 0)
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
            formatted.append({
                "template_id": template["template_id"],
                "name": template.get("name", ""),
                "description": template.get("description", ""),
                "user_id": template.get("user_id", ""),
                "version": template.get("version", 1),
                "schema_requirements": template.get("schema_requirements", []),
                "step_count": len(template.get("template_definition", {}).get("steps", [])),
                "created_at": template.get("created_at", ""),
            })

        logger.info(
            json.dumps({
                "event": "search_templates_success",
                "total_public": len(template_dict),
                "filtered": len(results),
                "returned": len(formatted),
            })
        )

        response_body: dict[str, Any] = {
            "templates": formatted,
            "count": len(formatted),
            "total": len(results),
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
