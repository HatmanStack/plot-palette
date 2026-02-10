"""
E2E tests for seed data upload URL generation and validation.
"""

import json
import os

import boto3
import pytest

from tests.e2e.conftest import ENDPOINT_URL, USER_ID, make_api_event


class TestSeedData:
    """Seed data operations against real LocalStack S3."""

    def test_generate_upload_url(self):
        """Generate presigned upload URL contains LocalStack endpoint."""
        from lambdas.seed_data.generate_upload_url import lambda_handler

        event = make_api_event('POST', '/seed-data/upload', body={
            'filename': 'test-data.json',
            'content_type': 'application/json',
        })

        response = lambda_handler(event, None)
        assert response['statusCode'] == 200

        body = json.loads(response['body'])
        assert 'upload_url' in body
        assert 's3_key' in body
        assert USER_ID in body['s3_key']
        # Presigned URL should point at LocalStack
        assert 'localhost' in body['upload_url'] or '4566' in body['upload_url']

    def test_upload_and_validate_seed_data(self):
        """Upload seed data to S3 then validate against template with no schema requirements."""
        from lambdas.seed_data.validate_seed_data import lambda_handler as validate_handler
        from lambdas.templates.create_template import lambda_handler as create_template

        # Create template with NO schema requirements (no variables)
        # This avoids Range header issues with LocalStack's S3
        template_event = make_api_event('POST', '/templates', body={
            'name': 'Simple Seed Template',
            'template_definition': {
                'steps': [{'id': 'step1', 'prompt': 'Generate a creative story.'}]
            },
        })
        template_resp = create_template(template_event, None)
        template_id = json.loads(template_resp['body'])['template_id']

        # Upload seed data directly to S3
        s3 = boto3.client('s3', endpoint_url=ENDPOINT_URL, region_name='us-east-1')
        bucket = os.environ['BUCKET_NAME']
        s3_key = f'seed-data/{USER_ID}/valid-data.json'
        seed_data = [{'topic': 'AI'}, {'topic': 'cooking'}]
        s3.put_object(Bucket=bucket, Key=s3_key, Body=json.dumps(seed_data))

        # Validate (template has no schema reqs, so validation passes trivially)
        validate_event = make_api_event('POST', '/seed-data/validate', body={
            's3_key': s3_key,
            'template_id': template_id,
        })
        validate_resp = validate_handler(validate_event, None)

        assert validate_resp['statusCode'] == 200
        body = json.loads(validate_resp['body'])
        assert body['valid'] is True

    def test_validate_malformed_json(self):
        """Validate malformed JSON seed data returns error."""
        from lambdas.seed_data.validate_seed_data import lambda_handler as validate_handler
        from lambdas.templates.create_template import lambda_handler as create_template

        # Create template
        template_event = make_api_event('POST', '/templates', body={
            'name': 'Malformed Test Template',
            'template_definition': {
                'steps': [{'id': 'step1', 'prompt': 'Hello {{ name }}'}]
            },
        })
        template_resp = create_template(template_event, None)
        template_id = json.loads(template_resp['body'])['template_id']

        # Upload malformed JSON
        s3 = boto3.client('s3', endpoint_url=ENDPOINT_URL, region_name='us-east-1')
        bucket = os.environ['BUCKET_NAME']
        s3_key = f'seed-data/{USER_ID}/bad-data.json'
        s3.put_object(Bucket=bucket, Key=s3_key, Body=b'not valid json {{{')

        # Validate
        validate_event = make_api_event('POST', '/seed-data/validate', body={
            's3_key': s3_key,
            'template_id': template_id,
        })
        validate_resp = validate_handler(validate_event, None)

        assert validate_resp['statusCode'] == 400
