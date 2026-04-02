"""Tests for shared Lambda response helpers."""

import json
import logging

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

    def test_handles_non_serializable_message(self):
        from decimal import Decimal

        # error_response should not crash when message contains non-JSON-native types
        result = error_response(400, str(Decimal("3.14")))
        body = json.loads(result["body"])
        assert body == {"error": "3.14"}


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


class TestCORSOriginValidation:
    def test_missing_allowed_origin_logs_error(self):
        """When ALLOWED_ORIGIN is not set, an ERROR log should be emitted."""
        import importlib
        import os

        import backend.shared.lambda_responses as lr_mod

        original = os.environ.pop("ALLOWED_ORIGIN", None)
        try:
            logger_obj = logging.getLogger("backend.shared.lambda_responses")
            records: list[logging.LogRecord] = []

            class _Handler(logging.Handler):
                def emit(self, record):
                    records.append(record)

            handler = _Handler()
            handler.setLevel(logging.DEBUG)
            logger_obj.addHandler(handler)
            try:
                importlib.reload(lr_mod)
            finally:
                logger_obj.removeHandler(handler)

            error_logs = [r for r in records if r.levelno >= logging.ERROR]
            assert len(error_logs) >= 1
            assert "ALLOWED_ORIGIN" in error_logs[0].getMessage()
        finally:
            if original is not None:
                os.environ["ALLOWED_ORIGIN"] = original
            importlib.reload(lr_mod)
