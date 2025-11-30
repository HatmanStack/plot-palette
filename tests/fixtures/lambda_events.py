"""
Lambda Event Factories

Factory functions for creating realistic AWS Lambda event payloads
for API Gateway HTTP API (v2) and REST API (v1) events.
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def make_api_gateway_event_v2(
    method: str = "GET",
    path: str = "/",
    path_parameters: Optional[Dict[str, str]] = None,
    query_string_parameters: Optional[Dict[str, str]] = None,
    body: Optional[Any] = None,
    headers: Optional[Dict[str, str]] = None,
    jwt_claims: Optional[Dict[str, Any]] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create an API Gateway HTTP API v2 event.

    Args:
        method: HTTP method (GET, POST, PUT, DELETE)
        path: Request path (e.g., "/jobs", "/jobs/{jobId}")
        path_parameters: Path parameters (e.g., {"jobId": "123"})
        query_string_parameters: Query string parameters
        body: Request body (will be JSON encoded if dict)
        headers: Request headers
        jwt_claims: JWT claims for authorization
        user_id: Shorthand for setting jwt_claims["sub"]

    Returns:
        API Gateway HTTP API v2 event dictionary
    """
    # Build JWT claims
    claims = jwt_claims or {}
    if user_id and "sub" not in claims:
        claims["sub"] = user_id

    # Set default user if no claims provided
    if not claims:
        claims = {
            "sub": "test-user-123",
            "email": "test@example.com",
            "email_verified": True,
        }

    # Build headers
    default_headers = {
        "content-type": "application/json",
        "accept": "application/json",
        "user-agent": "test-client/1.0",
        "x-forwarded-for": "127.0.0.1",
        "x-forwarded-proto": "https",
    }
    if headers:
        default_headers.update(headers)

    # Encode body if needed
    encoded_body = None
    if body is not None:
        encoded_body = json.dumps(body) if isinstance(body, (dict, list)) else str(body)

    # Build the event
    event = {
        "version": "2.0",
        "routeKey": f"{method} {path}",
        "rawPath": path,
        "rawQueryString": "",
        "headers": default_headers,
        "requestContext": {
            "accountId": "123456789012",
            "apiId": "test-api-id",
            "authorizer": {
                "jwt": {
                    "claims": claims,
                    "scopes": ["openid", "email"],
                }
            },
            "domainName": "api.example.com",
            "domainPrefix": "api",
            "http": {
                "method": method,
                "path": path,
                "protocol": "HTTP/1.1",
                "sourceIp": "127.0.0.1",
                "userAgent": "test-client/1.0",
            },
            "requestId": "test-request-id-123",
            "routeKey": f"{method} {path}",
            "stage": "$default",
            "time": datetime.now(timezone.utc).strftime("%d/%b/%Y:%H:%M:%S +0000"),
            "timeEpoch": int(datetime.now(timezone.utc).timestamp() * 1000),
        },
        "isBase64Encoded": False,
    }

    # Add optional fields
    if path_parameters:
        event["pathParameters"] = path_parameters

    if query_string_parameters:
        event["queryStringParameters"] = query_string_parameters
        # Build raw query string
        event["rawQueryString"] = "&".join(
            f"{k}={v}" for k, v in query_string_parameters.items()
        )

    if encoded_body is not None:
        event["body"] = encoded_body

    return event


def make_api_gateway_event(
    method: str = "GET",
    path: str = "/",
    path_parameters: Optional[Dict[str, str]] = None,
    query_string_parameters: Optional[Dict[str, str]] = None,
    body: Optional[Any] = None,
    headers: Optional[Dict[str, str]] = None,
    authorizer_claims: Optional[Dict[str, Any]] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create an API Gateway REST API v1 event.

    Args:
        method: HTTP method (GET, POST, PUT, DELETE)
        path: Request path
        path_parameters: Path parameters
        query_string_parameters: Query string parameters
        body: Request body
        headers: Request headers
        authorizer_claims: Cognito authorizer claims
        user_id: Shorthand for setting authorizer_claims["sub"]

    Returns:
        API Gateway REST API v1 event dictionary
    """
    # Build authorizer claims
    claims = authorizer_claims or {}
    if user_id and "sub" not in claims:
        claims["sub"] = user_id

    if not claims:
        claims = {
            "sub": "test-user-123",
            "email": "test@example.com",
        }

    # Build headers
    default_headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if headers:
        default_headers.update(headers)

    # Encode body
    encoded_body = None
    if body is not None:
        encoded_body = json.dumps(body) if isinstance(body, (dict, list)) else str(body)

    event = {
        "resource": path,
        "path": path,
        "httpMethod": method,
        "headers": default_headers,
        "multiValueHeaders": {k: [v] for k, v in default_headers.items()},
        "queryStringParameters": query_string_parameters,
        "multiValueQueryStringParameters": (
            {k: [v] for k, v in query_string_parameters.items()}
            if query_string_parameters
            else None
        ),
        "pathParameters": path_parameters,
        "stageVariables": None,
        "requestContext": {
            "resourceId": "test-resource",
            "authorizer": {
                "claims": claims,
            },
            "resourcePath": path,
            "httpMethod": method,
            "extendedRequestId": "test-extended-request-id",
            "requestTime": datetime.now(timezone.utc).strftime("%d/%b/%Y:%H:%M:%S +0000"),
            "path": f"/prod{path}",
            "accountId": "123456789012",
            "protocol": "HTTP/1.1",
            "stage": "prod",
            "domainPrefix": "api",
            "requestTimeEpoch": int(datetime.now(timezone.utc).timestamp() * 1000),
            "requestId": "test-request-id-123",
            "identity": {
                "sourceIp": "127.0.0.1",
                "userAgent": "test-client/1.0",
            },
            "domainName": "api.example.com",
            "apiId": "test-api-id",
        },
        "body": encoded_body,
        "isBase64Encoded": False,
    }

    return event


# Convenience functions for common event types
def make_get_jobs_event(user_id: str = "test-user-123") -> Dict[str, Any]:
    """Create a GET /jobs event."""
    return make_api_gateway_event_v2(
        method="GET",
        path="/jobs",
        user_id=user_id,
    )


def make_get_job_event(job_id: str, user_id: str = "test-user-123") -> Dict[str, Any]:
    """Create a GET /jobs/{jobId} event."""
    return make_api_gateway_event_v2(
        method="GET",
        path=f"/jobs/{job_id}",
        path_parameters={"jobId": job_id},
        user_id=user_id,
    )


def make_create_job_event(
    template_id: str,
    seed_data_key: str,
    budget_limit: float = 100.0,
    num_records: int = 1000,
    user_id: str = "test-user-123",
) -> Dict[str, Any]:
    """Create a POST /jobs event."""
    return make_api_gateway_event_v2(
        method="POST",
        path="/jobs",
        body={
            "template-id": template_id,
            "seed-data-key": seed_data_key,
            "budget-limit": budget_limit,
            "num-records": num_records,
        },
        user_id=user_id,
    )


def make_delete_job_event(job_id: str, user_id: str = "test-user-123") -> Dict[str, Any]:
    """Create a DELETE /jobs/{jobId} event."""
    return make_api_gateway_event_v2(
        method="DELETE",
        path=f"/jobs/{job_id}",
        path_parameters={"jobId": job_id},
        user_id=user_id,
    )


def make_get_templates_event(user_id: str = "test-user-123") -> Dict[str, Any]:
    """Create a GET /templates event."""
    return make_api_gateway_event_v2(
        method="GET",
        path="/templates",
        user_id=user_id,
    )


def make_create_template_event(
    name: str,
    steps: list,
    schema_requirements: Optional[list] = None,
    user_id: str = "test-user-123",
) -> Dict[str, Any]:
    """Create a POST /templates event."""
    return make_api_gateway_event_v2(
        method="POST",
        path="/templates",
        body={
            "name": name,
            "steps": steps,
            "schema_requirements": schema_requirements or [],
        },
        user_id=user_id,
    )
