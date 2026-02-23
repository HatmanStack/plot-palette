"""
Unit tests for batch CRUD Lambda handlers (list, get, delete).
"""

import json
import os
from decimal import Decimal
from unittest.mock import MagicMock

from tests.unit.handler_import import load_handler

_list_mod = load_handler("lambdas/jobs/list_batches.py", "_handler_list_batches")
_get_mod = load_handler("lambdas/jobs/get_batch.py", "_handler_get_batch")
_delete_mod = load_handler("lambdas/jobs/delete_batch.py", "_handler_delete_batch")

list_batches = _list_mod.lambda_handler
get_batch = _get_mod.lambda_handler
delete_batch = _delete_mod.lambda_handler


def _make_batch(batch_id="batch-001", user_id="user-123", status="RUNNING"):
    return {
        "batch_id": batch_id,
        "user_id": user_id,
        "name": "Test Batch",
        "status": status,
        "created_at": "2025-12-01T10:00:00",
        "updated_at": "2025-12-01T11:00:00",
        "job_ids": ["job-1", "job-2", "job-3"],
        "total_jobs": 3,
        "completed_jobs": 1,
        "failed_jobs": 0,
        "template_id": "tmpl-123",
        "template_version": 1,
        "sweep_config": {"model_tier": ["tier-1", "tier-2", "tier-3"]},
        "total_cost": Decimal("5.25"),
    }


def _make_job(job_id, status="QUEUED", user_id="user-123"):
    return {
        "job_id": job_id,
        "user_id": user_id,
        "status": status,
        "created_at": "2025-12-01T10:00:00",
        "updated_at": "2025-12-01T10:30:00",
        "records_generated": 50 if status == "COMPLETED" else 0,
        "cost_estimate": Decimal("1.50") if status == "COMPLETED" else Decimal("0"),
        "budget_limit": Decimal("10.0"),
    }


class TestListBatches:
    def setup_method(self):
        self.mock_table = MagicMock()
        _list_mod.batches_table = self.mock_table

    def test_list_batches_user_scoped(self):
        """User A has 2 batches, only their batches returned."""
        self.mock_table.query.return_value = {
            "Items": [_make_batch("b-1"), _make_batch("b-2")],
            "Count": 2,
        }

        event = {
            "requestContext": {
                "authorizer": {"jwt": {"claims": {"sub": "user-123"}}},
                "requestId": "req-1",
            },
            "queryStringParameters": None,
        }
        response = list_batches(event, None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert len(body["batches"]) == 2
        # Verify GSI query used user_id
        call_kwargs = self.mock_table.query.call_args[1]
        assert call_kwargs["IndexName"] == "user-id-index"

    def test_list_batches_pagination(self):
        """Returns has_more and last_key when more results exist."""
        self.mock_table.query.return_value = {
            "Items": [_make_batch()],
            "Count": 1,
            "LastEvaluatedKey": {"batch_id": "b-1", "user_id": "user-123", "created_at": "2025-12-01T10:00:00"},
        }

        event = {
            "requestContext": {
                "authorizer": {"jwt": {"claims": {"sub": "user-123"}}},
                "requestId": "req-1",
            },
            "queryStringParameters": None,
        }
        response = list_batches(event, None)

        body = json.loads(response["body"])
        assert body["has_more"] is True
        assert "last_key" in body


class TestGetBatch:
    def setup_method(self):
        self.mock_batches = MagicMock()
        self.mock_jobs = MagicMock()
        _get_mod.batches_table = self.mock_batches
        _get_mod.jobs_table = self.mock_jobs

    def test_get_batch_with_jobs(self):
        """Batch with 3 jobs returns job details."""
        batch = _make_batch()
        self.mock_batches.get_item.return_value = {"Item": batch}

        # The handler reads the table name from env and passes it to batch_get_item.
        # Since the mock's meta.client.batch_get_item returns whatever we configure,
        # we need the Responses key to match the JOBS_TABLE_NAME env var.
        table_name = os.environ.get("JOBS_TABLE_NAME", "plot-palette-Jobs")
        self.mock_jobs.meta.client.batch_get_item.return_value = {
            "Responses": {
                table_name: [
                    _make_job("job-1", "COMPLETED"),
                    _make_job("job-2", "RUNNING"),
                    _make_job("job-3", "QUEUED"),
                ]
            }
        }

        event = {
            "requestContext": {
                "authorizer": {"jwt": {"claims": {"sub": "user-123"}}},
                "requestId": "req-1",
            },
            "pathParameters": {"batch_id": "batch-001"},
        }
        response = get_batch(event, None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["batch_id"] == "batch-001"
        assert len(body["jobs"]) == 3

    def test_get_batch_not_owner(self):
        """Non-owner gets 403."""
        batch = _make_batch(user_id="other-user")
        self.mock_batches.get_item.return_value = {"Item": batch}

        event = {
            "requestContext": {
                "authorizer": {"jwt": {"claims": {"sub": "user-123"}}},
                "requestId": "req-1",
            },
            "pathParameters": {"batch_id": "batch-001"},
        }
        response = get_batch(event, None)

        assert response["statusCode"] == 403

    def test_get_batch_not_found(self):
        """Missing batch returns 404."""
        self.mock_batches.get_item.return_value = {}

        event = {
            "requestContext": {
                "authorizer": {"jwt": {"claims": {"sub": "user-123"}}},
                "requestId": "req-1",
            },
            "pathParameters": {"batch_id": "nonexistent"},
        }
        response = get_batch(event, None)

        assert response["statusCode"] == 404


class TestDeleteBatch:
    def setup_method(self):
        self.mock_batches = MagicMock()
        self.mock_jobs = MagicMock()
        self.mock_sfn = MagicMock()
        self.mock_s3 = MagicMock()
        self.mock_cost_table = MagicMock()
        # S3 paginator must return finite pages (not infinite MagicMock iteration)
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{}]
        self.mock_s3.get_paginator.return_value = mock_paginator
        # Cost tracking query must return finite results
        self.mock_cost_table.query.return_value = {"Items": [], "Count": 0}
        _delete_mod.batches_table = self.mock_batches
        _delete_mod.jobs_table = self.mock_jobs
        _delete_mod.sfn_client = self.mock_sfn
        _delete_mod.s3_client = self.mock_s3
        _delete_mod.cost_tracking_table = self.mock_cost_table

    def test_delete_batch_cancels_running(self):
        """Batch with 1 RUNNING, 1 COMPLETED job: RUNNING cancelled, COMPLETED cleaned up."""
        batch = _make_batch()
        batch["job_ids"] = ["job-1", "job-2"]
        self.mock_batches.get_item.return_value = {"Item": batch}

        self.mock_jobs.get_item.side_effect = [
            {"Item": _make_job("job-1", "RUNNING")},
            {"Item": _make_job("job-2", "COMPLETED")},
        ]

        event = {
            "requestContext": {
                "authorizer": {"jwt": {"claims": {"sub": "user-123"}}},
                "requestId": "req-1",
            },
            "pathParameters": {"batch_id": "batch-001"},
        }
        response = delete_batch(event, None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["jobs_cancelled"] == 1
        assert body["jobs_deleted"] == 1
        # RUNNING job updated to CANCELLED
        self.mock_jobs.update_item.assert_called_once()
        # COMPLETED job record deleted
        self.mock_jobs.delete_item.assert_called_once()
        # Batch record deleted
        self.mock_batches.delete_item.assert_called_once()

    def test_delete_batch_removes_record(self):
        """Batch record is deleted from table."""
        batch = _make_batch()
        batch["job_ids"] = []
        self.mock_batches.get_item.return_value = {"Item": batch}

        event = {
            "requestContext": {
                "authorizer": {"jwt": {"claims": {"sub": "user-123"}}},
                "requestId": "req-1",
            },
            "pathParameters": {"batch_id": "batch-001"},
        }
        response = delete_batch(event, None)

        assert response["statusCode"] == 200
        self.mock_batches.delete_item.assert_called_once()
