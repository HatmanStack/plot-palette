#!/bin/bash
set -e

echo "Starting Plot Palette Worker"
echo "Region: $AWS_REGION"
echo "Cluster: $ECS_CLUSTER_NAME"
echo "Job Table: $JOBS_TABLE_NAME"

# Run worker
exec python worker.py
