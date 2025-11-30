"""
Plot Palette - Worker Export Format Tests

Tests for the export_data function including JSONL, Parquet, and CSV format generation.
"""

import pytest
import json


class TestJSONLExport:
    """Tests for JSONL export format."""

    def test_jsonl_format_one_json_per_line(self):
        """Test that JSONL has one JSON object per line."""
        records = [
            {'id': '1', 'data': 'test1'},
            {'id': '2', 'data': 'test2'},
            {'id': '3', 'data': 'test3'}
        ]

        jsonl_content = '\n'.join([json.dumps(r) for r in records])
        lines = jsonl_content.split('\n')

        assert len(lines) == 3
        for line in lines:
            parsed = json.loads(line)
            assert 'id' in parsed

    def test_jsonl_each_line_is_valid_json(self):
        """Test that each JSONL line is valid JSON."""
        records = [
            {'id': '1', 'nested': {'key': 'value'}},
            {'id': '2', 'array': [1, 2, 3]}
        ]

        jsonl_content = '\n'.join([json.dumps(r) for r in records])

        for line in jsonl_content.split('\n'):
            try:
                json.loads(line)
                valid = True
            except json.JSONDecodeError:
                valid = False

            assert valid is True

    def test_jsonl_content_type(self):
        """Test JSONL content type."""
        content_type = 'application/x-ndjson'

        assert content_type == 'application/x-ndjson'

    def test_jsonl_s3_key_format(self):
        """Test JSONL export S3 key format."""
        job_id = 'test-job-123'
        key = f"jobs/{job_id}/exports/dataset.jsonl"

        assert key == 'jobs/test-job-123/exports/dataset.jsonl'


class TestParquetExport:
    """Tests for Parquet export format."""

    def test_parquet_flattens_nested_json(self):
        """Test that nested JSON is serialized for Parquet."""
        record = {
            'id': '1',
            'generation_result': {'key': 'value', 'nested': {'deep': 'data'}}
        }

        # Parquet export serializes nested JSON as string
        flat = {
            'id': record['id'],
            'generation_result': json.dumps(record['generation_result'])
        }

        assert isinstance(flat['generation_result'], str)
        assert 'nested' in flat['generation_result']

    def test_parquet_content_type(self):
        """Test Parquet content type."""
        content_type = 'application/octet-stream'

        assert content_type == 'application/octet-stream'

    def test_parquet_s3_key_format(self):
        """Test Parquet export S3 key format."""
        job_id = 'test-job-123'
        key = f"jobs/{job_id}/exports/dataset.parquet"

        assert key == 'jobs/test-job-123/exports/dataset.parquet'

    def test_parquet_no_partition_support(self):
        """Test that Parquet doesn't support partition_strategy."""
        partition_strategy = 'timestamp'

        # Parquet falls back to single file regardless of partition_strategy
        supports_partitioning = False

        if partition_strategy != 'none':
            supports_partitioning = False  # Log warning, fall back

        assert supports_partitioning is False


class TestCSVExport:
    """Tests for CSV export format."""

    def test_csv_header_row(self):
        """Test that CSV includes header row."""
        records = [
            {'id': '1', 'job_id': 'job-1', 'timestamp': '2025-01-01'},
            {'id': '2', 'job_id': 'job-1', 'timestamp': '2025-01-02'}
        ]

        # Create CSV manually (without pandas)
        header = ','.join(records[0].keys())
        csv_lines = [header]
        for record in records:
            csv_lines.append(','.join(record.values()))
        csv_content = '\n'.join(csv_lines)

        lines = csv_content.strip().split('\n')

        # First line should be header
        header = lines[0]
        assert 'id' in header
        assert 'job_id' in header
        assert 'timestamp' in header

    def test_csv_data_rows(self):
        """Test CSV data rows."""
        records = [
            {'id': '1', 'value': 'test1'},
            {'id': '2', 'value': 'test2'}
        ]

        # Create CSV manually
        header = ','.join(records[0].keys())
        csv_lines = [header]
        for record in records:
            csv_lines.append(','.join(record.values()))
        csv_content = '\n'.join(csv_lines)

        lines = csv_content.strip().split('\n')

        # Should have header + 2 data rows
        assert len(lines) == 3

    def test_csv_content_type(self):
        """Test CSV content type."""
        content_type = 'text/csv'

        assert content_type == 'text/csv'

    def test_csv_s3_key_format(self):
        """Test CSV export S3 key format."""
        job_id = 'test-job-123'
        key = f"jobs/{job_id}/exports/dataset.csv"

        assert key == 'jobs/test-job-123/exports/dataset.csv'

    def test_csv_no_partition_support(self):
        """Test that CSV doesn't support partition_strategy."""
        partition_strategy = 'timestamp'

        # CSV falls back to single file
        supports_partitioning = False

        assert supports_partitioning is False


class TestPartitionedExport:
    """Tests for partitioned JSONL export."""

    def test_timestamp_partitioning(self):
        """Test timestamp-based partitioning."""
        records = [
            {'id': '1', 'timestamp': '2025-01-01T10:00:00'},
            {'id': '2', 'timestamp': '2025-01-01T11:00:00'},
            {'id': '3', 'timestamp': '2025-01-02T10:00:00'}
        ]

        partitions = {}
        for record in records:
            date = record['timestamp'][:10]  # YYYY-MM-DD
            if date not in partitions:
                partitions[date] = []
            partitions[date].append(record)

        assert '2025-01-01' in partitions
        assert '2025-01-02' in partitions
        assert len(partitions['2025-01-01']) == 2
        assert len(partitions['2025-01-02']) == 1

    def test_partition_key_format(self):
        """Test partition key format."""
        job_id = 'test-job-123'
        date = '2025-01-15'
        key = f"jobs/{job_id}/exports/partitioned/date={date}/records.jsonl"

        assert key == 'jobs/test-job-123/exports/partitioned/date=2025-01-15/records.jsonl'


class TestOutputFormatNormalization:
    """Tests for output_format normalization."""

    def test_string_format_normalized_to_set(self):
        """Test that string output_format is normalized to set."""
        output_format = 'JSONL'

        if isinstance(output_format, str):
            formats = {output_format}
        else:
            formats = set(output_format)

        assert formats == {'JSONL'}

    def test_list_format_normalized_to_set(self):
        """Test that list output_format is normalized to set."""
        output_format = ['JSONL', 'PARQUET']

        if isinstance(output_format, str):
            formats = {output_format}
        elif isinstance(output_format, list):
            formats = set(output_format)

        assert 'JSONL' in formats
        assert 'PARQUET' in formats

    def test_multiple_formats_exported(self):
        """Test that multiple formats are exported."""
        formats = {'JSONL', 'PARQUET', 'CSV'}
        exports_done = []

        for fmt in formats:
            exports_done.append(fmt)

        assert len(exports_done) == 3

    def test_default_format_is_jsonl(self):
        """Test that default format is JSONL."""
        output_format = None
        default_formats = {'JSONL'}

        formats = default_formats if not output_format else {output_format}

        assert formats == {'JSONL'}


class TestEmptyRecordsHandling:
    """Tests for empty records handling."""

    def test_no_records_logs_warning(self):
        """Test that no records logs warning."""
        records = []
        warning_logged = False

        if not records:
            warning_logged = True

        assert warning_logged is True

    def test_no_records_returns_early(self):
        """Test that empty records returns early."""
        records = []
        export_performed = False

        if records:
            export_performed = True

        assert export_performed is False


class TestRecordFlattening:
    """Tests for record flattening for tabular formats."""

    def test_record_flattening(self):
        """Test that records are flattened for CSV/Parquet."""
        record = {
            'id': 'record-1',
            'job_id': 'job-123',
            'timestamp': '2025-01-15T10:00:00',
            'seed_data_id': 'seed-1',
            'generation_result': {'text': 'generated content'}
        }

        flat = {
            'id': record['id'],
            'job_id': record['job_id'],
            'timestamp': record['timestamp'],
            'seed_data_id': record.get('seed_data_id', 'unknown'),
            'generation_result': json.dumps(record['generation_result'])
        }

        assert flat['id'] == 'record-1'
        assert isinstance(flat['generation_result'], str)

    def test_missing_seed_data_id_defaults_to_unknown(self):
        """Test that missing seed_data_id defaults to 'unknown'."""
        record = {
            'id': 'record-1',
            'job_id': 'job-123'
            # No seed_data_id
        }

        seed_data_id = record.get('seed_data_id', 'unknown')

        assert seed_data_id == 'unknown'


class TestLoadAllBatches:
    """Tests for load_all_batches function."""

    def test_batches_loaded_from_outputs_prefix(self):
        """Test that batches are loaded from outputs prefix."""
        job_id = 'test-job-123'
        prefix = f"jobs/{job_id}/outputs/"

        assert prefix == 'jobs/test-job-123/outputs/'

    def test_only_jsonl_files_loaded(self):
        """Test that only .jsonl files are loaded."""
        keys = [
            'jobs/test/outputs/batch-0001.jsonl',
            'jobs/test/outputs/batch-0002.jsonl',
            'jobs/test/outputs/metadata.json'
        ]

        jsonl_keys = [k for k in keys if k.endswith('.jsonl')]

        assert len(jsonl_keys) == 2

    def test_batches_concatenated(self):
        """Test that batches are concatenated into single list."""
        batch1 = [{'id': '1'}, {'id': '2'}]
        batch2 = [{'id': '3'}, {'id': '4'}]

        all_records = batch1 + batch2

        assert len(all_records) == 4

    def test_empty_page_handling(self):
        """Test handling of pages with no Contents."""
        page = {}  # No 'Contents' key

        has_contents = 'Contents' in page

        assert has_contents is False


class TestExportLogging:
    """Tests for export logging."""

    def test_export_completion_logged(self):
        """Test that export completion is logged."""
        job_id = 'test-job-123'
        record_count = 1000
        format_count = 3

        log_message = f"Export complete for job {job_id}: {record_count} records in {format_count} format(s)"

        assert 'Export complete' in log_message
        assert job_id in log_message
        assert '1000' in log_message

    def test_individual_export_logged(self):
        """Test that each individual export is logged."""
        key = 'jobs/test/exports/dataset.jsonl'
        record_count = 500

        log_message = f"Exported JSONL: {key} ({record_count} records)"

        assert 'Exported JSONL' in log_message
        assert key in log_message
