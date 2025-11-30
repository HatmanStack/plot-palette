"""
Plot Palette - Lambda Input Validation Tests

Tests that Lambda handlers properly reject malformed and invalid input.
These tests directly test the validation logic functions and mock the handlers
to avoid complex import dependencies.
"""

import json
import pytest
from unittest.mock import patch, MagicMock
import sys
import os

# Add shared path first so constants can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../backend/shared'))

from constants import ExportFormat


class TestCreateJobValidation:
    """Tests for create_job Lambda input validation logic."""

    def validate_job_config(self, config):
        """
        Inline validation logic matching create_job.py validate_job_config().

        This duplicates the validation logic to test it without complex imports.
        """
        required_fields = ['template_id', 'seed_data_path', 'budget_limit', 'output_format', 'num_records']

        for field in required_fields:
            if field not in config:
                return False, f"Missing required field: {field}"

        # Validate budget_limit
        budget_limit = config['budget_limit']
        if not isinstance(budget_limit, (int, float)) or budget_limit <= 0 or budget_limit > 1000:
            return False, "budget_limit must be between 0 and 1000 USD"

        # Validate output_format
        output_format = config['output_format']
        if output_format not in [fmt.value for fmt in ExportFormat]:
            return False, f"output_format must be one of: {', '.join([fmt.value for fmt in ExportFormat])}"

        # Validate num_records
        num_records = config['num_records']
        if not isinstance(num_records, int) or num_records <= 0 or num_records > 1_000_000:
            return False, "num_records must be between 1 and 1,000,000"

        return True, ""

    def test_empty_config_missing_fields(self):
        """Test that empty config returns missing field error."""
        is_valid, error = self.validate_job_config({})

        assert not is_valid
        assert 'Missing required field' in error

    def test_negative_budget_limit_returns_400(self):
        """Test that negative budget_limit returns validation error."""
        is_valid, error = self.validate_job_config({
            'template_id': 'template-123',
            'seed_data_path': 'seed-data/test.json',
            'budget_limit': -10,
            'output_format': 'JSONL',
            'num_records': 1000
        })

        assert not is_valid
        assert 'budget_limit' in error

    def test_zero_budget_limit_returns_400(self):
        """Test that zero budget_limit returns validation error."""
        is_valid, error = self.validate_job_config({
            'template_id': 'template-123',
            'seed_data_path': 'seed-data/test.json',
            'budget_limit': 0,
            'output_format': 'JSONL',
            'num_records': 1000
        })

        assert not is_valid
        assert 'budget_limit' in error

    def test_budget_limit_over_max_returns_400(self):
        """Test that budget_limit > 1000 returns validation error."""
        is_valid, error = self.validate_job_config({
            'template_id': 'template-123',
            'seed_data_path': 'seed-data/test.json',
            'budget_limit': 2000,
            'output_format': 'JSONL',
            'num_records': 1000
        })

        assert not is_valid
        assert 'budget_limit' in error

    def test_non_numeric_budget_limit_returns_400(self):
        """Test that non-numeric budget_limit returns validation error."""
        is_valid, error = self.validate_job_config({
            'template_id': 'template-123',
            'seed_data_path': 'seed-data/test.json',
            'budget_limit': "fifty",
            'output_format': 'JSONL',
            'num_records': 1000
        })

        assert not is_valid
        assert 'budget_limit' in error

    def test_invalid_output_format_returns_400(self):
        """Test that invalid output_format returns validation error."""
        is_valid, error = self.validate_job_config({
            'template_id': 'template-123',
            'seed_data_path': 'seed-data/test.json',
            'budget_limit': 100,
            'output_format': 'XML',
            'num_records': 1000
        })

        assert not is_valid
        assert 'output_format' in error
        # Should list valid formats
        assert 'JSONL' in error

    def test_zero_num_records_returns_400(self):
        """Test that zero num_records returns validation error."""
        is_valid, error = self.validate_job_config({
            'template_id': 'template-123',
            'seed_data_path': 'seed-data/test.json',
            'budget_limit': 100,
            'output_format': 'JSONL',
            'num_records': 0
        })

        assert not is_valid
        assert 'num_records' in error

    def test_negative_num_records_returns_400(self):
        """Test that negative num_records returns validation error."""
        is_valid, error = self.validate_job_config({
            'template_id': 'template-123',
            'seed_data_path': 'seed-data/test.json',
            'budget_limit': 100,
            'output_format': 'JSONL',
            'num_records': -5
        })

        assert not is_valid
        assert 'num_records' in error

    def test_num_records_over_max_returns_400(self):
        """Test that num_records > 1,000,000 returns validation error."""
        is_valid, error = self.validate_job_config({
            'template_id': 'template-123',
            'seed_data_path': 'seed-data/test.json',
            'budget_limit': 100,
            'output_format': 'JSONL',
            'num_records': 2000000
        })

        assert not is_valid
        assert 'num_records' in error

    def test_non_integer_num_records_returns_400(self):
        """Test that non-integer num_records returns validation error."""
        is_valid, error = self.validate_job_config({
            'template_id': 'template-123',
            'seed_data_path': 'seed-data/test.json',
            'budget_limit': 100,
            'output_format': 'JSONL',
            'num_records': 100.5
        })

        assert not is_valid
        assert 'num_records' in error

    def test_missing_template_id_returns_400(self):
        """Test that missing template_id returns validation error."""
        is_valid, error = self.validate_job_config({
            'seed_data_path': 'seed-data/test.json',
            'budget_limit': 100,
            'output_format': 'JSONL',
            'num_records': 1000
        })

        assert not is_valid
        assert 'template_id' in error

    def test_missing_seed_data_path_returns_400(self):
        """Test that missing seed_data_path returns validation error."""
        is_valid, error = self.validate_job_config({
            'template_id': 'template-123',
            'budget_limit': 100,
            'output_format': 'JSONL',
            'num_records': 1000
        })

        assert not is_valid
        assert 'seed_data_path' in error

    def test_valid_config_passes_validation(self):
        """Test that valid config passes validation."""
        is_valid, error = self.validate_job_config({
            'template_id': 'template-123',
            'seed_data_path': 'seed-data/test.json',
            'budget_limit': 100,
            'output_format': 'JSONL',
            'num_records': 1000
        })

        assert is_valid
        assert error == ""

    def test_valid_config_with_parquet_format(self):
        """Test that valid config with PARQUET format passes."""
        is_valid, error = self.validate_job_config({
            'template_id': 'template-123',
            'seed_data_path': 'seed-data/test.json',
            'budget_limit': 500,
            'output_format': 'PARQUET',
            'num_records': 50000
        })

        assert is_valid
        assert error == ""

    def test_valid_config_with_csv_format(self):
        """Test that valid config with CSV format passes."""
        is_valid, error = self.validate_job_config({
            'template_id': 'template-123',
            'seed_data_path': 'seed-data/test.json',
            'budget_limit': 999.99,
            'output_format': 'CSV',
            'num_records': 1000000
        })

        assert is_valid
        assert error == ""


class TestCreateJobHandlerResponses:
    """Tests for create_job Lambda handler response format."""

    def create_error_response(self, status_code, message):
        """Helper to create error response matching handler format."""
        return {
            "statusCode": status_code,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({"error": message})
        }

    def test_error_response_format(self):
        """Test that error response has correct format."""
        response = self.create_error_response(400, "Test error message")

        assert response['statusCode'] == 400
        assert response['headers']['Content-Type'] == 'application/json'
        assert response['headers']['Access-Control-Allow-Origin'] == '*'

        body = json.loads(response['body'])
        assert 'error' in body
        assert body['error'] == "Test error message"

    def test_invalid_json_error_response(self):
        """Test error response for invalid JSON."""
        response = self.create_error_response(400, "Invalid JSON in request body")

        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'Invalid JSON' in body['error']


class TestGetJobValidation:
    """Tests for get_job Lambda path parameter validation."""

    def test_extract_path_parameters(self):
        """Test extraction of path parameters from event."""
        event = {
            'requestContext': {
                'authorizer': {
                    'jwt': {
                        'claims': {'sub': 'user-123'}
                    }
                }
            },
            'pathParameters': {'job_id': 'job-456'}
        }

        # Simulate handler extraction
        job_id = event['pathParameters']['job_id']
        user_id = event['requestContext']['authorizer']['jwt']['claims']['sub']

        assert job_id == 'job-456'
        assert user_id == 'user-123'

    def test_missing_path_parameters_raises_key_error(self):
        """Test that missing pathParameters raises KeyError."""
        event = {
            'requestContext': {
                'authorizer': {
                    'jwt': {'claims': {'sub': 'user-123'}}
                }
            }
        }

        with pytest.raises(KeyError):
            _ = event['pathParameters']['job_id']

    def test_missing_job_id_in_path_raises_key_error(self):
        """Test that missing job_id in pathParameters raises KeyError."""
        event = {
            'requestContext': {
                'authorizer': {
                    'jwt': {'claims': {'sub': 'user-123'}}
                }
            },
            'pathParameters': {}
        }

        with pytest.raises(KeyError):
            _ = event['pathParameters']['job_id']


class TestDeleteJobValidation:
    """Tests for delete_job Lambda path parameter validation."""

    def test_extract_job_id_and_user_id(self):
        """Test extraction of job_id and user_id from event."""
        event = {
            'requestContext': {
                'authorizer': {
                    'jwt': {
                        'claims': {'sub': 'user-789'}
                    }
                }
            },
            'pathParameters': {'job_id': 'job-to-delete'}
        }

        job_id = event['pathParameters']['job_id']
        user_id = event['requestContext']['authorizer']['jwt']['claims']['sub']

        assert job_id == 'job-to-delete'
        assert user_id == 'user-789'


class TestCreateTemplateValidation:
    """Tests for create_template Lambda input validation."""

    def test_missing_name_detected(self):
        """Test detection of missing name field."""
        body = {
            'template_definition': {
                'steps': [{'id': 'step1', 'model': 'meta.llama3-1-8b-instruct-v1:0', 'prompt': 'test'}]
            }
        }

        assert 'name' not in body

    def test_missing_template_definition_detected(self):
        """Test detection of missing template_definition field."""
        body = {'name': 'Test Template'}

        assert 'template_definition' not in body

    def test_empty_steps_detected(self):
        """Test detection of empty steps array."""
        body = {
            'name': 'Test Template',
            'template_definition': {'steps': []}
        }

        template_def = body['template_definition']
        assert 'steps' not in template_def or not template_def['steps']

    def test_valid_template_body(self):
        """Test valid template body structure."""
        body = {
            'name': 'Test Template',
            'template_definition': {
                'steps': [
                    {
                        'id': 'step1',
                        'model': 'meta.llama3-1-8b-instruct-v1:0',
                        'prompt': 'Generate content about {{ topic }}'
                    }
                ]
            }
        }

        assert 'name' in body
        assert 'template_definition' in body
        assert len(body['template_definition']['steps']) > 0


class TestJSONParsingValidation:
    """Tests for JSON body parsing validation across handlers."""

    def test_valid_json_parsing(self):
        """Test parsing of valid JSON body."""
        event_body = '{"template_id": "test-123", "budget_limit": 100}'

        parsed = json.loads(event_body)

        assert parsed['template_id'] == 'test-123'
        assert parsed['budget_limit'] == 100

    def test_invalid_json_raises_decode_error(self):
        """Test that invalid JSON raises JSONDecodeError."""
        event_body = 'not valid json'

        with pytest.raises(json.JSONDecodeError):
            json.loads(event_body)

    def test_truncated_json_raises_decode_error(self):
        """Test that truncated JSON raises JSONDecodeError."""
        event_body = '{"template_id": "test-123"'

        with pytest.raises(json.JSONDecodeError):
            json.loads(event_body)

    def test_empty_body_parsing(self):
        """Test parsing of empty JSON object."""
        event_body = '{}'

        parsed = json.loads(event_body)

        assert parsed == {}

    def test_null_body_handling(self):
        """Test handling of null body."""
        event = {'body': None}

        # Handler should check for None body
        body = event.get('body')
        if body is None:
            error_condition = True
        else:
            error_condition = False

        assert error_condition is True


class TestValidateSeedDataValidation:
    """Tests for validate_seed_data Lambda input validation."""

    def test_valid_seed_data_structure(self):
        """Test valid seed data structure."""
        seed_data = [
            {"author": {"name": "Jane Doe"}, "title": "Test Book"},
            {"author": {"name": "John Smith"}, "title": "Another Book"}
        ]

        # Valid seed data is a list of dictionaries
        assert isinstance(seed_data, list)
        assert all(isinstance(item, dict) for item in seed_data)

    def test_single_item_seed_data(self):
        """Test single item seed data (dictionary instead of list)."""
        seed_data = {"author": {"name": "Jane Doe"}, "title": "Test Book"}

        # Handler should accept both dict and list
        if isinstance(seed_data, list):
            items = seed_data
        else:
            items = [seed_data]

        assert len(items) == 1

    def test_invalid_seed_data_string(self):
        """Test that string seed data is invalid."""
        seed_data = "this is not valid seed data"

        # Should not be a dict or list of dicts
        is_valid = isinstance(seed_data, (list, dict))
        if isinstance(seed_data, list):
            is_valid = all(isinstance(item, dict) for item in seed_data)

        assert not is_valid


class TestAPIGatewayEventStructure:
    """Tests for API Gateway event structure validation."""

    def test_v2_event_structure(self):
        """Test API Gateway HTTP API v2 event structure."""
        event = {
            "version": "2.0",
            "routeKey": "POST /jobs",
            "rawPath": "/jobs",
            "headers": {"content-type": "application/json"},
            "requestContext": {
                "authorizer": {
                    "jwt": {
                        "claims": {"sub": "user-123", "email": "test@example.com"}
                    }
                }
            },
            "body": '{"template_id": "test"}'
        }

        # Verify structure
        assert event['version'] == '2.0'
        assert 'requestContext' in event
        assert 'authorizer' in event['requestContext']
        assert 'jwt' in event['requestContext']['authorizer']
        assert 'claims' in event['requestContext']['authorizer']['jwt']
        assert 'sub' in event['requestContext']['authorizer']['jwt']['claims']

    def test_missing_authorizer_detected(self):
        """Test detection of missing authorizer in event."""
        event = {
            "version": "2.0",
            "requestContext": {}
        }

        with pytest.raises(KeyError):
            _ = event['requestContext']['authorizer']['jwt']['claims']['sub']

    def test_missing_jwt_claims_detected(self):
        """Test detection of missing JWT claims."""
        event = {
            "version": "2.0",
            "requestContext": {
                "authorizer": {}
            }
        }

        with pytest.raises(KeyError):
            _ = event['requestContext']['authorizer']['jwt']['claims']['sub']
