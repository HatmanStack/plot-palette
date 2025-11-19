"""
Plot Palette - Dashboard API Integration Tests

Tests for dashboard endpoint:
GET /dashboard/{job_id}
"""

import pytest
import requests
import json


class TestDashboardAPI:
    """Integration tests for Dashboard API endpoints."""

    def test_get_dashboard_stats_success(self, api_endpoint, auth_headers, sample_template_definition, sample_job_config):
        """Test successful retrieval of dashboard statistics."""
        # Create template
        template_response = requests.post(
            f"{api_endpoint}/templates",
            headers=auth_headers,
            json={
                "name": "Dashboard Test Template",
                "template_definition": sample_template_definition
            }
        )
        template_id = template_response.json()['template_id']

        # Create job
        job_config = sample_job_config.copy()
        job_config['template_id'] = template_id

        job_response = requests.post(
            f"{api_endpoint}/jobs",
            headers=auth_headers,
            json=job_config
        )
        job_id = job_response.json()['job_id']

        # Get dashboard stats
        response = requests.get(
            f"{api_endpoint}/dashboard/{job_id}",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert data['job_id'] == job_id
        assert 'status' in data
        assert 'progress' in data
        assert 'cost' in data
        assert 'budget' in data
        assert 'timing' in data

        # Verify progress structure
        assert 'records_generated' in data['progress']
        assert 'target_records' in data['progress']
        assert 'percentage' in data['progress']

        # Verify cost breakdown
        assert 'bedrock' in data['cost']
        assert 'fargate' in data['cost']
        assert 's3' in data['cost']
        assert 'total' in data['cost']

        # Verify budget tracking
        assert 'limit' in data['budget']
        assert 'used' in data['budget']
        assert 'remaining' in data['budget']
        assert 'percentage_used' in data['budget']

        # Verify timing information
        assert 'created_at' in data['timing']
        assert 'started_at' in data['timing']
        assert 'estimated_completion' in data['timing']

    def test_get_dashboard_stats_not_found(self, api_endpoint, auth_headers):
        """Test dashboard stats for non-existent job."""
        response = requests.get(
            f"{api_endpoint}/dashboard/nonexistent-job-id",
            headers=auth_headers
        )

        assert response.status_code == 404

    def test_get_dashboard_stats_progress_calculation(self, api_endpoint, auth_headers, sample_template_definition, sample_job_config):
        """Test progress percentage calculation."""
        # Create template
        template_response = requests.post(
            f"{api_endpoint}/templates",
            headers=auth_headers,
            json={
                "name": "Progress Test Template",
                "template_definition": sample_template_definition
            }
        )
        template_id = template_response.json()['template_id']

        # Create job with known target
        job_config = sample_job_config.copy()
        job_config['template_id'] = template_id
        job_config['num_records'] = 100

        job_response = requests.post(
            f"{api_endpoint}/jobs",
            headers=auth_headers,
            json=job_config
        )
        job_id = job_response.json()['job_id']

        # Get stats
        response = requests.get(
            f"{api_endpoint}/dashboard/{job_id}",
            headers=auth_headers
        )

        data = response.json()
        assert data['progress']['target_records'] == 100
        assert data['progress']['percentage'] >= 0
        assert data['progress']['percentage'] <= 100

    def test_get_dashboard_stats_budget_tracking(self, api_endpoint, auth_headers, sample_template_definition, sample_job_config):
        """Test budget tracking calculations."""
        # Create template
        template_response = requests.post(
            f"{api_endpoint}/templates",
            headers=auth_headers,
            json={
                "name": "Budget Test Template",
                "template_definition": sample_template_definition
            }
        )
        template_id = template_response.json()['template_id']

        # Create job with known budget
        job_config = sample_job_config.copy()
        job_config['template_id'] = template_id
        job_config['budget_limit'] = 50.0

        job_response = requests.post(
            f"{api_endpoint}/jobs",
            headers=auth_headers,
            json=job_config
        )
        job_id = job_response.json()['job_id']

        # Get stats
        response = requests.get(
            f"{api_endpoint}/dashboard/{job_id}",
            headers=auth_headers
        )

        data = response.json()
        assert data['budget']['limit'] == 50.0
        assert data['budget']['used'] >= 0
        assert data['budget']['remaining'] == data['budget']['limit'] - data['budget']['used']

    def test_unauthorized_dashboard_access(self, api_endpoint):
        """Test accessing dashboard without authentication."""
        response = requests.get(f"{api_endpoint}/dashboard/some-job-id")

        # Should be 401 or 403 depending on API Gateway config
        assert response.status_code in [401, 403]
