"""
Plot Palette - Send Notification Lambda Handler

Triggered by Step Functions after terminal job states (COMPLETED, FAILED,
BUDGET_EXCEEDED). Sends email via SES and/or webhook POST based on user
notification preferences.
"""

import json
import os
import sys
from typing import Any

# Add shared library to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../shared"))

from botocore.exceptions import ClientError
from utils import setup_logger

# Initialize logger
logger = setup_logger(__name__)

# Initialize AWS clients
from aws_clients import get_dynamodb_resource, get_ses_client

dynamodb = get_dynamodb_resource()
prefs_table = dynamodb.Table(
    os.environ.get("NOTIFICATION_PREFERENCES_TABLE_NAME", "plot-palette-NotificationPreferences")
)
jobs_table = dynamodb.Table(os.environ.get("JOBS_TABLE_NAME", "plot-palette-Jobs"))
ses_client = get_ses_client()

SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "noreply@plotpalette.example.com")

STATUS_TO_PREF = {
    "COMPLETED": "notify_on_complete",
    "FAILED": "notify_on_failure",
    "BUDGET_EXCEEDED": "notify_on_budget_exceeded",
}


def _build_email_body(job: dict[str, Any], status: str) -> str:
    """Build email body with job summary."""
    records = job.get("records_generated", 0)
    cost = job.get("cost_estimate", 0)
    if hasattr(cost, "__float__"):
        cost = float(cost)
    job_id = job.get("job_id", "unknown")

    status_messages = {
        "COMPLETED": f"Your job {job_id} has completed successfully.",
        "FAILED": f"Your job {job_id} has failed.",
        "BUDGET_EXCEEDED": f"Your job {job_id} was stopped because the budget limit was exceeded.",
    }

    message = status_messages.get(status, f"Your job {job_id} has reached status: {status}.")

    return (
        f"{message}\n\n"
        f"Records generated: {records}\n"
        f"Cost: ${cost:.2f}\n"
        f"Status: {status}\n"
    )


def _send_email(email_address: str, job: dict[str, Any], status: str) -> None:
    """Send email notification via SES."""
    subject = f"Plot Palette - Job {status.replace('_', ' ').title()}"
    body = _build_email_body(job, status)

    try:
        ses_client.send_email(
            Source=SENDER_EMAIL,
            Destination={"ToAddresses": [email_address]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {"Text": {"Data": body, "Charset": "UTF-8"}},
            },
        )
        logger.info(json.dumps({
            "event": "email_sent",
            "to": email_address,
            "status": status,
        }))
    except ClientError as e:
        logger.error(json.dumps({
            "event": "email_send_error",
            "to": email_address,
            "error": str(e),
        }))


def _send_webhook(webhook_url: str, job: dict[str, Any], status: str, job_id: str) -> None:
    """Send webhook notification via HTTP POST."""
    import urllib.error
    import urllib.request

    payload = {
        "job_id": job_id,
        "status": status,
        "records_generated": int(job.get("records_generated", 0)),
        "cost_estimate": float(job.get("cost_estimate", 0)),
        "template_id": job.get("config", {}).get("template_id", ""),
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            logger.info(json.dumps({
                "event": "webhook_sent",
                "url": webhook_url,
                "status_code": resp.status,
            }))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        logger.error(json.dumps({
            "event": "webhook_send_error",
            "url": webhook_url,
            "error": str(e),
        }))


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Lambda handler for sending notifications on job terminal states.

    Input (from Step Functions):
        { "job_id": str, "status": str, "user_id": str }

    Always returns success to avoid failing the state machine.
    """
    try:
        job_id = event.get("job_id", "")
        status = event.get("status", "")
        user_id = event.get("user_id", "")

        if not job_id or not status or not user_id:
            logger.warning(json.dumps({
                "event": "missing_input_fields",
                "job_id": job_id,
                "status": status,
                "user_id": user_id,
            }))
            return {"statusCode": 200, "body": "Missing input fields, skipping notification"}

        logger.info(json.dumps({
            "event": "send_notification_request",
            "job_id": job_id,
            "status": status,
            "user_id": user_id,
        }))

        # Fetch notification preferences
        prefs_response = prefs_table.get_item(Key={"user_id": user_id})
        if "Item" not in prefs_response:
            logger.info(json.dumps({
                "event": "no_preferences_found",
                "user_id": user_id,
            }))
            return {"statusCode": 200, "body": "No preferences, skipping notification"}

        prefs = prefs_response["Item"]

        # Check if notification is wanted for this status
        pref_key = STATUS_TO_PREF.get(status)
        if pref_key and not prefs.get(pref_key, True):
            logger.info(json.dumps({
                "event": "notification_skipped",
                "user_id": user_id,
                "status": status,
                "pref_key": pref_key,
            }))
            return {"statusCode": 200, "body": f"Notification disabled for {status}"}

        # Fetch job details
        job_response = jobs_table.get_item(Key={"job_id": job_id})
        job = job_response.get("Item", {"job_id": job_id})

        # Send email if enabled
        if prefs.get("email_enabled", False):
            email_address = prefs.get("email_address")
            if email_address:
                _send_email(email_address, job, status)

        # Send webhook if enabled
        if prefs.get("webhook_enabled", False):
            webhook_url = prefs.get("webhook_url")
            if webhook_url:
                _send_webhook(webhook_url, job, status, job_id)

        return {"statusCode": 200, "body": "Notification sent"}

    except Exception as e:
        # Never fail — notifications are best-effort
        logger.error(json.dumps({
            "event": "notification_error",
            "error": str(e),
        }), exc_info=True)
        return {"statusCode": 200, "body": f"Notification error (non-fatal): {str(e)}"}
