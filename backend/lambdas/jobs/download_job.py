"""
Plot Palette - Download Job Lambda Handler

GET /jobs/{job_id}/download endpoint that generates a presigned URL
for downloading completed job exports.
"""

import json
import os
import sys
from typing import Any, Dict

# Add shared library to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../shared"))

from botocore.exceptions import ClientError
from lambda_responses import error_response, success_response
from utils import sanitize_error_message, setup_logger

# Initialize logger
logger = setup_logger(__name__)

# Initialize AWS clients
from aws_clients import get_dynamodb_resource, get_s3_client

dynamodb = get_dynamodb_resource()
s3_client = get_s3_client()
jobs_table = dynamodb.Table(os.environ.get("JOBS_TABLE_NAME", "plot-palette-Jobs"))
bucket_name = os.environ.get("BUCKET_NAME", "plot-palette-data")

PRESIGNED_URL_EXPIRATION = 3600  # 1 hour


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for GET /jobs/{job_id}/download endpoint.

    Generates a presigned S3 URL for downloading the job's export file.
    Only allows download of COMPLETED jobs owned by the requesting user.
    """
    try:
        # Extract user ID from JWT claims
        user_id = event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]
        job_id = event["pathParameters"]["job_id"]

        logger.info(
            json.dumps(
                {
                    "event": "download_job_request",
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

        # Status check
        if job.get("status") != "COMPLETED":
            return error_response(400, "Job is not completed - cannot download")

        # Derive file extension from job config output_format
        output_format = job.get("config", {}).get("output_format", "JSONL").lower()
        ext_map = {"jsonl": "jsonl", "parquet": "parquet", "csv": "csv"}
        ext = ext_map.get(output_format, "jsonl")

        s3_key = f"jobs/{job_id}/exports/output.{ext}"
        filename = f"job-{job_id[:12]}-output.{ext}"

        # Verify the export file exists before generating presigned URL
        try:
            s3_client.head_object(Bucket=bucket_name, Key=s3_key)
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return error_response(404, "Export file not found - job may still be processing")
            logger.error(json.dumps({"event": "head_object_error", "error": str(e)}))
            return error_response(500, "Error checking export file")

        try:
            download_url = s3_client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": bucket_name,
                    "Key": s3_key,
                    "ResponseContentDisposition": f'attachment; filename="{filename}"',
                },
                ExpiresIn=PRESIGNED_URL_EXPIRATION,
            )
        except ClientError as e:
            logger.error(json.dumps({"event": "presigned_url_error", "error": str(e)}))
            return error_response(500, "Error generating download URL")

        return success_response(
            200,
            {
                "download_url": download_url,
                "filename": filename,
                "expires_in": PRESIGNED_URL_EXPIRATION,
            },
        )

    except KeyError as e:
        return error_response(400, f"Missing required field: {sanitize_error_message(str(e))}")

    except Exception as e:
        logger.error(json.dumps({"event": "unexpected_error", "error": str(e)}), exc_info=True)
        return error_response(500, "Internal server error")
