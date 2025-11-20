"""
Plot Palette - Templates API Integration Tests

Tests for template management endpoints:
POST /templates, GET /templates, GET /templates/{id}, PUT /templates/{id}, DELETE /templates/{id}
"""

import pytest
import requests
import json


class TestTemplatesAPI:
    """Integration tests for Templates API endpoints."""

    def test_create_template_success(self, api_endpoint, auth_headers, sample_template_definition):
        """Test successful template creation."""
        response = requests.post(
            f"{api_endpoint}/templates",
            headers=auth_headers,
            json={
                "name": "Creative Writing Generator",
                "template_definition": sample_template_definition,
                "description": "Generates creative writing content"
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert 'template_id' in data
        assert data['version'] == 1
        assert 'schema_requirements' in data
        # Should detect 'author' and 'poem' from template
        assert any('author' in req for req in data['schema_requirements'])

    def test_create_template_invalid_jinja2(self, api_endpoint, auth_headers):
        """Test template creation with invalid Jinja2 syntax."""
        invalid_template = {
            "steps": [
                {
                    "id": "test",
                    "model": "llama-3.1-8b",
                    "prompt": "Generate {{ unclosed variable"  # Invalid syntax
                }
            ]
        }

        response = requests.post(
            f"{api_endpoint}/templates",
            headers=auth_headers,
            json={
                "name": "Invalid Template",
                "template_definition": invalid_template
            }
        )

        assert response.status_code == 400
        assert 'syntax' in response.json()['error'].lower()

    def test_create_template_missing_fields(self, api_endpoint, auth_headers):
        """Test template creation with missing required fields."""
        response = requests.post(
            f"{api_endpoint}/templates",
            headers=auth_headers,
            json={"name": "Incomplete Template"}  # Missing template_definition
        )

        assert response.status_code == 400

    def test_list_templates(self, api_endpoint, auth_headers):
        """Test listing user's templates."""
        response = requests.get(
            f"{api_endpoint}/templates",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert 'templates' in data
        assert isinstance(data['templates'], list)
        assert 'count' in data

    def test_list_templates_exclude_public(self, api_endpoint, auth_headers):
        """Test listing only user's templates (excluding public)."""
        response = requests.get(
            f"{api_endpoint}/templates?include_public=false",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        # All templates should be owned by user
        for template in data['templates']:
            assert template['is_owner'] is True

    def test_get_template_success(self, api_endpoint, auth_headers, sample_template_definition):
        """Test getting specific template details."""
        # Create template
        create_response = requests.post(
            f"{api_endpoint}/templates",
            headers=auth_headers,
            json={
                "name": "Test Template",
                "template_definition": sample_template_definition
            }
        )
        template_id = create_response.json()['template_id']

        # Get template
        response = requests.get(
            f"{api_endpoint}/templates/{template_id}",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data['template_id'] == template_id
        assert 'template_definition' in data
        assert data['is_owner'] is True

    def test_get_template_specific_version(self, api_endpoint, auth_headers, sample_template_definition):
        """Test getting specific version of template."""
        # Create template
        create_response = requests.post(
            f"{api_endpoint}/templates",
            headers=auth_headers,
            json={
                "name": "Versioned Template",
                "template_definition": sample_template_definition
            }
        )
        template_id = create_response.json()['template_id']

        # Get version 1
        response = requests.get(
            f"{api_endpoint}/templates/{template_id}?version=1",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert response.json()['version'] == 1

    def test_get_template_not_found(self, api_endpoint, auth_headers):
        """Test getting non-existent template."""
        response = requests.get(
            f"{api_endpoint}/templates/nonexistent-template-id",
            headers=auth_headers
        )

        assert response.status_code == 404

    def test_update_template_creates_new_version(self, api_endpoint, auth_headers, sample_template_definition):
        """Test updating template creates new version."""
        # Create template
        create_response = requests.post(
            f"{api_endpoint}/templates",
            headers=auth_headers,
            json={
                "name": "Original Template",
                "template_definition": sample_template_definition
            }
        )
        template_id = create_response.json()['template_id']

        # Update template
        updated_definition = sample_template_definition.copy()
        updated_definition['steps'][0]['prompt'] = "Updated prompt: {{ author.name }}"

        response = requests.put(
            f"{api_endpoint}/templates/{template_id}",
            headers=auth_headers,
            json={
                "name": "Updated Template",
                "template_definition": updated_definition
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data['version'] == 2
        assert data['previous_version'] == 1

    def test_update_template_not_found(self, api_endpoint, auth_headers, sample_template_definition):
        """Test updating non-existent template."""
        response = requests.put(
            f"{api_endpoint}/templates/nonexistent-template-id",
            headers=auth_headers,
            json={
                "name": "Updated",
                "template_definition": sample_template_definition
            }
        )

        assert response.status_code == 404

    def test_delete_template_success(self, api_endpoint, auth_headers, sample_template_definition):
        """Test deleting template that is not in use."""
        # Create template
        create_response = requests.post(
            f"{api_endpoint}/templates",
            headers=auth_headers,
            json={
                "name": "Temporary Template",
                "template_definition": sample_template_definition
            }
        )
        template_id = create_response.json()['template_id']

        # Delete template
        response = requests.delete(
            f"{api_endpoint}/templates/{template_id}",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert 'deleted' in response.json()['message'].lower()

        # Verify template is deleted
        get_response = requests.get(
            f"{api_endpoint}/templates/{template_id}",
            headers=auth_headers
        )
        assert get_response.status_code == 404

    def test_delete_template_in_use(self, api_endpoint, auth_headers, sample_template_definition, sample_job_config):
        """Test deleting template that is in use by jobs."""
        # Create template
        create_response = requests.post(
            f"{api_endpoint}/templates",
            headers=auth_headers,
            json={
                "name": "In-Use Template",
                "template_definition": sample_template_definition
            }
        )
        template_id = create_response.json()['template_id']

        # Create job using this template
        job_config = sample_job_config.copy()
        job_config['template_id'] = template_id

        requests.post(
            f"{api_endpoint}/jobs",
            headers=auth_headers,
            json=job_config
        )

        # Try to delete template
        response = requests.delete(
            f"{api_endpoint}/templates/{template_id}",
            headers=auth_headers
        )

        assert response.status_code == 409  # Conflict
        assert 'use' in response.json()['error'].lower()

    def test_delete_template_not_found(self, api_endpoint, auth_headers):
        """Test deleting non-existent template."""
        response = requests.delete(
            f"{api_endpoint}/templates/nonexistent-template-id",
            headers=auth_headers
        )

        assert response.status_code == 404
