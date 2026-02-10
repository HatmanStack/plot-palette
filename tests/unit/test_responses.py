"""Tests for shared Lambda response helpers."""

import json

from backend.shared.lambda_responses import CORS_HEADERS, error_response, success_response


class TestErrorResponse:
    def test_returns_correct_status_code(self):
        result = error_response(400, "Bad request")
        assert result["statusCode"] == 400

    def test_includes_cors_headers(self):
        result = error_response(500, "Server error")
        assert result["headers"] == CORS_HEADERS

    def test_body_contains_error_message(self):
        result = error_response(404, "Not found")
        body = json.loads(result["body"])
        assert body == {"error": "Not found"}

    def test_various_status_codes(self):
        for code in [400, 401, 403, 404, 409, 500]:
            result = error_response(code, "msg")
            assert result["statusCode"] == code


class TestSuccessResponse:
    def test_returns_correct_status_code(self):
        result = success_response(200, {"ok": True})
        assert result["statusCode"] == 200

    def test_includes_cors_headers(self):
        result = success_response(201, {})
        assert result["headers"] == CORS_HEADERS

    def test_serializes_body_as_json(self):
        result = success_response(200, {"job_id": "abc", "count": 5})
        body = json.loads(result["body"])
        assert body == {"job_id": "abc", "count": 5}

    def test_passes_json_kwargs(self):
        from datetime import datetime

        now = datetime(2024, 1, 1, 12, 0, 0)
        result = success_response(200, {"ts": now}, default=str)
        body = json.loads(result["body"])
        assert body["ts"] == "2024-01-01 12:00:00"

    def test_201_status_code(self):
        result = success_response(201, {"id": "new"})
        assert result["statusCode"] == 201
        body = json.loads(result["body"])
        assert body["id"] == "new"
