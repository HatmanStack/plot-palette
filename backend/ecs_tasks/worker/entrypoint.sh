#!/bin/bash
set -e

echo "Starting Plot Palette Worker"
echo "Region: $AWS_REGION"
echo "Cluster: $ECS_CLUSTER_NAME"
echo "Job Table: $JOBS_TABLE_NAME"

# Trap SIGTERM and forward to child process
trap 'kill -TERM $PID' TERM

python worker.py &
PID=$!
wait $PID
EXIT_CODE=$?

# Exit with the child's exit code
# 0 = job completed successfully
# 1 = job failed (unrecoverable)
# 143 = killed by SIGTERM (Spot interruption)
exit $EXIT_CODE
