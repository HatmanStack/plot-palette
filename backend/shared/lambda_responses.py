"""
Plot Palette - Shared Lambda Response Helpers

Common response builders for API Gateway Lambda handlers.
Eliminates duplicated error_response/success_response across 15 handlers.
"""

import json
import logging
import os
from typing import Any

_allowed_origin = os.environ.get("ALLOWED_ORIGIN")
if not _allowed_origin:
    logging.getLogger(__name__).warning("ALLOWED_ORIGIN not set, defaulting to 'null'")
    _allowed_origin = "null"

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": _allowed_origin,
}


def error_response(status_code: int, message: str) -> dict[str, Any]:
    """
    Generate standardized error response.

    Args:
        status_code: HTTP status code
        message: Error message

    Returns:
        Dict: API Gateway response object
    """
    return {
        "statusCode": status_code,
        "headers": CORS_HEADERS.copy(),
        "body": json.dumps({"error": message}),
    }


def success_response(status_code: int, body: Any, **json_kwargs: Any) -> dict[str, Any]:
    """
    Generate standardized success response.

    Args:
        status_code: HTTP status code
        body: Response body (will be JSON-serialized)
        **json_kwargs: Additional kwargs passed to json.dumps (e.g., default=str)

    Returns:
        Dict: API Gateway response object
    """
    return {
        "statusCode": status_code,
        "headers": CORS_HEADERS.copy(),
        "body": json.dumps(body, **json_kwargs),
    }
