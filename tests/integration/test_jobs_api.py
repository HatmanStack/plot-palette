"""
Plot Palette - Jobs API Integration Tests

Tests for job management endpoints:
POST /jobs, GET /jobs, GET /jobs/{id}, DELETE /jobs/{id}
"""

import pytest
import requests
import json
import time


class TestJobsAPI:
    """Integration tests for Jobs API endpoints."""

    def test_create_job_success(self, api_endpoint, auth_headers, sample_job_config, sample_template_definition):
        """Test successful job creation."""
        # First create a template
        template_response = requests.post(
            f"{api_endpoint}/templates",
            headers=auth_headers,
            json={
                "name": "Test Template for Job",
                "template_definition": sample_template_definition
            }
        )
        assert template_response.status_code == 201
        template_id = template_response.json()['template_id']

        # Update job config with actual template ID
        job_config = sample_job_config.copy()
        job_config['template_id'] = template_id

        # Create job
        response = requests.post(
            f"{api_endpoint}/jobs",
            headers=auth_headers,
            json=job_config
        )

        assert response.status_code == 201
        data = response.json()
        assert 'job_id' in data
        assert data['status'] == 'QUEUED'
        assert 'created_at' in data

    def test_create_job_missing_fields(self, api_endpoint, auth_headers):
        """Test job creation with missing required fields."""
        response = requests.post(
            f"{api_endpoint}/jobs",
            headers=auth_headers,
            json={"budget_limit": 50.0}  # Missing other required fields
        )

        assert response.status_code == 400
        assert 'error' in response.json()

    def test_create_job_invalid_budget(self, api_endpoint, auth_headers, sample_job_config):
        """Test job creation with invalid budget limit."""
        job_config = sample_job_config.copy()
        job_config['budget_limit'] = -10.0

        response = requests.post(
            f"{api_endpoint}/jobs",
            headers=auth_headers,
            json=job_config
        )

        assert response.status_code == 400
        assert 'budget_limit' in response.json()['error'].lower()

    def test_create_job_template_not_found(self, api_endpoint, auth_headers, sample_job_config):
        """Test job creation with non-existent template."""
        job_config = sample_job_config.copy()
        job_config['template_id'] = 'nonexistent-template-id'

        response = requests.post(
            f"{api_endpoint}/jobs",
            headers=auth_headers,
            json=job_config
        )

        assert response.status_code == 404
        assert 'template' in response.json()['error'].lower()

    def test_list_jobs(self, api_endpoint, auth_headers):
        """Test listing user's jobs."""
        response = requests.get(
            f"{api_endpoint}/jobs",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert 'jobs' in data
        assert isinstance(data['jobs'], list)
        assert 'has_more' in data

    def test_list_jobs_with_pagination(self, api_endpoint, auth_headers):
        """Test listing jobs with pagination."""
        response = requests.get(
            f"{api_endpoint}/jobs?limit=5",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data['jobs']) <= 5

    def test_list_jobs_with_status_filter(self, api_endpoint, auth_headers):
        """Test listing jobs with status filter."""
        response = requests.get(
            f"{api_endpoint}/jobs?status=QUEUED",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        # All returned jobs should have QUEUED status
        for job in data['jobs']:
            assert job['status'] == 'QUEUED'

    def test_get_job_success(self, api_endpoint, auth_headers, sample_job_config, sample_template_definition):
        """Test getting specific job details."""
        # Create a template
        template_response = requests.post(
            f"{api_endpoint}/templates",
            headers=auth_headers,
            json={
                "name": "Test Template",
                "template_definition": sample_template_definition
            }
        )
        template_id = template_response.json()['template_id']

        # Create a job
        job_config = sample_job_config.copy()
        job_config['template_id'] = template_id

        create_response = requests.post(
            f"{api_endpoint}/jobs",
            headers=auth_headers,
            json=job_config
        )
        job_id = create_response.json()['job_id']

        # Get job details
        response = requests.get(
            f"{api_endpoint}/jobs/{job_id}",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data['job_id'] == job_id
        assert 'status' in data
        assert 'config' in data
        assert 'created_at' in data

    def test_get_job_not_found(self, api_endpoint, auth_headers):
        """Test getting non-existent job."""
        response = requests.get(
            f"{api_endpoint}/jobs/nonexistent-job-id",
            headers=auth_headers
        )

        assert response.status_code == 404

    def test_delete_queued_job(self, api_endpoint, auth_headers, sample_job_config, sample_template_definition):
        """Test deleting a QUEUED job."""
        # Create template
        template_response = requests.post(
            f"{api_endpoint}/templates",
            headers=auth_headers,
            json={
                "name": "Test Template",
                "template_definition": sample_template_definition
            }
        )
        template_id = template_response.json()['template_id']

        # Create job
        job_config = sample_job_config.copy()
        job_config['template_id'] = template_id

        create_response = requests.post(
            f"{api_endpoint}/jobs",
            headers=auth_headers,
            json=job_config
        )
        job_id = create_response.json()['job_id']

        # Delete job
        response = requests.delete(
            f"{api_endpoint}/jobs/{job_id}",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert 'cancelled' in response.json()['message'].lower()

        # Verify job is cancelled
        get_response = requests.get(
            f"{api_endpoint}/jobs/{job_id}",
            headers=auth_headers
        )
        assert get_response.json()['status'] == 'CANCELLED'

    def test_delete_job_not_found(self, api_endpoint, auth_headers):
        """Test deleting non-existent job."""
        response = requests.delete(
            f"{api_endpoint}/jobs/nonexistent-job-id",
            headers=auth_headers
        )

        assert response.status_code == 404

    def test_unauthorized_access(self, api_endpoint):
        """Test accessing jobs without authentication."""
        response = requests.get(f"{api_endpoint}/jobs")

        # Should be 401 or 403 depending on API Gateway config
        assert response.status_code in [401, 403]
