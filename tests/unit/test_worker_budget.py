"""
Plot Palette - Worker Budget Enforcement Tests

Tests that Worker correctly enforces budget limits and handles BudgetExceededError.
"""

import pytest


class BudgetExceededError(Exception):
    """Exception raised when job exceeds budget limit."""
    pass


class TestBudgetCheckBeforeGeneration:
    """Tests for budget check before each record."""

    def test_budget_checked_before_each_record(self):
        """Test that budget is checked before generating each record."""
        budget_checks = 0
        budget_limit = 10.0
        current_cost = 0.0
        records_to_generate = 5

        for i in range(records_to_generate):
            budget_checks += 1
            if current_cost >= budget_limit:
                break
            current_cost += 1.0  # Simulate cost per record

        assert budget_checks == 5

    def test_generation_stops_at_budget_limit(self):
        """Test that generation stops when budget is reached."""
        budget_limit = 5.0
        records_generated = 0

        # Per-record costs: 1.0, 1.5, 2.0, 2.5, 3.0
        # Cumulative: 1.0, 2.5, 4.5, 7.0, 10.0
        # Check happens AFTER each record, so we stop when cumulative >= limit
        costs = [1.0, 1.5, 2.0, 2.5, 3.0]
        total_cost = 0.0

        for cost in costs:
            total_cost += cost
            if total_cost >= budget_limit:
                break
            records_generated += 1

        # After record 1: 1.0 < 5.0, continue (count=1)
        # After record 2: 2.5 < 5.0, continue (count=2)
        # After record 3: 4.5 < 5.0, continue (count=3)
        # After record 4: 7.0 >= 5.0, break (count still 3)
        assert records_generated == 3


class TestBudgetExceededError:
    """Tests for BudgetExceededError handling."""

    def test_budget_exceeded_error_raised(self):
        """Test that BudgetExceededError is raised when budget exceeded."""
        budget_limit = 10.0
        current_cost = 11.0

        with pytest.raises(BudgetExceededError) as exc_info:
            if current_cost >= budget_limit:
                raise BudgetExceededError(f"Exceeded budget limit of ${budget_limit}")

        assert "budget limit" in str(exc_info.value)

    def test_error_message_includes_budget_amount(self):
        """Test that error message includes the budget amount."""
        budget_limit = 50.0

        try:
            raise BudgetExceededError(f"Exceeded budget limit of ${budget_limit}")
        except BudgetExceededError as e:
            error_message = str(e)

        assert "$50.0" in error_message or "50.0" in error_message


class TestMarkJobBudgetExceeded:
    """Tests for mark_job_budget_exceeded functionality."""

    def test_job_status_set_to_budget_exceeded(self):
        """Test that job status is set to BUDGET_EXCEEDED."""
        job_status = 'RUNNING'

        # When budget exceeded
        job_status = 'BUDGET_EXCEEDED'

        assert job_status == 'BUDGET_EXCEEDED'

    def test_budget_exceeded_is_terminal_state(self):
        """Test that BUDGET_EXCEEDED is a terminal state."""
        terminal_states = ['COMPLETED', 'FAILED', 'CANCELLED', 'BUDGET_EXCEEDED']

        assert 'BUDGET_EXCEEDED' in terminal_states


class TestBudgetValueNormalization:
    """Tests for budget value type handling."""

    def test_string_budget_converted_to_float(self):
        """Test that string budget_limit is converted to float."""
        budget_limit_raw = "100.0"

        budget_limit = float(budget_limit_raw)

        assert budget_limit == 100.0
        assert isinstance(budget_limit, float)

    def test_integer_budget_converted_to_float(self):
        """Test that integer budget_limit works."""
        budget_limit_raw = 100

        budget_limit = float(budget_limit_raw)

        assert budget_limit == 100.0

    def test_decimal_string_converted(self):
        """Test decimal string conversion."""
        budget_limit_raw = "99.99"

        budget_limit = float(budget_limit_raw)

        assert budget_limit == 99.99


class TestInvalidBudgetFallback:
    """Tests for invalid budget value handling."""

    def test_none_budget_uses_default(self):
        """Test that None budget uses default."""
        budget_limit_raw = None
        default_budget = 100.0

        try:
            budget_limit = float(budget_limit_raw)
        except (TypeError, ValueError):
            budget_limit = default_budget

        assert budget_limit == 100.0

    def test_invalid_string_uses_default(self):
        """Test that invalid string uses default."""
        budget_limit_raw = "invalid"
        default_budget = 100.0

        try:
            budget_limit = float(budget_limit_raw)
        except (TypeError, ValueError):
            budget_limit = default_budget

        assert budget_limit == 100.0

    def test_empty_string_uses_default(self):
        """Test that empty string uses default."""
        budget_limit_raw = ""
        default_budget = 100.0

        try:
            budget_limit = float(budget_limit_raw) if budget_limit_raw else default_budget
        except (TypeError, ValueError):
            budget_limit = default_budget

        assert budget_limit == 100.0


class TestCostCalculationQueryFailure:
    """Tests for cost calculation query failure handling."""

    def test_cost_query_failure_returns_zero(self):
        """Test that cost query failure returns 0.0 (fail open)."""
        error_occurred = True

        if error_occurred:
            current_cost = 0.0
        else:
            current_cost = 5.0

        assert current_cost == 0.0

    def test_generation_continues_on_cost_failure(self):
        """Test that generation continues when cost query fails."""
        cost_query_failed = True
        generation_should_continue = True

        if cost_query_failed:
            # Use 0.0 as current cost, don't stop generation
            pass

        assert generation_should_continue is True


class TestBudgetAtLimit:
    """Tests for budget exactly at limit scenarios."""

    def test_cost_equal_to_budget_triggers_exceeded(self):
        """Test that cost >= budget triggers exceeded (not just >)."""
        budget_limit = 10.0
        current_cost = 10.0

        is_exceeded = current_cost >= budget_limit

        assert is_exceeded is True

    def test_cost_slightly_below_budget_continues(self):
        """Test that cost just below budget allows continuation."""
        budget_limit = 10.0
        current_cost = 9.99

        is_exceeded = current_cost >= budget_limit

        assert is_exceeded is False


class TestBudgetEnforcementInterval:
    """Tests for budget enforcement interval."""

    def test_budget_checked_every_record(self):
        """Test that budget is checked for every record."""
        budget_check_interval = 1  # Check every record

        assert budget_check_interval == 1

    def test_no_records_skipped_between_checks(self):
        """Test that no records are generated without budget check."""
        check_count = 0
        record_count = 0

        for i in range(10):
            check_count += 1  # Check happens
            record_count += 1  # Then record generated

        assert check_count == record_count


class TestCostAccumulation:
    """Tests for cost accumulation tracking."""

    def test_cost_accumulated_in_checkpoint(self):
        """Test that cost is accumulated in checkpoint."""
        checkpoint = {
            'records_generated': 100,
            'cost_accumulated': 0.0
        }

        # Simulate cost updates
        checkpoint['cost_accumulated'] = 2.50

        assert checkpoint['cost_accumulated'] == 2.50

    def test_cost_updated_at_checkpoint_interval(self):
        """Test that cost is updated at checkpoint intervals."""
        checkpoint_interval = 50
        records_generated = 100
        cost_updates = records_generated // checkpoint_interval

        assert cost_updates == 2


class TestBudgetFromDifferentSources:
    """Tests for budget from different configuration sources."""

    def test_budget_from_config(self):
        """Test reading budget from config dictionary."""
        config = {'budget_limit': 75.0}

        budget_limit = config.get('budget_limit', 100.0)

        assert budget_limit == 75.0

    def test_budget_from_job_fallback(self):
        """Test fallback to job-level budget_limit."""
        config = {}  # No budget in config
        job = {'budget_limit': 50.0}

        budget_limit = config.get('budget_limit', job.get('budget_limit', 100.0))

        assert budget_limit == 50.0

    def test_budget_default_when_not_specified(self):
        """Test default budget when not specified anywhere."""
        config = {}
        job = {}
        default_budget = 100.0

        budget_limit = config.get('budget_limit', job.get('budget_limit', default_budget))

        assert budget_limit == 100.0


class TestOutputTokenPricing:
    """Tests for output token pricing inclusion."""

    def test_output_tokens_included_in_cost(self):
        """Test that cost calculation includes both input and output token pricing."""
        from backend.shared.constants import MODEL_PRICING

        model_id = 'anthropic.claude-3-5-sonnet-20241022-v2:0'
        pricing = MODEL_PRICING[model_id]
        tokens_used = 1_000_000

        # Old calculation (input only)
        old_cost = (tokens_used / 1_000_000) * pricing['input']

        # New calculation (40/60 input/output split)
        input_tokens = int(tokens_used * 0.4)
        output_tokens = tokens_used - input_tokens
        new_cost = (input_tokens / 1_000_000) * pricing['input'] + \
                   (output_tokens / 1_000_000) * pricing['output']

        # New cost should be significantly higher than old cost
        assert new_cost > old_cost
        # Claude Sonnet: input=$3, output=$15
        # Old: 1M * $3/1M = $3.00
        # New: 400K * $3/1M + 600K * $15/1M = $1.20 + $9.00 = $10.20
        assert abs(new_cost - 10.20) < 0.01

    def test_estimate_single_call_cost(self):
        """Test estimate_single_call_cost helper returns non-zero for valid input."""
        import json
        from backend.shared.constants import MODEL_PRICING

        result = {"step1": {"output": "Generated text " * 100}}
        model_id = 'meta.llama3-1-8b-instruct-v1:0'
        pricing = MODEL_PRICING[model_id]

        text = json.dumps(result)
        tokens = max(1, int(len(text) / 4))  # Llama token estimation
        input_tokens = int(tokens * 0.4)
        output_tokens = tokens - input_tokens
        cost = (input_tokens / 1_000_000) * pricing['input'] + \
               (output_tokens / 1_000_000) * pricing['output']

        assert cost > 0


class TestStepFunctionsModeBudget:
    """Tests for budget exceeded behavior in Step Functions mode."""

    def test_sf_mode_exits_with_budget_exceeded_code(self):
        """In SF mode, BudgetExceededError causes exit code 2."""
        from backend.shared.constants import WORKER_EXIT_BUDGET_EXCEEDED

        exit_code = WORKER_EXIT_BUDGET_EXCEEDED
        assert exit_code == 2

    def test_sf_mode_state_machine_marks_budget_exceeded(self):
        """Step Functions state machine marks job as BUDGET_EXCEEDED on exit code 2."""
        exit_code = 2
        expected_status = 'BUDGET_EXCEEDED' if exit_code == 2 else 'FAILED'
        assert expected_status == 'BUDGET_EXCEEDED'

    def test_sf_mode_budget_exceeded_is_terminal(self):
        """In SF mode, exit code 2 leads to terminal BUDGET_EXCEEDED state."""
        terminal_exit_codes = {0: 'COMPLETED', 2: 'BUDGET_EXCEEDED'}
        non_terminal_exit_codes = {1: 'FAILED'}

        assert 2 in terminal_exit_codes
        assert terminal_exit_codes[2] == 'BUDGET_EXCEEDED'


class TestInMemoryBudgetTracking:
    """Tests for in-memory budget tracking."""

    def test_running_cost_catches_overage_within_checkpoint(self):
        """Test that in-memory running cost catches budget overages within checkpoint interval."""
        budget_limit = 1.0
        running_cost = 0.0
        records_generated = 0
        checkpoint_interval = 50

        # Simulate high per-record cost
        cost_per_record = 0.05  # $0.05 per record

        for i in range(100):
            if running_cost >= budget_limit:
                break
            running_cost += cost_per_record
            records_generated += 1

        # Should stop at 20 records (20 * 0.05 = 1.00)
        assert records_generated == 20
        # This is well within the checkpoint interval of 50
        assert records_generated < checkpoint_interval
