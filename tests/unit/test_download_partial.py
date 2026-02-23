"""Tests for download_partial Lambda handler — calls actual lambda_handler."""

import json
import os
from io import BytesIO
from unittest.mock import MagicMock, patch

from tests.unit.handler_import import load_handler

# Load the actual handler module
_mod = load_handler("lambdas/jobs/download_partial.py")
lambda_handler = _mod.lambda_handler


def make_event(user_id="user-123", job_id="job-abc", query_params=None):
    return {
        "requestContext": {
            "authorizer": {"jwt": {"claims": {"sub": user_id}}}
        },
        "pathParameters": {"job_id": job_id},
        "queryStringParameters": query_params,
    }


def _make_s3_mock(batch_keys=None, batch_contents=None):
    """Create an S3 mock with paginator and batch files."""
    mock_s3 = MagicMock()

    if batch_keys is None:
        batch_keys = []

    contents = [{"Key": k} for k in batch_keys]
    page = {"Contents": contents} if contents else {}

    mock_paginator = MagicMock()
    mock_paginator.paginate.return_value = [page]
    mock_s3.get_paginator.return_value = mock_paginator

    if batch_contents is None:
        batch_contents = {}

    def mock_get_object(Bucket, Key):
        data = batch_contents.get(Key, b'{"record": "data"}\n')
        return {"Body": BytesIO(data)}

    mock_s3.get_object.side_effect = mock_get_object

    mock_s3.create_multipart_upload.return_value = {"UploadId": "test-upload-id"}
    mock_s3.upload_part.return_value = {"ETag": '"test-etag"'}
    mock_s3.complete_multipart_upload.return_value = {}

    mock_s3.generate_presigned_url.return_value = (
        "https://s3.example.com/partial-export"
    )

    return mock_s3


def _invoke(event, mock_table, mock_s3, bucket_name="test-bucket"):
    """Invoke the actual lambda_handler with patched module-level clients."""
    _mod.jobs_table = mock_table
    _mod.s3_client = mock_s3
    _mod.bucket_name = bucket_name
    return lambda_handler(event, None)


class TestDownloadPartialHandler:
    def _job_with_records(self, records=100, user_id="user-123", status="RUNNING"):
        return {
            "job_id": "job-abc",
            "user_id": user_id,
            "status": status,
            "records_generated": records,
            "config": {"output_format": "JSONL"},
        }

    def test_download_partial_success(self):
        """Invoke actual handler: 2 batch files -> 200 with download_url."""
        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": self._job_with_records(100)}

        batch_keys = [
            "jobs/job-abc/outputs/batch-0000.jsonl",
            "jobs/job-abc/outputs/batch-0001.jsonl",
        ]
        batch_contents = {
            "jobs/job-abc/outputs/batch-0000.jsonl": b'{"id": 1}\n{"id": 2}\n',
            "jobs/job-abc/outputs/batch-0001.jsonl": b'{"id": 3}\n{"id": 4}\n',
        }
        mock_s3 = _make_s3_mock(batch_keys, batch_contents)

        result = _invoke(make_event(), mock_table, mock_s3)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["download_url"] == "https://s3.example.com/partial-export"
        assert body["records_available"] == 100
        assert body["format"] == "jsonl"
        assert body["expires_in"] == 3600
        assert "partial" in body["filename"]

    def test_download_partial_no_records(self):
        """Invoke actual handler: records_generated=0 -> 400."""
        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": self._job_with_records(0)}

        result = _invoke(make_event(), mock_table, MagicMock())

        assert result["statusCode"] == 400
        body = json.loads(result["body"])
        assert "no records" in body["error"].lower()

    def test_download_partial_not_owner(self):
        """Invoke actual handler: different user_id -> 403."""
        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            "Item": self._job_with_records(100, user_id="other-user")
        }

        result = _invoke(make_event(), mock_table, MagicMock())

        assert result["statusCode"] == 403

    def test_download_partial_no_batches(self):
        """Invoke actual handler: S3 list empty -> 404."""
        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": self._job_with_records(100)}

        mock_s3 = _make_s3_mock(batch_keys=[])

        result = _invoke(make_event(), mock_table, mock_s3)

        assert result["statusCode"] == 404
        body = json.loads(result["body"])
        assert "no batch files" in body["error"].lower()

    def test_download_partial_job_not_found(self):
        """Invoke actual handler: no Item in response -> 404."""
        mock_table = MagicMock()
        mock_table.get_item.return_value = {}

        result = _invoke(make_event(), mock_table, MagicMock())

        assert result["statusCode"] == 404

    def test_download_partial_missing_path_params(self):
        """Invoke actual handler: missing pathParameters -> 400."""
        event = {
            "requestContext": {
                "authorizer": {"jwt": {"claims": {"sub": "user-123"}}}
            }
        }

        result = _invoke(event, MagicMock(), MagicMock())

        assert result["statusCode"] == 400

    def test_download_partial_concatenation_order(self):
        """Invoke actual handler: batch files sorted before concatenation."""
        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": self._job_with_records(100)}

        batch_keys = [
            "jobs/job-abc/outputs/batch-0002.jsonl",
            "jobs/job-abc/outputs/batch-0000.jsonl",
            "jobs/job-abc/outputs/batch-0001.jsonl",
        ]
        mock_s3 = _make_s3_mock(batch_keys)

        result = _invoke(make_event(), mock_table, mock_s3)

        assert result["statusCode"] == 200
        calls = mock_s3.get_object.call_args_list
        keys = [c.kwargs["Key"] for c in calls]
        assert keys == sorted(keys)

    def test_download_partial_works_for_any_status_with_records(self):
        """Invoke actual handler: works for RUNNING, FAILED, CANCELLED, BUDGET_EXCEEDED."""
        for status in ["RUNNING", "FAILED", "CANCELLED", "BUDGET_EXCEEDED"]:
            mock_table = MagicMock()
            mock_table.get_item.return_value = {
                "Item": self._job_with_records(50, status=status)
            }
            mock_s3 = _make_s3_mock(
                ["jobs/job-abc/outputs/batch-0000.jsonl"]
            )

            result = _invoke(make_event(), mock_table, mock_s3)

            assert result["statusCode"] == 200, f"Failed for status {status}"
