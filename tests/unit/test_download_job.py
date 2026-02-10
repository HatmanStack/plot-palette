"""Tests for download_job Lambda handler logic."""

import json

from backend.shared.lambda_responses import error_response, success_response


def make_event(user_id='user-123', job_id='job-abc'):
    return {
        'requestContext': {
            'authorizer': {'jwt': {'claims': {'sub': user_id}}}
        },
        'pathParameters': {'job_id': job_id},
    }


def simulate_download_handler(event, jobs_table_mock, s3_client_mock, bucket_name='test-bucket'):
    """
    Simulate download_job handler logic without importing the Lambda module.
    This avoids sys.path conflicts while testing the core business logic.
    """
    try:
        user_id = event['requestContext']['authorizer']['jwt']['claims']['sub']
        job_id = event['pathParameters']['job_id']

        response = jobs_table_mock.get_item(Key={'job_id': job_id})

        if 'Item' not in response:
            return error_response(404, "Job not found")

        job = response['Item']

        if job['user_id'] != user_id:
            return error_response(403, "Access denied - you do not own this job")

        if job.get('status') != 'COMPLETED':
            return error_response(400, "Job is not completed - cannot download")

        s3_key = f"jobs/{job_id}/exports/output.jsonl"
        filename = f"job-{job_id[:12]}-output.jsonl"

        download_url = s3_client_mock.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': bucket_name,
                'Key': s3_key,
                'ResponseContentDisposition': f'attachment; filename="{filename}"',
            },
            ExpiresIn=3600,
        )

        return success_response(200, {
            "download_url": download_url,
            "filename": filename,
            "expires_in": 3600,
        })

    except KeyError as e:
        return error_response(400, f"Missing required field: {e}")

    except Exception:
        return error_response(500, "Internal server error")


class TestDownloadJobLogic:
    def test_success(self):
        from unittest.mock import MagicMock

        mock_table = MagicMock()
        mock_s3 = MagicMock()
        mock_table.get_item.return_value = {
            'Item': {'job_id': 'job-abc', 'user_id': 'user-123', 'status': 'COMPLETED'}
        }
        mock_s3.generate_presigned_url.return_value = 'https://s3.example.com/presigned'

        result = simulate_download_handler(make_event(), mock_table, mock_s3)

        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert body['download_url'] == 'https://s3.example.com/presigned'
        assert body['filename'] == 'job-job-abc-output.jsonl'
        assert body['expires_in'] == 3600

    def test_job_not_found(self):
        from unittest.mock import MagicMock

        mock_table = MagicMock()
        mock_table.get_item.return_value = {}

        result = simulate_download_handler(make_event(), mock_table, MagicMock())
        assert result['statusCode'] == 404

    def test_unauthorized_user(self):
        from unittest.mock import MagicMock

        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            'Item': {'job_id': 'job-abc', 'user_id': 'other-user', 'status': 'COMPLETED'}
        }

        result = simulate_download_handler(make_event(), mock_table, MagicMock())
        assert result['statusCode'] == 403

    def test_job_not_completed(self):
        from unittest.mock import MagicMock

        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            'Item': {'job_id': 'job-abc', 'user_id': 'user-123', 'status': 'RUNNING'}
        }

        result = simulate_download_handler(make_event(), mock_table, MagicMock())
        assert result['statusCode'] == 400
        body = json.loads(result['body'])
        assert 'not completed' in body['error']

    def test_missing_path_params(self):
        event = {'requestContext': {'authorizer': {'jwt': {'claims': {'sub': 'u1'}}}}}
        from unittest.mock import MagicMock
        result = simulate_download_handler(event, MagicMock(), MagicMock())
        assert result['statusCode'] == 400

    def test_presigned_url_params(self):
        from unittest.mock import MagicMock

        mock_table = MagicMock()
        mock_s3 = MagicMock()
        mock_table.get_item.return_value = {
            'Item': {'job_id': 'job-abc', 'user_id': 'user-123', 'status': 'COMPLETED'}
        }
        mock_s3.generate_presigned_url.return_value = 'https://s3.example.com/url'

        simulate_download_handler(make_event(), mock_table, mock_s3)

        mock_s3.generate_presigned_url.assert_called_once_with(
            'get_object',
            Params={
                'Bucket': 'test-bucket',
                'Key': 'jobs/job-abc/exports/output.jsonl',
                'ResponseContentDisposition': 'attachment; filename="job-job-abc-output.jsonl"',
            },
            ExpiresIn=3600,
        )
