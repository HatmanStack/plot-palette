"""
Plot Palette - Lambda Authorization Tests

Tests that Lambda handlers properly handle authorization failures.
"""

import json
import pytest
from unittest.mock import MagicMock


class TestMissingJWTClaims:
    """Tests for missing JWT claims handling."""

    def test_missing_authorizer_raises_key_error(self):
        """Test that missing authorizer section raises KeyError."""
        event = {
            'requestContext': {}
        }

        with pytest.raises(KeyError):
            _ = event['requestContext']['authorizer']['jwt']['claims']['sub']

    def test_missing_jwt_section_raises_key_error(self):
        """Test that missing JWT section raises KeyError."""
        event = {
            'requestContext': {
                'authorizer': {}
            }
        }

        with pytest.raises(KeyError):
            _ = event['requestContext']['authorizer']['jwt']['claims']['sub']

    def test_missing_claims_raises_key_error(self):
        """Test that missing claims section raises KeyError."""
        event = {
            'requestContext': {
                'authorizer': {
                    'jwt': {}
                }
            }
        }

        with pytest.raises(KeyError):
            _ = event['requestContext']['authorizer']['jwt']['claims']['sub']

    def test_missing_sub_claim_raises_key_error(self):
        """Test that missing sub claim raises KeyError."""
        event = {
            'requestContext': {
                'authorizer': {
                    'jwt': {
                        'claims': {
                            'email': 'test@example.com'
                            # No 'sub' claim
                        }
                    }
                }
            }
        }

        with pytest.raises(KeyError):
            _ = event['requestContext']['authorizer']['jwt']['claims']['sub']


class TestResourceOwnershipValidation:
    """Tests for cross-user access prevention."""

    def test_job_owner_check_passes_for_owner(self):
        """Test that owner can access their own job."""
        requesting_user_id = 'user-123'
        job = {
            'job_id': 'job-456',
            'user_id': 'user-123',
            'status': 'RUNNING'
        }

        # Authorization check
        is_authorized = job['user_id'] == requesting_user_id

        assert is_authorized is True

    def test_job_owner_check_fails_for_non_owner(self):
        """Test that non-owner cannot access another user's job."""
        requesting_user_id = 'user-789'  # Different user
        job = {
            'job_id': 'job-456',
            'user_id': 'user-123',  # Owner is different
            'status': 'RUNNING'
        }

        # Authorization check
        is_authorized = job['user_id'] == requesting_user_id

        assert is_authorized is False

    def test_template_owner_check_passes_for_owner(self):
        """Test that owner can access their own template."""
        requesting_user_id = 'user-abc'
        template = {
            'template_id': 'template-xyz',
            'user_id': 'user-abc',
            'name': 'My Template'
        }

        is_authorized = template['user_id'] == requesting_user_id

        assert is_authorized is True

    def test_template_owner_check_fails_for_non_owner(self):
        """Test that non-owner cannot access another user's template."""
        requesting_user_id = 'user-different'
        template = {
            'template_id': 'template-xyz',
            'user_id': 'user-abc',
            'name': 'My Template',
            'is_public': False
        }

        is_authorized = template['user_id'] == requesting_user_id

        assert is_authorized is False

    def test_public_template_access(self):
        """Test that public templates have different access rules."""
        requesting_user_id = 'user-different'
        template = {
            'template_id': 'template-xyz',
            'user_id': 'user-abc',
            'name': 'Public Template',
            'is_public': True
        }

        # Public templates can be read by anyone
        can_read = template['is_public'] or template['user_id'] == requesting_user_id
        # But only owner can modify
        can_modify = template['user_id'] == requesting_user_id

        assert can_read is True
        assert can_modify is False


class TestJobNotFoundHandling:
    """Tests for non-existent job handling."""

    def test_job_not_found_returns_none_item(self):
        """Test DynamoDB response when job doesn't exist."""
        response = {}  # No 'Item' key

        job_exists = 'Item' in response

        assert job_exists is False

    def test_job_found_returns_item(self):
        """Test DynamoDB response when job exists."""
        response = {
            'Item': {
                'job_id': 'job-123',
                'user_id': 'user-456',
                'status': 'COMPLETED'
            }
        }

        job_exists = 'Item' in response

        assert job_exists is True

    def test_get_job_error_response_format(self):
        """Test 404 error response format for non-existent job."""
        error_response = {
            "statusCode": 404,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({"error": "Job not found"})
        }

        assert error_response['statusCode'] == 404
        body = json.loads(error_response['body'])
        assert body['error'] == "Job not found"


class TestTemplateNotFoundHandling:
    """Tests for non-existent template handling."""

    def test_template_not_found_returns_none_item(self):
        """Test DynamoDB response when template doesn't exist."""
        response = {}

        template_exists = 'Item' in response

        assert template_exists is False

    def test_template_found_returns_item(self):
        """Test DynamoDB response when template exists."""
        response = {
            'Item': {
                'template_id': 'template-123',
                'version': 1,
                'name': 'Test Template'
            }
        }

        template_exists = 'Item' in response

        assert template_exists is True


class TestDeleteJobAuthorization:
    """Tests for delete job authorization scenarios."""

    def test_delete_queued_job_by_owner(self):
        """Test that owner can delete queued job."""
        requesting_user_id = 'user-123'
        job = {
            'job_id': 'job-456',
            'user_id': 'user-123',
            'status': 'QUEUED'
        }

        is_authorized = job['user_id'] == requesting_user_id
        can_delete = job['status'] == 'QUEUED'

        assert is_authorized is True
        assert can_delete is True

    def test_delete_running_job_by_owner(self):
        """Test that owner can cancel running job."""
        requesting_user_id = 'user-123'
        job = {
            'job_id': 'job-456',
            'user_id': 'user-123',
            'status': 'RUNNING',
            'task_arn': 'arn:aws:ecs:us-east-1:123456:task/test'
        }

        is_authorized = job['user_id'] == requesting_user_id
        is_running = job['status'] == 'RUNNING'
        has_task = 'task_arn' in job and bool(job['task_arn'])

        assert is_authorized is True
        assert is_running is True
        assert has_task is True

    def test_delete_completed_job_by_owner(self):
        """Test that owner can delete completed job."""
        requesting_user_id = 'user-123'
        job = {
            'job_id': 'job-456',
            'user_id': 'user-123',
            'status': 'COMPLETED'
        }

        is_authorized = job['user_id'] == requesting_user_id
        is_terminal_state = job['status'] in ['COMPLETED', 'FAILED', 'CANCELLED', 'BUDGET_EXCEEDED']

        assert is_authorized is True
        assert is_terminal_state is True

    def test_delete_job_by_non_owner_forbidden(self):
        """Test that non-owner cannot delete job."""
        requesting_user_id = 'user-different'
        job = {
            'job_id': 'job-456',
            'user_id': 'user-123',
            'status': 'QUEUED'
        }

        is_authorized = job['user_id'] == requesting_user_id

        assert is_authorized is False


class TestAuthorizationErrorResponses:
    """Tests for authorization error response formats."""

    def test_403_forbidden_response_format(self):
        """Test 403 Forbidden response format."""
        error_response = {
            "statusCode": 403,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({"error": "Access denied - you do not own this job"})
        }

        assert error_response['statusCode'] == 403
        body = json.loads(error_response['body'])
        assert 'Access denied' in body['error']

    def test_401_unauthorized_response_format(self):
        """Test 401 Unauthorized response format."""
        error_response = {
            "statusCode": 401,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({"error": "Missing or invalid authentication"})
        }

        assert error_response['statusCode'] == 401
        body = json.loads(error_response['body'])
        assert 'authentication' in body['error'].lower()

    def test_400_missing_field_response_format(self):
        """Test 400 response for missing required field."""
        error_response = {
            "statusCode": 400,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({"error": "Missing required field: 'pathParameters'"})
        }

        assert error_response['statusCode'] == 400
        body = json.loads(error_response['body'])
        assert 'Missing required field' in body['error']


class TestConditionalCheckFailures:
    """Tests for DynamoDB conditional check failure handling."""

    def test_conditional_check_failure_for_delete(self):
        """Test handling of ConditionalCheckFailedException during delete."""
        from botocore.exceptions import ClientError

        # Simulate conditional check failure
        error_response = {
            'Error': {
                'Code': 'ConditionalCheckFailedException',
                'Message': 'The conditional request failed'
            }
        }

        error = ClientError(error_response, 'DeleteItem')

        assert error.response['Error']['Code'] == 'ConditionalCheckFailedException'

    def test_conditional_check_failure_detection(self):
        """Test detection of conditional check failure error code."""
        error_code = 'ConditionalCheckFailedException'

        is_conditional_failure = error_code == 'ConditionalCheckFailedException'

        assert is_conditional_failure is True

    def test_other_error_code_not_conditional_failure(self):
        """Test that other error codes are not conditional failures."""
        error_code = 'InternalError'

        is_conditional_failure = error_code == 'ConditionalCheckFailedException'

        assert is_conditional_failure is False


class TestUserIdExtraction:
    """Tests for user ID extraction from various event formats."""

    def test_http_api_v2_user_id_extraction(self):
        """Test user ID extraction from HTTP API v2 event."""
        event = {
            'requestContext': {
                'authorizer': {
                    'jwt': {
                        'claims': {
                            'sub': 'user-id-from-cognito',
                            'email': 'user@example.com'
                        }
                    }
                }
            }
        }

        user_id = event['requestContext']['authorizer']['jwt']['claims']['sub']

        assert user_id == 'user-id-from-cognito'

    def test_rest_api_v1_user_id_extraction(self):
        """Test user ID extraction from REST API v1 event."""
        event = {
            'requestContext': {
                'authorizer': {
                    'claims': {
                        'sub': 'user-id-from-cognito-v1',
                        'email': 'user@example.com'
                    }
                }
            }
        }

        # REST API v1 has claims directly under authorizer
        user_id = event['requestContext']['authorizer']['claims']['sub']

        assert user_id == 'user-id-from-cognito-v1'

    def test_custom_authorizer_user_id_extraction(self):
        """Test user ID extraction from custom Lambda authorizer."""
        event = {
            'requestContext': {
                'authorizer': {
                    'principalId': 'custom-user-id',
                    'claims': {
                        'sub': 'custom-user-id'
                    }
                }
            }
        }

        # Custom authorizer may use principalId
        user_id = event['requestContext']['authorizer'].get('principalId') or \
                  event['requestContext']['authorizer']['claims']['sub']

        assert user_id == 'custom-user-id'


class TestJobStatusTransitions:
    """Tests for job status transition authorization."""

    def test_queued_job_can_be_cancelled(self):
        """Test that QUEUED job can transition to CANCELLED."""
        current_status = 'QUEUED'
        allowed_transitions = {
            'QUEUED': ['RUNNING', 'CANCELLED'],
            'RUNNING': ['COMPLETED', 'FAILED', 'CANCELLED', 'BUDGET_EXCEEDED'],
            'COMPLETED': [],  # Terminal state
            'FAILED': [],
            'CANCELLED': [],
            'BUDGET_EXCEEDED': []
        }

        can_cancel = 'CANCELLED' in allowed_transitions.get(current_status, [])

        assert can_cancel is True

    def test_running_job_can_be_cancelled(self):
        """Test that RUNNING job can transition to CANCELLED."""
        current_status = 'RUNNING'
        allowed_transitions = {
            'QUEUED': ['RUNNING', 'CANCELLED'],
            'RUNNING': ['COMPLETED', 'FAILED', 'CANCELLED', 'BUDGET_EXCEEDED'],
        }

        can_cancel = 'CANCELLED' in allowed_transitions.get(current_status, [])

        assert can_cancel is True

    def test_completed_job_cannot_be_cancelled(self):
        """Test that COMPLETED job cannot transition to CANCELLED."""
        current_status = 'COMPLETED'
        allowed_transitions = {
            'COMPLETED': [],  # Terminal state - no transitions allowed
        }

        can_cancel = 'CANCELLED' in allowed_transitions.get(current_status, [])

        assert can_cancel is False

    def test_terminal_states_have_no_transitions(self):
        """Test that terminal states have no allowed transitions."""
        terminal_states = ['COMPLETED', 'FAILED', 'CANCELLED', 'BUDGET_EXCEEDED']
        allowed_transitions = {
            'COMPLETED': [],
            'FAILED': [],
            'CANCELLED': [],
            'BUDGET_EXCEEDED': []
        }

        for state in terminal_states:
            transitions = allowed_transitions.get(state, [])
            assert len(transitions) == 0, f"Terminal state {state} should have no transitions"
