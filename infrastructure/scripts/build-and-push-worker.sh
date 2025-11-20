#!/bin/bash
set -e

# Configuration
ENV=${ENV:-production}
REGION=${AWS_REGION:-us-east-1}

echo "Building and pushing worker Docker image..."
echo "Environment: $ENV"
echo "Region: $REGION"

# Get ECR repository URI from CloudFormation
ECR_URI=$(aws cloudformation describe-stacks \
  --stack-name plot-palette-compute-${ENV} \
  --region $REGION \
  --query 'Stacks[0].Outputs[?OutputKey==`ECRRepositoryUri`].OutputValue' \
  --output text)

if [ -z "$ECR_URI" ]; then
  echo "Error: Could not retrieve ECR repository URI"
  exit 1
fi

echo "ECR URI: $ECR_URI"

# Login to ECR
echo "Logging in to ECR..."
aws ecr get-login-password --region $REGION | \
  docker login --username AWS --password-stdin $ECR_URI

# Build image
echo "Building Docker image..."
cd backend/ecs_tasks/worker

# Create temporary directory with shared library
mkdir -p temp_build
cp -r ../../shared temp_build/
cp Dockerfile worker.py template_engine.py requirements.txt entrypoint.sh temp_build/

cd temp_build

# Modify Dockerfile to copy from current directory
sed -i 's|COPY ../../shared /app/shared|COPY shared /app/shared|g' Dockerfile

docker build -t plot-palette-worker:latest .

# Tag and push
echo "Tagging image..."
docker tag plot-palette-worker:latest $ECR_URI:latest
docker tag plot-palette-worker:latest $ECR_URI:$(git rev-parse --short HEAD 2>/dev/null || echo "local")

echo "Pushing images to ECR..."
docker push $ECR_URI:latest
docker push $ECR_URI:$(git rev-parse --short HEAD 2>/dev/null || echo "local")

# Cleanup
cd ..
rm -rf temp_build

echo "Successfully pushed to $ECR_URI:latest"
