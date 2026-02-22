"""
Plot Palette - Download Partial Results Lambda Handler

GET /jobs/{job_id}/download-partial endpoint that concatenates available
batch JSONL files from S3 and returns a presigned download URL, allowing
users to download partial results from any job with generated records.
"""

import json
import os
import sys
import time
from io import BytesIO
from typing import Any

# Add shared library to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../shared"))

from botocore.exceptions import ClientError
from lambda_responses import error_response, success_response
from utils import extract_request_id, sanitize_error_message, set_correlation_id, setup_logger

# Initialize logger
logger = setup_logger(__name__)

# Initialize AWS clients
from aws_clients import get_dynamodb_resource, get_s3_client

dynamodb = get_dynamodb_resource()
s3_client = get_s3_client()
jobs_table = dynamodb.Table(os.environ.get("JOBS_TABLE_NAME", "plot-palette-Jobs"))
bucket_name = os.environ.get("BUCKET_NAME", "plot-palette-data")

PRESIGNED_URL_EXPIRATION = 3600  # 1 hour


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Lambda handler for GET /jobs/{job_id}/download-partial endpoint.

    Concatenates available JSONL batch files from S3 into a single file
    and returns a presigned URL for download. Works for any job status
    as long as records have been generated.
    """
    try:
        set_correlation_id(extract_request_id(event))

        # Extract user ID from JWT claims
        user_id = event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]
        job_id = event["pathParameters"]["job_id"]

        logger.info(
            json.dumps(
                {
                    "event": "download_partial_request",
                    "user_id": user_id,
                    "job_id": job_id,
                }
            )
        )

        # Get job from DynamoDB
        try:
            response = jobs_table.get_item(Key={"job_id": job_id})
        except ClientError as e:
            logger.error(json.dumps({"event": "get_item_error", "error": str(e)}))
            return error_response(500, "Error retrieving job")

        if "Item" not in response:
            return error_response(404, "Job not found")

        job = response["Item"]

        # Authorization check
        if job["user_id"] != user_id:
            return error_response(403, "Access denied - you do not own this job")

        # Check that records have been generated
        records_generated = job.get("records_generated", 0)
        if not records_generated or int(records_generated) <= 0:
            return error_response(400, "No records generated yet")

        records_generated = int(records_generated)

        # List all batch files under the job's outputs prefix
        prefix = f"jobs/{job_id}/outputs/"
        batch_files = []

        try:
            paginator = s3_client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=bucket_name, Prefix=prefix):
                for obj in page.get("Contents", []):
                    if obj["Key"].endswith(".jsonl"):
                        batch_files.append(obj["Key"])
        except ClientError as e:
            logger.error(json.dumps({"event": "s3_list_error", "error": str(e)}))
            return error_response(500, "Error listing batch files")

        if not batch_files:
            return error_response(404, "No batch files found")

        # Sort to ensure correct order (batch-0000.jsonl, batch-0001.jsonl, ...)
        batch_files.sort()

        # Concatenate batch files into a single partial export
        timestamp = int(time.time())
        partial_key = f"jobs/{job_id}/exports/partial-{timestamp}.jsonl"
        filename = f"job-{job_id[:12]}-partial.jsonl"

        try:
            mpu = s3_client.create_multipart_upload(Bucket=bucket_name, Key=partial_key)
            upload_id = mpu["UploadId"]

            # Read all batches into a combined buffer
            combined = BytesIO()
            for batch_key in batch_files:
                obj = s3_client.get_object(Bucket=bucket_name, Key=batch_key)
                data = obj["Body"].read()
                combined.write(data)
                if not data.endswith(b"\n"):
                    combined.write(b"\n")

            combined.seek(0)
            part = s3_client.upload_part(
                Bucket=bucket_name,
                Key=partial_key,
                UploadId=upload_id,
                PartNumber=1,
                Body=combined.read(),
            )

            s3_client.complete_multipart_upload(
                Bucket=bucket_name,
                Key=partial_key,
                UploadId=upload_id,
                MultipartUpload={"Parts": [{"PartNumber": 1, "ETag": part["ETag"]}]},
            )

        except ClientError as e:
            logger.error(json.dumps({"event": "s3_concat_error", "error": str(e)}))
            # Attempt to abort the multipart upload
            try:
                s3_client.abort_multipart_upload(
                    Bucket=bucket_name, Key=partial_key, UploadId=upload_id
                )
            except Exception:
                pass
            return error_response(500, "Error creating partial export file")

        # Generate presigned URL for the concatenated file
        try:
            download_url = s3_client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": bucket_name,
                    "Key": partial_key,
                    "ResponseContentDisposition": f'attachment; filename="{filename}"',
                },
                ExpiresIn=PRESIGNED_URL_EXPIRATION,
            )
        except ClientError as e:
            logger.error(json.dumps({"event": "presigned_url_error", "error": str(e)}))
            return error_response(500, "Error generating download URL")

        logger.info(
            json.dumps(
                {
                    "event": "download_partial_success",
                    "job_id": job_id,
                    "records_available": records_generated,
                    "batch_files": len(batch_files),
                }
            )
        )

        return success_response(
            200,
            {
                "download_url": download_url,
                "filename": filename,
                "records_available": records_generated,
                "format": "jsonl",
                "expires_in": PRESIGNED_URL_EXPIRATION,
            },
        )

    except KeyError as e:
        return error_response(400, f"Missing required field: {sanitize_error_message(str(e))}")

    except Exception as e:
        logger.error(json.dumps({"event": "unexpected_error", "error": str(e)}), exc_info=True)
        return error_response(500, "Internal server error")
