"""Tests for download_partial Lambda handler logic."""

import json
from io import BytesIO
from unittest.mock import MagicMock

from backend.shared.lambda_responses import error_response, success_response
from backend.shared.utils import sanitize_error_message

PRESIGNED_URL_EXPIRATION = 3600


def make_event(user_id="user-123", job_id="job-abc", query_params=None):
    return {
        "requestContext": {
            "authorizer": {"jwt": {"claims": {"sub": user_id}}}
        },
        "pathParameters": {"job_id": job_id},
        "queryStringParameters": query_params,
    }


def simulate_download_partial_handler(
    event, jobs_table_mock, s3_client_mock, bucket_name="test-bucket"
):
    """
    Simulate download_partial handler logic without importing the Lambda module.
    Mirrors the core business logic of the handler.
    """
    try:
        user_id = event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]
        job_id = event["pathParameters"]["job_id"]

        response = jobs_table_mock.get_item(Key={"job_id": job_id})

        if "Item" not in response:
            return error_response(404, "Job not found")

        job = response["Item"]

        if job["user_id"] != user_id:
            return error_response(403, "Access denied - you do not own this job")

        records_generated = job.get("records_generated", 0)
        if not records_generated or records_generated <= 0:
            return error_response(400, "No records generated yet")

        # List batch files
        prefix = f"jobs/{job_id}/outputs/"
        paginator = s3_client_mock.get_paginator("list_objects_v2")
        batch_files = []
        for page in paginator.paginate(Bucket=bucket_name, Prefix=prefix):
            for obj in page.get("Contents", []):
                if obj["Key"].endswith(".jsonl"):
                    batch_files.append(obj["Key"])

        if not batch_files:
            return error_response(404, "No batch files found")

        batch_files.sort()

        # Concatenate batch files via multipart upload
        import time

        timestamp = int(time.time())
        partial_key = f"jobs/{job_id}/exports/partial-{timestamp}.jsonl"
        filename = f"job-{job_id[:12]}-partial.jsonl"

        mpu = s3_client_mock.create_multipart_upload(
            Bucket=bucket_name, Key=partial_key
        )
        upload_id = mpu["UploadId"]

        parts = []
        combined = BytesIO()
        for batch_key in batch_files:
            obj = s3_client_mock.get_object(Bucket=bucket_name, Key=batch_key)
            data = obj["Body"].read()
            combined.write(data)
            if not data.endswith(b"\n"):
                combined.write(b"\n")

        combined.seek(0)
        part = s3_client_mock.upload_part(
            Bucket=bucket_name,
            Key=partial_key,
            UploadId=upload_id,
            PartNumber=1,
            Body=combined.read(),
        )
        parts.append({"PartNumber": 1, "ETag": part["ETag"]})

        s3_client_mock.complete_multipart_upload(
            Bucket=bucket_name,
            Key=partial_key,
            UploadId=upload_id,
            MultipartUpload={"Parts": parts},
        )

        # Generate presigned URL
        download_url = s3_client_mock.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": bucket_name,
                "Key": partial_key,
                "ResponseContentDisposition": f'attachment; filename="{filename}"',
            },
            ExpiresIn=PRESIGNED_URL_EXPIRATION,
        )

        return success_response(
            200,
            {
                "download_url": download_url,
                "filename": filename,
                "records_available": records_generated,
                "format": "jsonl",
                "expires_in": PRESIGNED_URL_EXPIRATION,
            },
        )

    except KeyError as e:
        return error_response(
            400, f"Missing required field: {sanitize_error_message(str(e))}"
        )

    except Exception:
        return error_response(500, "Internal server error")


def _make_s3_mock(batch_keys=None, batch_contents=None):
    """Create an S3 mock with paginator and batch files."""
    mock_s3 = MagicMock()

    # Set up paginator
    if batch_keys is None:
        batch_keys = []

    contents = [{"Key": k} for k in batch_keys]
    page = {"Contents": contents} if contents else {}

    mock_paginator = MagicMock()
    mock_paginator.paginate.return_value = [page]
    mock_s3.get_paginator.return_value = mock_paginator

    # Set up batch file reads
    if batch_contents is None:
        batch_contents = {}

    def mock_get_object(Bucket, Key):
        data = batch_contents.get(Key, b'{"record": "data"}\n')
        return {"Body": BytesIO(data)}

    mock_s3.get_object.side_effect = mock_get_object

    # Set up multipart upload
    mock_s3.create_multipart_upload.return_value = {"UploadId": "test-upload-id"}
    mock_s3.upload_part.return_value = {"ETag": '"test-etag"'}
    mock_s3.complete_multipart_upload.return_value = {}

    # Set up presigned URL
    mock_s3.generate_presigned_url.return_value = (
        "https://s3.example.com/partial-export"
    )

    return mock_s3


class TestDownloadPartialLogic:
    def _job_with_records(self, records=100, user_id="user-123", status="RUNNING"):
        return {
            "job_id": "job-abc",
            "user_id": user_id,
            "status": status,
            "records_generated": records,
            "config": {"output_format": "JSONL"},
        }

    def test_download_partial_success(self):
        """Mock S3 list (2 batch files), mock read, mock multipart upload,
        mock presigned URL. Assert 200 response with download_url and records_available."""
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

        result = simulate_download_partial_handler(
            make_event(), mock_table, mock_s3
        )

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["download_url"] == "https://s3.example.com/partial-export"
        assert body["records_available"] == 100
        assert body["format"] == "jsonl"
        assert body["expires_in"] == 3600
        assert "partial" in body["filename"]

    def test_download_partial_no_records(self):
        """Mock job with records_generated=0. Assert 400."""
        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": self._job_with_records(0)}

        result = simulate_download_partial_handler(
            make_event(), mock_table, MagicMock()
        )

        assert result["statusCode"] == 400
        body = json.loads(result["body"])
        assert "no records" in body["error"].lower()

    def test_download_partial_not_owner(self):
        """Mock job with different user_id. Assert 403."""
        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            "Item": self._job_with_records(100, user_id="other-user")
        }

        result = simulate_download_partial_handler(
            make_event(), mock_table, MagicMock()
        )

        assert result["statusCode"] == 403

    def test_download_partial_no_batches(self):
        """Mock S3 list returning empty. Assert 404."""
        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": self._job_with_records(100)}

        mock_s3 = _make_s3_mock(batch_keys=[])

        result = simulate_download_partial_handler(
            make_event(), mock_table, mock_s3
        )

        assert result["statusCode"] == 404
        body = json.loads(result["body"])
        assert "no batch files" in body["error"].lower()

    def test_download_partial_job_not_found(self):
        """Mock get_item returning no Item. Assert 404."""
        mock_table = MagicMock()
        mock_table.get_item.return_value = {}

        result = simulate_download_partial_handler(
            make_event(), mock_table, MagicMock()
        )

        assert result["statusCode"] == 404

    def test_download_partial_missing_path_params(self):
        """Missing path parameters should return 400."""
        event = {
            "requestContext": {
                "authorizer": {"jwt": {"claims": {"sub": "user-123"}}}
            }
        }

        result = simulate_download_partial_handler(
            event, MagicMock(), MagicMock()
        )

        assert result["statusCode"] == 400

    def test_download_partial_concatenation_order(self):
        """Batch files should be sorted and concatenated in order."""
        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": self._job_with_records(100)}

        # Provide batch keys in reverse order to test sorting
        batch_keys = [
            "jobs/job-abc/outputs/batch-0002.jsonl",
            "jobs/job-abc/outputs/batch-0000.jsonl",
            "jobs/job-abc/outputs/batch-0001.jsonl",
        ]
        mock_s3 = _make_s3_mock(batch_keys)

        result = simulate_download_partial_handler(
            make_event(), mock_table, mock_s3
        )

        assert result["statusCode"] == 200
        # Verify get_object was called in sorted order
        calls = mock_s3.get_object.call_args_list
        keys = [c.kwargs["Key"] for c in calls]
        assert keys == sorted(keys)

    def test_download_partial_works_for_any_status_with_records(self):
        """Partial download should work for RUNNING, FAILED, CANCELLED, BUDGET_EXCEEDED."""
        for status in ["RUNNING", "FAILED", "CANCELLED", "BUDGET_EXCEEDED"]:
            mock_table = MagicMock()
            mock_table.get_item.return_value = {
                "Item": self._job_with_records(50, status=status)
            }
            mock_s3 = _make_s3_mock(
                ["jobs/job-abc/outputs/batch-0000.jsonl"]
            )

            result = simulate_download_partial_handler(
                make_event(), mock_table, mock_s3
            )

            assert result["statusCode"] == 200, f"Failed for status {status}"
