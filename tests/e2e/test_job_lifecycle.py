"""
E2E tests for job CRUD lifecycle against real LocalStack DynamoDB.
"""

import json
import os
from datetime import datetime
from decimal import Decimal

import boto3
import pytest

from tests.e2e.conftest import ENDPOINT_URL, USER_ID, make_api_event


def _get_jobs_table():
    dynamodb = boto3.resource('dynamodb', endpoint_url=ENDPOINT_URL, region_name='us-east-1')
    return dynamodb.Table(os.environ['JOBS_TABLE_NAME'])


def _get_queue_table():
    dynamodb = boto3.resource('dynamodb', endpoint_url=ENDPOINT_URL, region_name='us-east-1')
    return dynamodb.Table(os.environ['QUEUE_TABLE_NAME'])


def _create_prerequisite_template():
    """Create a template needed for job creation."""
    from lambdas.templates.create_template import lambda_handler

    event = make_api_event('POST', '/templates', body={
        'name': 'Job Test Template',
        'template_definition': {
            'steps': [{'id': 'step1', 'prompt': 'Generate {{ category }}'}]
        },
    })
    resp = lambda_handler(event, None)
    body = json.loads(resp['body'])
    return body['template_id']


def _insert_job_directly(job_id: str, template_id: str):
    """Insert a job record directly into DynamoDB (bypasses ECS worker startup)."""
    jobs_table = _get_jobs_table()
    queue_table = _get_queue_table()
    now = datetime.utcnow().isoformat()

    jobs_table.put_item(Item={
        'job_id': job_id,
        'user_id': USER_ID,
        'status': 'QUEUED',
        'created_at': now,
        'updated_at': now,
        'config': {
            'template_id': template_id,
            'seed_data_path': f'seed-data/{USER_ID}/test.json',
            'budget_limit': Decimal('10'),
            'output_format': 'JSONL',
            'num_records': 100,
        },
        'budget_limit': Decimal('10'),
        'tokens_used': 0,
        'records_generated': 0,
        'cost_estimate': Decimal('0'),
    })

    queue_table.put_item(Item={
        'status': 'QUEUED',
        'job_id_timestamp': f'{job_id}#{now}',
        'job_id': job_id,
        'priority': 5,
        'timestamp': now,
    })

    return now


class TestJobLifecycle:
    """Job CRUD against real DynamoDB."""

    def test_create_job_via_handler(self):
        """Create job through the handler succeeds against real DynamoDB."""
        from lambdas.jobs.create_job import lambda_handler
        from lambdas.jobs.get_job import lambda_handler as get_handler

        template_id = _create_prerequisite_template()

        event = make_api_event('POST', '/jobs', body={
            'template_id': template_id,
            'seed_data_path': f'seed-data/{USER_ID}/test.json',
            'budget_limit': 10.0,
            'output_format': 'JSONL',
            'num_records': 100,
        })

        response = lambda_handler(event, None)
        assert response['statusCode'] == 201
        body = json.loads(response['body'])
        assert body['status'] == 'QUEUED'
        assert 'job_id' in body
        assert 'created_at' in body

        # Verify it's readable via get handler
        job_id = body['job_id']
        get_event = make_api_event('GET', f'/jobs/{job_id}',
                                   path_parameters={'job_id': job_id})
        get_resp = get_handler(get_event, None)
        assert get_resp['statusCode'] == 200

    def test_get_job(self):
        """Get job returns details for a directly-inserted job."""
        from lambdas.jobs.get_job import lambda_handler as get_handler

        template_id = _create_prerequisite_template()
        job_id = 'e2e-get-job-001'
        _insert_job_directly(job_id, template_id)

        get_event = make_api_event('GET', f'/jobs/{job_id}',
                                   path_parameters={'job_id': job_id})
        get_resp = get_handler(get_event, None)

        assert get_resp['statusCode'] == 200
        body = json.loads(get_resp['body'])
        assert body['status'] == 'QUEUED'
        assert body['job_id'] == job_id

    def test_list_jobs(self):
        """List jobs includes directly-inserted job."""
        from lambdas.jobs.list_jobs import lambda_handler as list_handler

        template_id = _create_prerequisite_template()
        job_id = 'e2e-list-job-001'
        _insert_job_directly(job_id, template_id)

        list_event = make_api_event('GET', '/jobs')
        list_resp = list_handler(list_event, None)

        assert list_resp['statusCode'] == 200
        body = json.loads(list_resp['body'])
        job_ids = [j['job_id'] for j in body['jobs']]
        assert job_id in job_ids

    def test_create_with_missing_fields(self):
        """Create job with missing required fields returns 400."""
        from lambdas.jobs.create_job import lambda_handler

        event = make_api_event('POST', '/jobs', body={
            'budget_limit': 10.0,
        })

        response = lambda_handler(event, None)
        assert response['statusCode'] == 400

    def test_create_with_nonexistent_template(self):
        """Create job with non-existent template returns 404."""
        from lambdas.jobs.create_job import lambda_handler

        event = make_api_event('POST', '/jobs', body={
            'template_id': 'nonexistent-template-id',
            'seed_data_path': f'seed-data/{USER_ID}/test.json',
            'budget_limit': 10.0,
            'output_format': 'JSONL',
            'num_records': 100,
        })

        response = lambda_handler(event, None)
        assert response['statusCode'] == 404

    def test_delete_queued_job(self):
        """Delete a QUEUED job marks it as CANCELLED."""
        from lambdas.jobs.delete_job import lambda_handler as delete_handler

        template_id = _create_prerequisite_template()
        job_id = 'e2e-delete-job-001'
        _insert_job_directly(job_id, template_id)

        delete_event = make_api_event('DELETE', f'/jobs/{job_id}',
                                      path_parameters={'job_id': job_id})
        delete_resp = delete_handler(delete_event, None)

        assert delete_resp['statusCode'] == 200

        # Verify job status is CANCELLED
        jobs_table = _get_jobs_table()
        item = jobs_table.get_item(Key={'job_id': job_id})
        assert item['Item']['status'] == 'CANCELLED'

    def test_delete_nonexistent_job(self):
        """Delete non-existent job returns 404."""
        from lambdas.jobs.delete_job import lambda_handler

        event = make_api_event('DELETE', '/jobs/nonexistent-id',
                               path_parameters={'job_id': 'nonexistent-id'})
        response = lambda_handler(event, None)
        assert response['statusCode'] == 404

    def test_get_job_wrong_user(self):
        """Get job owned by another user returns 403."""
        from lambdas.jobs.get_job import lambda_handler as get_handler

        template_id = _create_prerequisite_template()
        job_id = 'e2e-auth-job-001'
        _insert_job_directly(job_id, template_id)

        get_event = make_api_event('GET', f'/jobs/{job_id}',
                                   path_parameters={'job_id': job_id},
                                   user_id='different-user-999')
        get_resp = get_handler(get_event, None)
        assert get_resp['statusCode'] == 403
