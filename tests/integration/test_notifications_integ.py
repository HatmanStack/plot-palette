"""
Integration tests for notification dispatch — calls actual lambda_handler against moto.

Uses moto's @mock_aws to create real DynamoDB tables, then invokes the
actual send_notification.lambda_handler.
"""

import json
from decimal import Decimal
from unittest.mock import MagicMock, patch

import boto3
from moto import mock_aws

from tests.unit.handler_import import load_handler

_mod = load_handler("lambdas/notifications/send_notification.py")
lambda_handler = _mod.lambda_handler


def _create_prefs_table(dynamodb):
    """Create NotificationPreferences table."""
    return dynamodb.create_table(
        TableName="plot-palette-NotificationPreferences-test",
        KeySchema=[{"AttributeName": "user_id", "KeyType": "HASH"}],
        AttributeDefinitions=[
            {"AttributeName": "user_id", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )


def _create_jobs_table(dynamodb):
    """Create Jobs table."""
    return dynamodb.create_table(
        TableName="plot-palette-Jobs-test",
        KeySchema=[{"AttributeName": "job_id", "KeyType": "HASH"}],
        AttributeDefinitions=[
            {"AttributeName": "job_id", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )


def _insert_job(jobs_table, job_id="job-1", user_id="user-A"):
    """Insert a completed job."""
    jobs_table.put_item(Item={
        "job_id": job_id,
        "user_id": user_id,
        "status": "COMPLETED",
        "records_generated": 500,
        "cost_estimate": Decimal("12.50"),
        "config": {"template_id": "tmpl-1"},
    })


def _insert_preferences(prefs_table, user_id="user-A", **overrides):
    """Insert notification preferences."""
    item = {
        "user_id": user_id,
        "email_enabled": True,
        "email_address": "test@example.com",
        "webhook_enabled": False,
        "webhook_url": None,
        "notify_on_complete": True,
        "notify_on_failure": True,
        "notify_on_budget_exceeded": True,
    }
    item.update(overrides)
    # Remove None values (DynamoDB doesn't accept None for string attributes)
    item = {k: v for k, v in item.items() if v is not None}
    prefs_table.put_item(Item=item)


@mock_aws
def test_notification_sends_email_on_complete():
    """Email enabled, job completed. Assert SES send_email called."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    prefs_table = _create_prefs_table(dynamodb)
    jobs_table = _create_jobs_table(dynamodb)

    _insert_job(jobs_table)
    _insert_preferences(prefs_table)

    _mod.prefs_table = prefs_table
    _mod.jobs_table = jobs_table

    mock_ses = MagicMock()
    _mod.ses_client = mock_ses

    event = {"job_id": "job-1", "status": "COMPLETED", "user_id": "user-A"}
    result = lambda_handler(event, None)

    assert result["statusCode"] == 200
    mock_ses.send_email.assert_called_once()
    call_args = mock_ses.send_email.call_args
    assert call_args.kwargs["Destination"]["ToAddresses"] == ["test@example.com"]
    assert "Completed" in call_args.kwargs["Message"]["Subject"]["Data"]


@mock_aws
def test_notification_skips_email_when_disabled():
    """Email disabled. Assert SES not called."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    prefs_table = _create_prefs_table(dynamodb)
    jobs_table = _create_jobs_table(dynamodb)

    _insert_job(jobs_table)
    _insert_preferences(prefs_table, email_enabled=False)

    _mod.prefs_table = prefs_table
    _mod.jobs_table = jobs_table

    mock_ses = MagicMock()
    _mod.ses_client = mock_ses

    event = {"job_id": "job-1", "status": "COMPLETED", "user_id": "user-A"}
    result = lambda_handler(event, None)

    assert result["statusCode"] == 200
    mock_ses.send_email.assert_not_called()


@mock_aws
def test_notification_skips_for_wrong_status_preference():
    """notify_on_failure=false, job failed. Assert SES not called."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    prefs_table = _create_prefs_table(dynamodb)
    jobs_table = _create_jobs_table(dynamodb)

    _insert_job(jobs_table)
    _insert_preferences(prefs_table, notify_on_failure=False)

    _mod.prefs_table = prefs_table
    _mod.jobs_table = jobs_table

    mock_ses = MagicMock()
    _mod.ses_client = mock_ses

    event = {"job_id": "job-1", "status": "FAILED", "user_id": "user-A"}
    result = lambda_handler(event, None)

    assert result["statusCode"] == 200
    mock_ses.send_email.assert_not_called()


@mock_aws
def test_notification_no_preferences_no_notification():
    """No preferences saved for user. Assert no SES call."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    prefs_table = _create_prefs_table(dynamodb)
    jobs_table = _create_jobs_table(dynamodb)

    _insert_job(jobs_table)
    # No preferences inserted for user-A

    _mod.prefs_table = prefs_table
    _mod.jobs_table = jobs_table

    mock_ses = MagicMock()
    _mod.ses_client = mock_ses

    event = {"job_id": "job-1", "status": "COMPLETED", "user_id": "user-A"}
    result = lambda_handler(event, None)

    assert result["statusCode"] == 200
    mock_ses.send_email.assert_not_called()
    assert "No preferences" in result["body"]


@mock_aws
def test_notification_sends_webhook():
    """Webhook enabled, job completed. Assert webhook POST made."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    prefs_table = _create_prefs_table(dynamodb)
    jobs_table = _create_jobs_table(dynamodb)

    _insert_job(jobs_table)
    _insert_preferences(
        prefs_table,
        email_enabled=False,
        webhook_enabled=True,
        webhook_url="https://hooks.example.com/notify",
    )

    _mod.prefs_table = prefs_table
    _mod.jobs_table = jobs_table

    mock_ses = MagicMock()
    _mod.ses_client = mock_ses

    event = {"job_id": "job-1", "status": "COMPLETED", "user_id": "user-A"}

    public_addrinfo = [(2, 1, 6, "", ("93.184.216.34", 443))]
    with (
        patch("socket.getaddrinfo", return_value=public_addrinfo),
        patch("urllib.request.urlopen") as mock_urlopen,
    ):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        result = lambda_handler(event, None)

    assert result["statusCode"] == 200
    mock_ses.send_email.assert_not_called()
    mock_urlopen.assert_called_once()

    # Verify webhook request
    req = mock_urlopen.call_args[0][0]
    payload = json.loads(req.data.decode("utf-8"))
    assert payload["job_id"] == "job-1"
    assert payload["status"] == "COMPLETED"
    assert payload["records_generated"] == 500


@mock_aws
def test_notification_both_email_and_webhook():
    """Both email and webhook enabled. Assert both called."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    prefs_table = _create_prefs_table(dynamodb)
    jobs_table = _create_jobs_table(dynamodb)

    _insert_job(jobs_table)
    _insert_preferences(
        prefs_table,
        email_enabled=True,
        webhook_enabled=True,
        webhook_url="https://hooks.example.com/notify",
    )

    _mod.prefs_table = prefs_table
    _mod.jobs_table = jobs_table

    mock_ses = MagicMock()
    _mod.ses_client = mock_ses

    event = {"job_id": "job-1", "status": "COMPLETED", "user_id": "user-A"}

    public_addrinfo = [(2, 1, 6, "", ("93.184.216.34", 443))]
    with (
        patch("socket.getaddrinfo", return_value=public_addrinfo),
        patch("urllib.request.urlopen") as mock_urlopen,
    ):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        result = lambda_handler(event, None)

    assert result["statusCode"] == 200
    mock_ses.send_email.assert_called_once()
    mock_urlopen.assert_called_once()
