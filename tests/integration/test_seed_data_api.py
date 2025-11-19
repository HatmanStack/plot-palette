"""
Plot Palette - Seed Data API Integration Tests

Tests for seed data endpoints:
POST /seed-data/upload, POST /seed-data/validate
"""

import pytest
import requests
import json


class TestSeedDataAPI:
    """Integration tests for Seed Data API endpoints."""

    def test_generate_upload_url_success(self, api_endpoint, auth_headers):
        """Test successful presigned URL generation."""
        response = requests.post(
            f"{api_endpoint}/seed-data/upload",
            headers=auth_headers,
            json={
                "filename": "test-seed-data.json",
                "content_type": "application/json"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert 'upload_url' in data
        assert 'https://' in data['upload_url']
        assert 's3_key' in data
        assert 'expires_in' in data
        assert data['expires_in'] == 900  # 15 minutes

    def test_generate_upload_url_missing_filename(self, api_endpoint, auth_headers):
        """Test presigned URL generation without filename."""
        response = requests.post(
            f"{api_endpoint}/seed-data/upload",
            headers=auth_headers,
            json={"content_type": "application/json"}
        )

        assert response.status_code == 400
        assert 'filename' in response.json()['error'].lower()

    def test_upload_file_using_presigned_url(self, api_endpoint, auth_headers, sample_seed_data, s3_client):
        """Test actual file upload using presigned URL."""
        # Generate presigned URL
        upload_response = requests.post(
            f"{api_endpoint}/seed-data/upload",
            headers=auth_headers,
            json={
                "filename": "integration-test.json",
                "content_type": "application/json"
            }
        )

        assert upload_response.status_code == 200
        upload_url = upload_response.json()['upload_url']
        s3_key = upload_response.json()['s3_key']
        bucket = upload_response.json()['bucket']

        # Upload file to presigned URL
        upload_result = requests.put(
            upload_url,
            headers={'Content-Type': 'application/json'},
            data=json.dumps(sample_seed_data)
        )

        assert upload_result.status_code == 200

        # Verify file exists in S3
        try:
            s3_client.head_object(Bucket=bucket, Key=s3_key)
        except:
            pytest.fail("File was not uploaded to S3")

        # Cleanup
        try:
            s3_client.delete_object(Bucket=bucket, Key=s3_key)
        except:
            pass

    def test_validate_seed_data_success(self, api_endpoint, auth_headers, sample_template_definition, sample_seed_data, s3_client):
        """Test successful seed data validation."""
        # Create template
        template_response = requests.post(
            f"{api_endpoint}/templates",
            headers=auth_headers,
            json={
                "name": "Validation Test Template",
                "template_definition": sample_template_definition
            }
        )
        template_id = template_response.json()['template_id']

        # Upload seed data
        upload_response = requests.post(
            f"{api_endpoint}/seed-data/upload",
            headers=auth_headers,
            json={
                "filename": "validation-test.json",
                "content_type": "application/json"
            }
        )
        upload_url = upload_response.json()['upload_url']
        s3_key = upload_response.json()['s3_key']
        bucket = upload_response.json()['bucket']

        requests.put(
            upload_url,
            headers={'Content-Type': 'application/json'},
            data=json.dumps(sample_seed_data)
        )

        # Validate seed data
        response = requests.post(
            f"{api_endpoint}/seed-data/validate",
            headers=auth_headers,
            json={
                "s3_key": s3_key,
                "template_id": template_id
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data['valid'] is True

        # Cleanup
        try:
            s3_client.delete_object(Bucket=bucket, Key=s3_key)
        except:
            pass

    def test_validate_seed_data_missing_fields(self, api_endpoint, auth_headers, sample_template_definition, s3_client):
        """Test seed data validation with missing required fields."""
        # Create template
        template_response = requests.post(
            f"{api_endpoint}/templates",
            headers=auth_headers,
            json={
                "name": "Validation Test",
                "template_definition": sample_template_definition
            }
        )
        template_id = template_response.json()['template_id']

        # Upload incomplete seed data (missing 'poem')
        upload_response = requests.post(
            f"{api_endpoint}/seed-data/upload",
            headers=auth_headers,
            json={"filename": "incomplete.json"}
        )
        upload_url = upload_response.json()['upload_url']
        s3_key = upload_response.json()['s3_key']
        bucket = upload_response.json()['bucket']

        incomplete_data = {"author": {"name": "Test Author"}}  # Missing poem

        requests.put(
            upload_url,
            headers={'Content-Type': 'application/json'},
            data=json.dumps(incomplete_data)
        )

        # Validate
        response = requests.post(
            f"{api_endpoint}/seed-data/validate",
            headers=auth_headers,
            json={
                "s3_key": s3_key,
                "template_id": template_id
            }
        )

        assert response.status_code == 400
        data = response.json()
        assert data['valid'] is False
        assert 'error' in data

        # Cleanup
        try:
            s3_client.delete_object(Bucket=bucket, Key=s3_key)
        except:
            pass

    def test_validate_seed_data_template_not_found(self, api_endpoint, auth_headers):
        """Test validation with non-existent template."""
        response = requests.post(
            f"{api_endpoint}/seed-data/validate",
            headers=auth_headers,
            json={
                "s3_key": "seed-data/test/file.json",
                "template_id": "nonexistent-template"
            }
        )

        assert response.status_code == 404

    def test_validate_seed_data_file_not_found(self, api_endpoint, auth_headers, sample_template_definition):
        """Test validation with non-existent S3 file."""
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

        # Validate non-existent file
        response = requests.post(
            f"{api_endpoint}/seed-data/validate",
            headers=auth_headers,
            json={
                "s3_key": "seed-data/nonexistent/file.json",
                "template_id": template_id
            }
        )

        assert response.status_code == 404
