#!/bin/bash
#
# Plot Palette - Lambda Deployment Script
#
# Uploads packaged Lambda functions to S3 for CloudFormation deployment.
#

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Starting Lambda deployment...${NC}"

# Configuration
REGION=${1:-us-east-1}
BUILD_DIR="build/lambda"

# Validate build directory exists
if [ ! -d "$BUILD_DIR" ]; then
    echo -e "${RED}Error: Build directory not found. Run package-lambdas.sh first.${NC}"
    exit 1
fi

# Check if Lambda code bucket stack exists
STACK_EXISTS=$(aws cloudformation describe-stacks \
    --stack-name lambda-code-bucket \
    --region "$REGION" \
    --query 'Stacks[0].StackStatus' \
    --output text 2>/dev/null || echo "DOES_NOT_EXIST")

if [ "$STACK_EXISTS" == "DOES_NOT_EXIST" ]; then
    echo -e "${YELLOW}Lambda code bucket stack does not exist. Creating...${NC}"

    # Create lambda-code-bucket CloudFormation stack
    aws cloudformation create-stack \
        --stack-name lambda-code-bucket \
        --template-body file://infrastructure/cloudformation/lambda-code-bucket.yaml \
        --region "$REGION"

    echo "Waiting for stack creation to complete..."
    aws cloudformation wait stack-create-complete \
        --stack-name lambda-code-bucket \
        --region "$REGION"

    echo -e "${GREEN}✓ Lambda code bucket created${NC}"
fi

# Get bucket name from CloudFormation outputs
BUCKET=$(aws cloudformation describe-stacks \
    --stack-name lambda-code-bucket \
    --query 'Stacks[0].Outputs[?OutputKey==`BucketName`].OutputValue' \
    --output text \
    --region "$REGION")

if [ -z "$BUCKET" ]; then
    echo -e "${RED}Error: Could not retrieve Lambda code bucket name${NC}"
    exit 1
fi

echo "Using bucket: $BUCKET"
echo ""

# Upload all Lambda ZIPs to S3
UPLOAD_COUNT=0
for zip in "$BUILD_DIR"/*.zip; do
    if [ -f "$zip" ]; then
        lambda_name=$(basename "$zip" .zip)
        echo -e "${GREEN}Uploading ${lambda_name}.zip...${NC}"

        aws s3 cp "$zip" "s3://$BUCKET/lambdas/${lambda_name}.zip" \
            --region "$REGION" \
            --quiet

        echo -e "  ${GREEN}✓ Uploaded to s3://$BUCKET/lambdas/${lambda_name}.zip${NC}"
        UPLOAD_COUNT=$((UPLOAD_COUNT + 1))
    fi
done

# Summary
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Lambda deployment complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "Region: ${YELLOW}$REGION${NC}"
echo -e "Bucket: ${YELLOW}$BUCKET${NC}"
echo -e "Uploaded: ${YELLOW}$UPLOAD_COUNT${NC} Lambda packages"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "  1. Update your CloudFormation templates to reference S3 code:"
echo "     Code:"
echo "       S3Bucket: $BUCKET"
echo "       S3Key: lambdas/<lambda_name>.zip"
echo ""
echo "  2. Deploy/update your API stack:"
echo "     aws cloudformation update-stack --stack-name api-stack ..."
echo ""
