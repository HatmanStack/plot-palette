"""
Plot Palette - Quality Scoring Lambda Handler

Invoked by Step Functions after job completion, or manually via trigger_scoring.
Samples records from a completed job's export, sends them to an LLM for
evaluation, computes aggregate quality scores, and stores results.
"""

import json
import math
import os
import random
import re
import sys
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

# Add shared library to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../shared"))

from aws_clients import get_bedrock_client, get_dynamodb_resource, get_s3_client  # noqa: E402
from constants import (  # noqa: E402
    QUALITY_BATCH_SIZE,
    QUALITY_DIMENSIONS,
    QUALITY_SAMPLE_SIZE,
    QUALITY_SCORING_MODEL,
    QUALITY_WEIGHTS,
    QualityStatus,
)
from utils import (  # noqa: E402
    calculate_bedrock_cost,
    estimate_tokens,
    sanitize_error_message,
    setup_logger,
)

logger = setup_logger(__name__)

dynamodb = get_dynamodb_resource()
s3_client = get_s3_client()
bedrock_client = get_bedrock_client()

jobs_table = dynamodb.Table(os.environ.get("JOBS_TABLE_NAME", "plot-palette-Jobs"))
templates_table = dynamodb.Table(os.environ.get("TEMPLATES_TABLE_NAME", "plot-palette-Templates"))
quality_table = dynamodb.Table(
    os.environ.get("QUALITY_METRICS_TABLE_NAME", "plot-palette-QualityMetrics")
)
bucket_name = os.environ.get("BUCKET_NAME", "")


def _load_export_records(job_id: str, output_format: str) -> list[dict[str, Any]]:
    """Load records from the job's export file in S3."""
    if output_format.upper() != "JSONL":
        raise ValueError(f"Quality scoring only supports JSONL exports, got {output_format}")

    s3_key = f"jobs/{job_id}/exports/dataset.jsonl"
    response = s3_client.get_object(Bucket=bucket_name, Key=s3_key)
    body = response["Body"].read().decode("utf-8")

    records = []
    for line in body.strip().split("\n"):
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return records


def _build_scoring_prompt(
    records: list[dict[str, Any]],
    template_name: str,
    schema_requirements: list[str],
    start_index: int,
) -> str:
    """Build a batched scoring prompt for multiple records."""
    records_section = ""
    for i, record in enumerate(records):
        record_text = json.dumps(record, indent=2, default=str)
        records_section += f"\n--- Record {start_index + i + 1} ---\n{record_text}\n"

    schema_str = ", ".join(schema_requirements) if schema_requirements else "N/A"

    return f"""You are evaluating the quality of synthetically generated data records.

Template context: This template generates "{template_name}" data.
Schema requirements: {schema_str}

Score each of the following {len(records)} records on these dimensions (0.0 to 1.0):
1. Coherence: Is the text grammatically correct, logically consistent, and well-structured?
2. Relevance: Does the output relate to the seed data and follow the template's intent?
3. Format compliance: Does the output structure match the expected schema?

{records_section}

Respond with ONLY a JSON array of {len(records)} objects, one per record, in order:
[{{"coherence": 0.X, "relevance": 0.X, "format_compliance": 0.X, "detail": "brief rationale"}}]"""


def _invoke_bedrock_scoring(prompt: str) -> tuple[list[dict[str, Any]], int, int]:
    """Invoke Bedrock for scoring and return parsed scores plus token estimates."""
    model_id = QUALITY_SCORING_MODEL

    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
        "temperature": 0.0,
    }

    response = bedrock_client.invoke_model(
        modelId=model_id,
        body=json.dumps(request_body),
    )

    response_body = json.loads(response["body"].read())
    content = response_body.get("content", [])
    text = ""
    if isinstance(content, list) and len(content) > 0:
        text = next((c.get("text", "") for c in content if isinstance(c, dict)), "")

    # Estimate tokens
    input_tokens = estimate_tokens(prompt, model_id)
    output_tokens = estimate_tokens(text, model_id)

    # Parse JSON from response (strip markdown wrappers)
    cleaned = re.sub(r"```(?:json)?\s*", "", text).strip()
    cleaned = re.sub(r"```\s*$", "", cleaned).strip()

    try:
        scores = json.loads(cleaned)
    except json.JSONDecodeError:
        # Try extracting array
        match = re.search(r"\[.*\]", cleaned, re.DOTALL)
        if match:
            scores = json.loads(match.group())
        else:
            raise ValueError("Could not parse scoring response as JSON") from None

    if not isinstance(scores, list):
        scores = [scores]

    return scores, input_tokens, output_tokens


def _compute_diversity(records: list[dict[str, Any]]) -> float:
    """Compute diversity score from unique first-50-char prefixes."""
    if not records:
        return 0.0

    prefixes = set()
    for record in records:
        text = str(record.get("generation_result", record))
        prefixes.add(text[:50])

    return len(prefixes) / len(records)


def _compute_overall_score(aggregate_scores: dict[str, float], diversity_score: float) -> float:
    """Compute weighted overall score."""
    total = 0.0
    for dim in QUALITY_DIMENSIONS:
        if dim in aggregate_scores:
            total += aggregate_scores[dim] * QUALITY_WEIGHTS.get(dim, 0)
    total += diversity_score * QUALITY_WEIGHTS.get("diversity", 0)
    return round(total, 4)


def _convert_record_scores(scores: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert float values in record scores to Decimal for DynamoDB."""
    converted = []
    for s in scores:
        converted.append({
            "record_index": s.get("record_index", 0),
            "coherence": Decimal(str(round(float(s.get("coherence", 0)), 4))),
            "relevance": Decimal(str(round(float(s.get("relevance", 0)), 4))),
            "format_compliance": Decimal(str(round(float(s.get("format_compliance", 0)), 4))),
            "detail": s.get("detail", ""),
        })
    return converted


def _store_quality_metrics(
    job_id: str,
    status: QualityStatus,
    sample_size: int = 0,
    total_records: int = 0,
    aggregate_scores: dict[str, float] | None = None,
    diversity_score: float = 0.0,
    overall_score: float = 0.0,
    record_scores: list[dict[str, Any]] | None = None,
    scoring_cost: float = 0.0,
    error_message: str | None = None,
) -> None:
    """Store quality metrics in DynamoDB."""
    item: dict[str, Any] = {
        "job_id": job_id,
        "scored_at": datetime.now(UTC).isoformat(),
        "sample_size": sample_size,
        "total_records": total_records,
        "model_used_for_scoring": QUALITY_SCORING_MODEL,
        "aggregate_scores": {
            k: Decimal(str(round(v, 4))) for k, v in (aggregate_scores or {}).items()
        },
        "diversity_score": Decimal(str(round(diversity_score, 4))),
        "overall_score": Decimal(str(round(overall_score, 4))),
        "record_scores": _convert_record_scores(record_scores or []),
        "scoring_cost": Decimal(str(round(scoring_cost, 6))),
        "status": status.value,
        "ttl": int(datetime.now(UTC).timestamp() + (90 * 24 * 60 * 60)),
    }
    if error_message is not None:
        item["error_message"] = error_message

    quality_table.put_item(Item=item)


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Score a completed job's output quality.

    Input: {"job_id": str} — from Step Functions or async invocation.
    """
    job_id = event.get("job_id", "")
    if not job_id:
        logger.error(json.dumps({"event": "score_job_missing_job_id"}))
        return {"error": "Missing job_id"}

    logger.info(json.dumps({"event": "score_job_start", "job_id": job_id}))

    # Fetch job
    job_response = jobs_table.get_item(Key={"job_id": job_id})
    job = job_response.get("Item")
    if not job:
        logger.error(json.dumps({"event": "job_not_found", "job_id": job_id}))
        return {"error": "Job not found"}

    if job.get("status") != "COMPLETED":
        logger.warning(
            json.dumps({"event": "job_not_completed", "job_id": job_id, "status": job.get("status")})
        )
        return {"error": f"Job is not COMPLETED (status: {job.get('status')})"}

    # Create PENDING record
    _store_quality_metrics(
        job_id=job_id,
        status=QualityStatus.PENDING,
        total_records=int(job.get("records_generated", 0)),
    )

    # Update to SCORING
    _store_quality_metrics(
        job_id=job_id,
        status=QualityStatus.SCORING,
        total_records=int(job.get("records_generated", 0)),
    )

    try:
        config = job.get("config", {})
        output_format = config.get("output_format", "JSONL")
        template_id = config.get("template_id", "")
        template_version = config.get("template_version", 1)

        # Load export records
        try:
            all_records = _load_export_records(job_id, output_format)
        except Exception as e:
            error_msg = f"Failed to load export file: {sanitize_error_message(str(e))}"
            logger.error(json.dumps({"event": "export_load_error", "job_id": job_id, "error": sanitize_error_message(str(e))}))
            _store_quality_metrics(
                job_id=job_id,
                status=QualityStatus.FAILED,
                total_records=int(job.get("records_generated", 0)),
                error_message=error_msg,
            )
            return {"error": error_msg}

        if not all_records:
            _store_quality_metrics(
                job_id=job_id,
                status=QualityStatus.FAILED,
                total_records=0,
                error_message="Export file is empty",
            )
            return {"error": "Export file is empty"}

        total_records = len(all_records)

        # Sample records
        sample_size = min(QUALITY_SAMPLE_SIZE, total_records)
        if total_records > sample_size:
            sampled_records = random.sample(all_records, sample_size)
        else:
            sampled_records = all_records

        # Fetch template for context
        template_name = "Unknown"
        schema_requirements: list[str] = []
        try:
            tmpl_response = templates_table.get_item(
                Key={"template_id": template_id, "version": int(template_version)}
            )
            tmpl = tmpl_response.get("Item")
            if tmpl:
                template_name = tmpl.get("name", "Unknown")
                schema_requirements = tmpl.get("schema_requirements", [])
        except Exception as e:
            logger.warning(json.dumps({"event": "template_fetch_warning", "error": str(e)}))

        # Score in batches
        all_scores: list[dict[str, Any]] = []
        total_input_tokens = 0
        total_output_tokens = 0
        failed_records = 0

        num_batches = math.ceil(sample_size / QUALITY_BATCH_SIZE)
        for batch_idx in range(num_batches):
            start = batch_idx * QUALITY_BATCH_SIZE
            end = min(start + QUALITY_BATCH_SIZE, sample_size)
            batch_records = sampled_records[start:end]

            prompt = _build_scoring_prompt(batch_records, template_name, schema_requirements, start)

            try:
                scores, input_tokens, output_tokens = _invoke_bedrock_scoring(prompt)
                total_input_tokens += input_tokens
                total_output_tokens += output_tokens

                # Add record_index to each score
                for i, score in enumerate(scores):
                    score["record_index"] = start + i
                    all_scores.append(score)

            except Exception as e:
                logger.error(
                    json.dumps(
                        {
                            "event": "scoring_batch_error",
                            "batch_idx": batch_idx,
                            "error": str(e),
                        }
                    )
                )
                failed_records += len(batch_records)

        # Check failure threshold (>50% failed)
        if failed_records > sample_size * 0.5:
            _store_quality_metrics(
                job_id=job_id,
                status=QualityStatus.FAILED,
                sample_size=sample_size,
                total_records=total_records,
                error_message=f"More than 50% of records failed scoring ({failed_records}/{sample_size})",
            )
            return {"error": "Majority of scoring calls failed"}

        # Compute aggregates
        aggregate_scores: dict[str, float] = {}
        for dim in QUALITY_DIMENSIONS:
            values = [s[dim] for s in all_scores if dim in s]
            if values:
                aggregate_scores[dim] = sum(values) / len(values)

        # Compute diversity from sampled records
        diversity_score = _compute_diversity(sampled_records)

        # Compute overall score
        overall_score = _compute_overall_score(aggregate_scores, diversity_score)

        # Compute cost
        model_id = QUALITY_SCORING_MODEL
        try:
            input_cost = calculate_bedrock_cost(total_input_tokens, model_id, is_input=True)
            output_cost = calculate_bedrock_cost(total_output_tokens, model_id, is_input=False)
            scoring_cost = round(input_cost + output_cost, 6)
        except (ValueError, KeyError):
            scoring_cost = 0.0

        # Format record_scores for storage
        record_scores_items = []
        for s in all_scores:
            record_scores_items.append(
                {
                    "record_index": s.get("record_index", 0),
                    "coherence": float(s.get("coherence", 0)),
                    "relevance": float(s.get("relevance", 0)),
                    "format_compliance": float(s.get("format_compliance", 0)),
                    "detail": s.get("detail", ""),
                }
            )

        # Store completed metrics
        _store_quality_metrics(
            job_id=job_id,
            status=QualityStatus.COMPLETED,
            sample_size=sample_size,
            total_records=total_records,
            aggregate_scores=aggregate_scores,
            diversity_score=diversity_score,
            overall_score=overall_score,
            record_scores=record_scores_items,
            scoring_cost=scoring_cost,
        )

        logger.info(
            json.dumps(
                {
                    "event": "score_job_complete",
                    "job_id": job_id,
                    "overall_score": overall_score,
                    "sample_size": sample_size,
                    "scoring_cost": scoring_cost,
                }
            )
        )

        return {
            "job_id": job_id,
            "overall_score": overall_score,
            "status": "COMPLETED",
        }

    except Exception as e:
        logger.error(
            json.dumps({"event": "score_job_unexpected_error", "job_id": job_id, "error": str(e)}),
            exc_info=True,
        )
        _store_quality_metrics(
            job_id=job_id,
            status=QualityStatus.FAILED,
            total_records=int(job.get("records_generated", 0)),
            error_message=f"Unexpected error: {str(e)}",
        )
        raise
