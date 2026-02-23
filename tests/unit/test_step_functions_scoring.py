"""
Unit tests for Step Functions quality scoring state machine integration.

Verifies that the job-lifecycle.asl.json includes the ScoreJobQuality
state with correct configuration.
"""

import json
import os
import re

import pytest

ASL_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "backend",
    "infrastructure",
    "step-functions",
    "job-lifecycle.asl.json",
)


@pytest.fixture
def state_machine():
    """Load the state machine definition, substituting SAM variables."""
    with open(ASL_PATH) as f:
        content = f.read()

    # Replace bare ${SubnetIds} (not inside quotes) with a placeholder JSON array
    content = re.sub(r':\s*\$\{SubnetIds\}', ': ["subnet-placeholder"]', content)

    return json.loads(content)


class TestScoreJobQualityState:
    """Test ScoreJobQuality state is correctly configured in the ASL."""

    def test_score_job_quality_state_exists(self, state_machine):
        """Assert ScoreJobQuality state exists."""
        assert "ScoreJobQuality" in state_machine["States"]

    def test_mark_job_completed_next_is_scoring(self, state_machine):
        """Assert MarkJobCompleted.Next == ScoreJobQuality."""
        mark_completed = state_machine["States"]["MarkJobCompleted"]
        assert mark_completed["Next"] == "ScoreJobQuality"

    def test_score_job_quality_next_is_notification(self, state_machine):
        """Assert ScoreJobQuality.Next == SendNotificationCompleted."""
        score_state = state_machine["States"]["ScoreJobQuality"]
        assert score_state["Next"] == "SendNotificationCompleted"

    def test_score_job_quality_has_catch(self, state_machine):
        """Assert Catch block is present and catches all errors."""
        score_state = state_machine["States"]["ScoreJobQuality"]
        assert "Catch" in score_state
        catch_block = score_state["Catch"][0]
        assert "States.ALL" in catch_block["ErrorEquals"]
        assert catch_block["Next"] == "SendNotificationCompleted"

    def test_score_job_quality_result_path_null(self, state_machine):
        """Assert ResultPath is null (don't pollute state)."""
        score_state = state_machine["States"]["ScoreJobQuality"]
        assert score_state["ResultPath"] is None

    def test_score_job_quality_timeout(self, state_machine):
        """Assert timeout is 180 seconds."""
        score_state = state_machine["States"]["ScoreJobQuality"]
        assert score_state["TimeoutSeconds"] == 180

    def test_score_job_quality_resource(self, state_machine):
        """Assert resource uses substitution variable."""
        score_state = state_machine["States"]["ScoreJobQuality"]
        assert score_state["Resource"] == "${ScoreJobFunctionArn}"

    def test_flow_order(self, state_machine):
        """Assert correct flow: MarkJobCompleted -> ScoreJobQuality -> SendNotificationCompleted -> EndCompleted."""
        states = state_machine["States"]

        assert states["MarkJobCompleted"]["Next"] == "ScoreJobQuality"
        assert states["ScoreJobQuality"]["Next"] == "SendNotificationCompleted"
        assert states["SendNotificationCompleted"]["Next"] == "EndCompleted"
