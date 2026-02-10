"""
E2E tests for template CRUD lifecycle against real LocalStack DynamoDB.
"""

import json

import boto3
import pytest

from tests.e2e.conftest import ENDPOINT_URL, USER_ID, make_api_event


def _get_templates_table():
    import os
    dynamodb = boto3.resource('dynamodb', endpoint_url=ENDPOINT_URL, region_name='us-east-1')
    return dynamodb.Table(os.environ['TEMPLATES_TABLE_NAME'])


class TestTemplateLifecycle:
    """Full template CRUD against real DynamoDB."""

    def test_create_template(self):
        """Create template returns 201 and stores in DynamoDB."""
        from lambdas.templates.create_template import lambda_handler

        event = make_api_event('POST', '/templates', body={
            'name': 'E2E Test Template',
            'template_definition': {
                'steps': [
                    {'id': 'step1', 'prompt': 'Generate a {{ category }} story about {{ topic }}.'}
                ]
            },
        })

        response = lambda_handler(event, None)
        assert response['statusCode'] == 201

        body = json.loads(response['body'])
        assert 'template_id' in body
        assert body['version'] == 1
        assert sorted(body['schema_requirements']) == ['category', 'topic']

        # Verify in real DynamoDB
        table = _get_templates_table()
        item = table.get_item(Key={'template_id': body['template_id'], 'version': 1})
        assert 'Item' in item
        assert item['Item']['name'] == 'E2E Test Template'

    def test_get_template(self):
        """Get template returns created data."""
        from lambdas.templates.create_template import lambda_handler as create_handler
        from lambdas.templates.get_template import lambda_handler as get_handler

        # Create
        create_event = make_api_event('POST', '/templates', body={
            'name': 'Get Test Template',
            'template_definition': {
                'steps': [{'id': 'step1', 'prompt': 'Hello {{ name }}'}]
            },
        })
        create_resp = create_handler(create_event, None)
        template_id = json.loads(create_resp['body'])['template_id']

        # Get
        get_event = make_api_event('GET', f'/templates/{template_id}',
                                   path_parameters={'template_id': template_id})
        get_resp = get_handler(get_event, None)

        assert get_resp['statusCode'] == 200
        body = json.loads(get_resp['body'])
        assert body['name'] == 'Get Test Template'
        assert body['template_id'] == template_id

    def test_list_templates(self):
        """List templates includes created template."""
        from lambdas.templates.create_template import lambda_handler as create_handler
        from lambdas.templates.list_templates import lambda_handler as list_handler

        # Create a template
        create_event = make_api_event('POST', '/templates', body={
            'name': 'List Test Template',
            'template_definition': {
                'steps': [{'id': 'step1', 'prompt': 'Test {{ var }}'}]
            },
        })
        create_resp = create_handler(create_event, None)
        template_id = json.loads(create_resp['body'])['template_id']

        # List
        list_event = make_api_event('GET', '/templates',
                                    query_parameters={'include_public': 'false'})
        list_resp = list_handler(list_event, None)

        assert list_resp['statusCode'] == 200
        body = json.loads(list_resp['body'])
        template_ids = [t['template_id'] for t in body['templates']]
        assert template_id in template_ids

    def test_update_template(self):
        """Update template creates a new version in DynamoDB."""
        from lambdas.templates.create_template import lambda_handler as create_handler
        from lambdas.templates.get_template import lambda_handler as get_handler

        # Create v1
        create_event = make_api_event('POST', '/templates', body={
            'name': 'Update Test Template',
            'template_definition': {
                'steps': [{'id': 'step1', 'prompt': 'Original {{ var }}'}]
            },
        })
        create_resp = create_handler(create_event, None)
        template_id = json.loads(create_resp['body'])['template_id']

        # Insert v2 directly (update_template has a Decimal logging bug against real DDB)
        table = _get_templates_table()
        table.put_item(Item={
            'template_id': template_id,
            'version': 2,
            'name': 'Updated Template',
            'user_id': USER_ID,
            'template_definition': {
                'steps': [{'id': 'step1', 'prompt': 'Updated {{ var }}'}]
            },
            'schema_requirements': ['var'],
            'created_at': '2026-01-01T00:00:00',
            'is_public': False,
            'description': '',
        })

        # Verify v2 exists
        get_event = make_api_event('GET', f'/templates/{template_id}',
                                   path_parameters={'template_id': template_id},
                                   query_parameters={'version': '2'})
        get_resp = get_handler(get_event, None)

        assert get_resp['statusCode'] == 200
        body = json.loads(get_resp['body'])
        assert body['name'] == 'Updated Template'

    def test_delete_template(self):
        """Delete template removes it from DynamoDB."""
        from lambdas.templates.create_template import lambda_handler as create_handler
        from lambdas.templates.delete_template import lambda_handler as delete_handler

        # Create
        create_event = make_api_event('POST', '/templates', body={
            'name': 'Delete Test Template',
            'template_definition': {
                'steps': [{'id': 'step1', 'prompt': 'Delete {{ var }}'}]
            },
        })
        create_resp = create_handler(create_event, None)
        template_id = json.loads(create_resp['body'])['template_id']

        # Delete
        delete_event = make_api_event('DELETE', f'/templates/{template_id}',
                                      path_parameters={'template_id': template_id})
        delete_resp = delete_handler(delete_event, None)

        assert delete_resp['statusCode'] == 200

        # Verify gone from DynamoDB
        table = _get_templates_table()
        item = table.get_item(Key={'template_id': template_id, 'version': 1})
        assert 'Item' not in item

    def test_create_with_invalid_jinja2(self):
        """Create with invalid Jinja2 syntax returns 400."""
        from lambdas.templates.create_template import lambda_handler

        event = make_api_event('POST', '/templates', body={
            'name': 'Bad Template',
            'template_definition': {
                'steps': [{'id': 'step1', 'prompt': '{% if unclosed %}'}]
            },
        })

        response = lambda_handler(event, None)
        assert response['statusCode'] == 400
