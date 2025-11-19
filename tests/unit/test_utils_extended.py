"""
Extended unit tests for backend utility functions.

Additional coverage for edge cases and error handling.
"""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock

from backend.shared.utils import (
    generate_job_id,
    generate_template_id,
    get_nested_field,
    set_nested_field,
    parse_etag,
    resolve_model_id,
    validate_seed_data,
    format_cost,
    format_timestamp,
    parse_timestamp,
)
from backend.shared.constants import MODEL_TIERS


class TestNestedFieldOperations:
    """Test nested dictionary field operations."""

    def test_get_nested_field_deep_nesting(self):
        """Test getting deeply nested fields."""
        data = {
            "level1": {
                "level2": {
                    "level3": {
                        "level4": "deep value"
                    }
                }
            }
        }

        assert get_nested_field(data, "level1.level2.level3.level4") == "deep value"

    def test_get_nested_field_with_none_values(self):
        """Test getting field when intermediate value is None."""
        data = {
            "author": None
        }

        assert get_nested_field(data, "author.name") is None

    def test_set_nested_field_creates_missing_dicts(self):
        """Test that set_nested_field creates missing intermediate dicts."""
        data = {}
        set_nested_field(data, "author.details.name", "Jane Doe")

        assert data["author"]["details"]["name"] == "Jane Doe"

    def test_set_nested_field_single_level(self):
        """Test setting top-level field."""
        data = {}
        set_nested_field(data, "simple", "value")

        assert data["simple"] == "value"

    def test_set_nested_field_overwrites_existing(self):
        """Test that setting field overwrites existing value."""
        data = {"author": {"name": "Old Name"}}
        set_nested_field(data, "author.name", "New Name")

        assert data["author"]["name"] == "New Name"


class TestETagParsing:
    """Test ETag parsing."""

    def test_parse_etag_with_quotes(self):
        """Test parsing ETag with double quotes."""
        assert parse_etag('"abc123"') == "abc123"
        assert parse_etag('"def456"') == "def456"

    def test_parse_etag_without_quotes(self):
        """Test parsing ETag without quotes."""
        assert parse_etag('abc123') == "abc123"
        assert parse_etag('xyz789') == "xyz789"

    def test_parse_etag_empty_string(self):
        """Test parsing empty ETag."""
        assert parse_etag('""') == ""
        assert parse_etag('') == ""


class TestModelResolution:
    """Test model ID resolution."""

    def test_resolve_all_tier_aliases(self):
        """Test resolving all tier aliases."""
        tier_aliases = {
            "tier-1": MODEL_TIERS["tier-1"],
            "tier-2": MODEL_TIERS["tier-2"],
            "tier-3": MODEL_TIERS["tier-3"],
            "cheap": MODEL_TIERS["cheap"],
            "balanced": MODEL_TIERS["balanced"],
            "premium": MODEL_TIERS["premium"]
        }

        for alias, expected_model in tier_aliases.items():
            assert resolve_model_id(alias) == expected_model

    def test_resolve_direct_model_id(self):
        """Test that direct model IDs pass through."""
        model_ids = [
            "anthropic.claude-3-5-sonnet-20241022-v2:0",
            "meta.llama3-1-8b-instruct-v1:0",
            "meta.llama3-1-70b-instruct-v1:0",
            "mistral.mistral-7b-instruct-v0:2"
        ]

        for model_id in model_ids:
            assert resolve_model_id(model_id) == model_id


class TestSeedDataValidation:
    """Test seed data validation."""

    def test_validate_empty_requirements(self):
        """Test validation with no required fields."""
        data = {"any": "data"}
        is_valid, error = validate_seed_data(data, [])

        assert is_valid is True
        assert error is None

    def test_validate_multiple_missing_fields(self):
        """Test validation reports first missing field."""
        data = {"author": {"name": "Jane"}}
        is_valid, error = validate_seed_data(
            data,
            ["author.name", "author.bio", "poem.text"]
        )

        assert is_valid is False
        # Should report a missing field
        assert "Missing required field" in error

    def test_validate_nested_empty_dict(self):
        """Test validation with empty nested dict."""
        data = {"author": {}}
        is_valid, error = validate_seed_data(data, ["author.name"])

        assert is_valid is False
        assert "Missing required field: author.name" in error


class TestFormatting:
    """Test formatting functions."""

    def test_format_cost_edge_cases(self):
        """Test cost formatting edge cases."""
        assert format_cost(0) == "$0.00"
        assert format_cost(0.001) == "$0.00"  # Rounds to 0
        assert format_cost(0.005) == "$0.01"  # Rounds up
        assert format_cost(999.999) == "$1000.00"

    def test_format_timestamp_microseconds(self):
        """Test timestamp formatting."""
        dt = datetime(2025, 11, 19, 10, 30, 45)
        formatted = format_timestamp(dt)

        # Should be in ISO format
        assert "2025-11-19" in formatted
        assert "10:30:45" in formatted

    def test_parse_timestamp_invalid_format(self):
        """Test parsing invalid timestamp raises error."""
        with pytest.raises(ValueError):
            parse_timestamp("invalid-timestamp")


class TestUUIDGeneration:
    """Test UUID generation functions."""

    def test_job_id_uniqueness(self):
        """Test that generated job IDs are unique."""
        ids = [generate_job_id() for _ in range(100)]

        # All IDs should be unique
        assert len(ids) == len(set(ids))

    def test_template_id_uniqueness(self):
        """Test that generated template IDs are unique."""
        ids = [generate_template_id() for _ in range(100)]

        # All IDs should be unique
        assert len(ids) == len(set(ids))

    def test_job_id_format(self):
        """Test job ID format is valid UUID."""
        job_id = generate_job_id()

        # Should be UUID4 format with dashes
        assert len(job_id) == 36
        assert job_id.count('-') == 4

        # Should be parseable as UUID
        import uuid
        uuid.UUID(job_id)  # Should not raise


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
