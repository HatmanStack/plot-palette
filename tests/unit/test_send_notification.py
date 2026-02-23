"""
Unit tests for send_notification Lambda handler.

Tests email and webhook dispatch based on user notification preferences.
"""

import json
from decimal import Decimal
from unittest.mock import patch, MagicMock

from tests.unit.handler_import import load_handler

_mod = load_handler("lambdas/notifications/send_notification.py")
lambda_handler = _mod.lambda_handler


def _make_prefs(
    email_enabled=False,
    email_address=None,
    webhook_enabled=False,
    webhook_url=None,
    notify_on_complete=True,
    notify_on_failure=True,
    notify_on_budget_exceeded=True,
):
    item = {
        "user_id": "user-A",
        "email_enabled": email_enabled,
        "webhook_enabled": webhook_enabled,
        "notify_on_complete": notify_on_complete,
        "notify_on_failure": notify_on_failure,
        "notify_on_budget_exceeded": notify_on_budget_exceeded,
        "updated_at": "2026-02-22T12:00:00+00:00",
    }
    if email_address:
        item["email_address"] = email_address
    if webhook_url:
        item["webhook_url"] = webhook_url
    return item


def _make_job(job_id="job-1", status="COMPLETED"):
    return {
        "job_id": job_id,
        "user_id": "user-A",
        "status": status,
        "records_generated": 500,
        "cost_estimate": Decimal("12.50"),
        "budget_limit": Decimal("50"),
        "config": {"template_id": "tmpl-1"},
    }


def _make_event(job_id="job-1", status="COMPLETED", user_id="user-A"):
    return {"job_id": job_id, "status": status, "user_id": user_id}


def _setup_tables(prefs_item=None, job_item=None):
    """Set up separate mock tables for prefs and jobs to avoid aliasing."""
    mock_prefs_table = MagicMock()
    mock_jobs_table = MagicMock()

    if prefs_item is not None:
        mock_prefs_table.get_item.return_value = {"Item": prefs_item}
    else:
        mock_prefs_table.get_item.return_value = {}

    if job_item is not None:
        mock_jobs_table.get_item.return_value = {"Item": job_item}
    else:
        mock_jobs_table.get_item.return_value = {}

    _mod.prefs_table = mock_prefs_table
    _mod.jobs_table = mock_jobs_table


class TestSendNotification:
    def test_send_email_on_complete(self):
        """Email enabled, job completed. Assert SES send_email called."""
        _setup_tables(
            prefs_item=_make_prefs(email_enabled=True, email_address="user@example.com"),
            job_item=_make_job(),
        )
        _mod.ses_client = MagicMock()
        _mod.ses_client.send_email.return_value = {"MessageId": "msg-1"}

        result = lambda_handler(_make_event(), None)

        assert result["statusCode"] == 200
        _mod.ses_client.send_email.assert_called_once()
        call_kwargs = _mod.ses_client.send_email.call_args
        assert call_kwargs[1]["Destination"]["ToAddresses"] == ["user@example.com"]

    def test_skip_email_when_disabled(self):
        """Email disabled. Assert SES not called."""
        _setup_tables(
            prefs_item=_make_prefs(email_enabled=False),
            job_item=_make_job(),
        )
        _mod.ses_client = MagicMock()

        result = lambda_handler(_make_event(), None)

        assert result["statusCode"] == 200
        _mod.ses_client.send_email.assert_not_called()

    def test_skip_email_wrong_status(self):
        """notify_on_failure=false, job failed. Assert SES not called."""
        _setup_tables(
            prefs_item=_make_prefs(
                email_enabled=True,
                email_address="user@example.com",
                notify_on_failure=False,
            ),
        )
        _mod.ses_client = MagicMock()

        result = lambda_handler(_make_event(status="FAILED"), None)

        assert result["statusCode"] == 200
        _mod.ses_client.send_email.assert_not_called()

    def test_send_webhook_on_failure(self):
        """Webhook enabled, job failed. Assert webhook POST sent."""
        _setup_tables(
            prefs_item=_make_prefs(
                webhook_enabled=True,
                webhook_url="https://hooks.example.com/notify",
            ),
            job_item=_make_job(status="FAILED"),
        )
        _mod.ses_client = MagicMock()

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.__enter__ = MagicMock(return_value=mock_resp)
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp

            result = lambda_handler(_make_event(status="FAILED"), None)

        assert result["statusCode"] == 200
        mock_urlopen.assert_called_once()

    def test_webhook_failure_handled(self):
        """Webhook returns error. Assert handler returns success anyway."""
        _setup_tables(
            prefs_item=_make_prefs(
                webhook_enabled=True,
                webhook_url="https://hooks.example.com/notify",
            ),
            job_item=_make_job(),
        )
        _mod.ses_client = MagicMock()

        import urllib.error

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

            result = lambda_handler(_make_event(), None)

        # Should still succeed (notifications are best-effort)
        assert result["statusCode"] == 200

    def test_no_preferences_no_notification(self):
        """No preferences saved for user. Assert no SES/webhook calls."""
        _setup_tables()  # No prefs
        _mod.ses_client = MagicMock()

        result = lambda_handler(_make_event(), None)

        assert result["statusCode"] == 200
        _mod.ses_client.send_email.assert_not_called()

    def test_both_email_and_webhook(self):
        """Both enabled. Assert both SES and webhook called."""
        _setup_tables(
            prefs_item=_make_prefs(
                email_enabled=True,
                email_address="user@example.com",
                webhook_enabled=True,
                webhook_url="https://hooks.example.com/notify",
            ),
            job_item=_make_job(),
        )
        _mod.ses_client = MagicMock()
        _mod.ses_client.send_email.return_value = {"MessageId": "msg-2"}

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.__enter__ = MagicMock(return_value=mock_resp)
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp

            result = lambda_handler(_make_event(), None)

        assert result["statusCode"] == 200
        _mod.ses_client.send_email.assert_called_once()
        mock_urlopen.assert_called_once()
