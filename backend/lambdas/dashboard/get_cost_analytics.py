"""
Plot Palette - Cost Analytics Lambda Handler

GET /dashboard/cost-analytics endpoint that aggregates cost data
across all user jobs by day, week, or model tier.
"""

import json
import os
import sys
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

# Add shared library to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../shared"))

from boto3.dynamodb.conditions import Key  # noqa: E402
from botocore.exceptions import ClientError  # noqa: E402
from constants import MODEL_PRICING  # noqa: E402
from lambda_responses import error_response, success_response  # noqa: E402
from utils import (  # noqa: E402
    extract_request_id,
    sanitize_error_message,
    set_correlation_id,
    setup_logger,
)

# Initialize logger
logger = setup_logger(__name__)

# Initialize AWS clients
from aws_clients import get_dynamodb_resource  # noqa: E402

dynamodb = get_dynamodb_resource()
jobs_table = dynamodb.Table(os.environ.get("JOBS_TABLE_NAME", "plot-palette-Jobs"))
cost_tracking_table = dynamodb.Table(
    os.environ.get("COST_TRACKING_TABLE_NAME", "plot-palette-CostTracking")
)

PERIOD_DAYS = {"7d": 7, "30d": 30, "90d": 90}
MAX_JOBS = 100
MAX_COST_PAGES = 10


def get_user_jobs(user_id: str, cutoff: datetime) -> list[dict[str, Any]]:
    """Query user's jobs created after the cutoff date."""
    try:
        response = jobs_table.query(
            IndexName="user-id-index",
            KeyConditionExpression=Key("user_id").eq(user_id)
            & Key("created_at").gte(cutoff.isoformat()),
            ProjectionExpression="job_id, #s, budget_limit, records_generated, created_at",
            ExpressionAttributeNames={"#s": "status"},
            Limit=MAX_JOBS,
        )
        return response.get("Items", [])[:MAX_JOBS]
    except ClientError as e:
        logger.error(json.dumps({"event": "query_jobs_error", "error": str(e)}))
        return []


def get_cost_records(job_id: str) -> list[dict[str, Any]]:
    """Query all cost tracking records for a job, with pagination."""
    records: list[dict[str, Any]] = []
    last_key = None
    pages = 0
    while pages < MAX_COST_PAGES:
        query_kwargs: dict[str, Any] = {
            "KeyConditionExpression": Key("job_id").eq(job_id),
        }
        if last_key:
            query_kwargs["ExclusiveStartKey"] = last_key
        response = cost_tracking_table.query(**query_kwargs)
        records.extend(response.get("Items", []))
        last_key = response.get("LastEvaluatedKey")
        pages += 1
        if not last_key:
            break
    return records


def extract_cost(item: dict[str, Any]) -> dict[str, float]:
    """Extract cost components from a cost tracking record."""
    estimated_cost = item.get("estimated_cost", {})
    if estimated_cost is None:
        return {"bedrock": 0.0, "fargate": 0.0, "s3": 0.0, "total": 0.0}
    if isinstance(estimated_cost, dict):
        return {
            "bedrock": float(estimated_cost.get("bedrock", 0)),
            "fargate": float(estimated_cost.get("fargate", 0)),
            "s3": float(estimated_cost.get("s3", 0)),
            "total": float(estimated_cost.get("total", 0)),
        }
    val = float(estimated_cost)
    return {"bedrock": val, "fargate": 0.0, "s3": 0.0, "total": val}


def aggregate_by_day(all_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group cost records by date and sum costs per day."""
    daily: dict[str, dict[str, float]] = defaultdict(
        lambda: {"bedrock": 0.0, "fargate": 0.0, "s3": 0.0, "total": 0.0}
    )
    for record in all_records:
        ts = record.get("timestamp", "")
        if len(ts) < 10:
            continue
        date_key = ts[:10]  # YYYY-MM-DD
        costs = extract_cost(record)
        for k in ("bedrock", "fargate", "s3", "total"):
            daily[date_key][k] += costs[k]

    return [
        {"date": date, **{k: round(v, 4) for k, v in costs.items()}}
        for date, costs in sorted(daily.items())
    ]


def aggregate_by_week(all_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group cost records by ISO week and sum costs."""
    weekly: dict[str, dict[str, float]] = defaultdict(
        lambda: {"bedrock": 0.0, "fargate": 0.0, "s3": 0.0, "total": 0.0}
    )
    for record in all_records:
        ts = record.get("timestamp", "")
        try:
            dt = datetime.fromisoformat(ts)
            # ISO week: YYYY-WNN
            week_key = f"{dt.isocalendar()[0]}-W{dt.isocalendar()[1]:02d}"
        except (ValueError, TypeError):
            continue
        costs = extract_cost(record)
        for k in ("bedrock", "fargate", "s3", "total"):
            weekly[week_key][k] += costs[k]

    return [
        {"date": week, **{k: round(v, 4) for k, v in costs.items()}}
        for week, costs in sorted(weekly.items())
    ]


def aggregate_by_model(all_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group cost records by model_id and sum totals."""
    model_data: dict[str, dict[str, Any]] = defaultdict(lambda: {"total": 0.0, "job_ids": set()})
    for record in all_records:
        model_id = record.get("model_id", "unknown")
        costs = extract_cost(record)
        model_data[model_id]["total"] += costs["total"]
        model_data[model_id]["job_ids"].add(record.get("job_id", ""))

    return sorted(
        [
            {
                "model_id": mid,
                "model_name": MODEL_PRICING.get(mid, {}).get("name", mid),
                "total": round(data["total"], 4),
                "job_count": len(data["job_ids"]),
            }
            for mid, data in model_data.items()
        ],
        key=lambda x: x["total"],
        reverse=True,
    )


def compute_summary(
    jobs: list[dict[str, Any]],
    all_records: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compute summary statistics across all jobs and cost records."""
    total_spend = sum(extract_cost(r)["total"] for r in all_records)
    job_count = len(jobs)
    total_records = sum(int(j.get("records_generated", 0)) for j in jobs)

    # Budget efficiency: average (cost / budget_limit) for completed jobs
    completed_jobs = [j for j in jobs if j.get("status") == "COMPLETED"]
    budget_efficiency = 0.0
    if completed_jobs:
        efficiencies = []
        for job in completed_jobs:
            budget = float(job.get("budget_limit", 0))
            if budget > 0:
                # Get cost for this job
                job_cost = sum(
                    extract_cost(r)["total"]
                    for r in all_records
                    if r.get("job_id") == job["job_id"]
                )
                efficiencies.append(job_cost / budget)
        if efficiencies:
            budget_efficiency = sum(efficiencies) / len(efficiencies)

    # Most expensive job
    job_costs: dict[str, float] = defaultdict(float)
    for record in all_records:
        job_costs[record.get("job_id", "")] += extract_cost(record)["total"]
    most_expensive = (
        max(job_costs, key=job_costs.get, default=None)  # type: ignore[arg-type]
        if job_costs
        else None
    )

    return {
        "total_spend": round(total_spend, 4),
        "job_count": job_count,
        "avg_cost_per_job": round(total_spend / job_count, 4) if job_count > 0 else 0,
        "avg_cost_per_record": round(total_spend / total_records, 4) if total_records > 0 else 0,
        "budget_efficiency": round(budget_efficiency, 4),
        "most_expensive_job": most_expensive,
    }


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Lambda handler for GET /dashboard/cost-analytics endpoint.

    Aggregates cost data across user jobs by day, week, or model.

    Query parameters:
        period: 7d, 30d, 90d (default 30d)
        group_by: day, week, model (default day)
    """
    try:
        set_correlation_id(extract_request_id(event))

        user_id = event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]

        params = event.get("queryStringParameters") or {}
        period = params.get("period", "30d")
        group_by = params.get("group_by", "day")

        if period not in PERIOD_DAYS:
            return error_response(400, f"Invalid period: {period}. Must be one of: 7d, 30d, 90d")

        if group_by not in ("day", "week", "model"):
            return error_response(
                400, f"Invalid group_by: {group_by}. Must be one of: day, week, model"
            )

        logger.info(
            json.dumps(
                {
                    "event": "cost_analytics_request",
                    "period": period,
                    "group_by": group_by,
                }
            )
        )

        cutoff = datetime.now(UTC) - timedelta(days=PERIOD_DAYS[period])
        jobs = get_user_jobs(user_id, cutoff)

        # Collect all cost records across jobs
        all_records: list[dict[str, Any]] = []
        for job in jobs:
            records = get_cost_records(job["job_id"])
            all_records.extend(records)

        # Deduplicate: keep only the latest cost record per job.
        # Cost records are cumulative snapshots (each contains total cost
        # from job start), so only the final record represents actual spend.
        latest_by_job: dict[str, dict[str, Any]] = {}
        for record in all_records:
            jid = record.get("job_id", "")
            ts = record.get("timestamp", "")
            if jid not in latest_by_job or ts > latest_by_job[jid].get("timestamp", ""):
                latest_by_job[jid] = record
        all_records = list(latest_by_job.values())

        # Build time series
        if group_by == "week":
            time_series = aggregate_by_week(all_records)
        elif group_by == "model":
            time_series = []  # No time series for model grouping
        else:
            time_series = aggregate_by_day(all_records)

        by_model = aggregate_by_model(all_records)
        summary = compute_summary(jobs, all_records)

        logger.info(
            json.dumps(
                {
                    "event": "cost_analytics_success",
                    "job_count": len(jobs),
                    "record_count": len(all_records),
                }
            )
        )

        return success_response(
            200,
            {
                "summary": summary,
                "time_series": time_series,
                "by_model": by_model,
            },
            default=str,
        )

    except KeyError as e:
        logger.error(json.dumps({"event": "missing_field_error", "error": str(e)}))
        return error_response(400, f"Missing required field: {sanitize_error_message(str(e))}")

    except Exception as e:
        logger.error(json.dumps({"event": "unexpected_error", "error": str(e)}), exc_info=True)
        return error_response(500, "Internal server error")
