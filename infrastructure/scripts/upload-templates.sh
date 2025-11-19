#!/bin/bash
##############################################################################
# Plot Palette - CloudFormation Template Upload Script
#
# Uploads all nested stack templates to S3 bucket for master stack deployment
##############################################################################

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

REGION=${1:-us-east-1}
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
BUCKET_NAME="plot-palette-cfn-${AWS_ACCOUNT_ID}-${REGION}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CFN_DIR="${SCRIPT_DIR}/../cloudformation"

echo -e "${BLUE}=== CloudFormation Template Upload ===${NC}"
echo "Region: $REGION"
echo "Bucket: $BUCKET_NAME"
echo ""

# Create templates bucket if doesn't exist
if ! aws s3 ls s3://$BUCKET_NAME --region $REGION 2>/dev/null; then
    echo -e "${YELLOW}Creating S3 bucket: $BUCKET_NAME${NC}"

    if [ "$REGION" = "us-east-1" ]; then
        aws s3 mb s3://$BUCKET_NAME
    else
        aws s3 mb s3://$BUCKET_NAME --region $REGION
    fi

    # Enable versioning
    echo "Enabling versioning..."
    aws s3api put-bucket-versioning \
        --bucket $BUCKET_NAME \
        --versioning-configuration Status=Enabled \
        --region $REGION

    # Block public access
    echo "Configuring public access block..."
    aws s3api put-public-access-block \
        --bucket $BUCKET_NAME \
        --public-access-block-configuration \
        "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true" \
        --region $REGION

    # Add bucket tagging
    aws s3api put-bucket-tagging \
        --bucket $BUCKET_NAME \
        --tagging 'TagSet=[{Key=Project,Value=plot-palette},{Key=Purpose,Value=CloudFormation}]' \
        --region $REGION

    echo -e "${GREEN}✓ Bucket created successfully${NC}"
else
    echo -e "${GREEN}✓ Bucket already exists${NC}"
fi

echo ""
echo -e "${BLUE}Uploading nested templates...${NC}"

# List of templates to upload (exclude master stack)
TEMPLATES=(
    "network-stack.yaml"
    "storage-stack.yaml"
    "database-stack.yaml"
    "iam-stack.yaml"
    "auth-stack.yaml"
    "api-stack.yaml"
    "compute-stack.yaml"
    "frontend-stack.yaml"
)

# Upload each template
UPLOADED=0
for TEMPLATE in "${TEMPLATES[@]}"; do
    TEMPLATE_PATH="${CFN_DIR}/${TEMPLATE}"

    if [ ! -f "$TEMPLATE_PATH" ]; then
        echo -e "${YELLOW}⚠ Template not found, skipping: $TEMPLATE${NC}"
        continue
    fi

    echo "  Uploading: $TEMPLATE"

    aws s3 cp "$TEMPLATE_PATH" "s3://$BUCKET_NAME/$TEMPLATE" \
        --region $REGION \
        --metadata "uploaded-at=$(date -Iseconds)" \
        --quiet

    UPLOADED=$((UPLOADED + 1))
done

echo -e "${GREEN}✓ Uploaded $UPLOADED templates${NC}"
echo ""

# Validate templates
echo -e "${BLUE}Validating templates...${NC}"

VALIDATED=0
for TEMPLATE in "${TEMPLATES[@]}"; do
    TEMPLATE_PATH="${CFN_DIR}/${TEMPLATE}"

    if [ ! -f "$TEMPLATE_PATH" ]; then
        continue
    fi

    echo "  Validating: $TEMPLATE"

    if aws cloudformation validate-template \
        --template-body "file://$TEMPLATE_PATH" \
        --region $REGION > /dev/null 2>&1; then
        VALIDATED=$((VALIDATED + 1))
    else
        echo -e "${RED}✗ Validation failed: $TEMPLATE${NC}"
        exit 1
    fi
done

echo -e "${GREEN}✓ All $VALIDATED templates validated${NC}"
echo ""

# Validate master stack
echo -e "${BLUE}Validating master stack...${NC}"
MASTER_TEMPLATE="${CFN_DIR}/master-stack.yaml"

if [ -f "$MASTER_TEMPLATE" ]; then
    if aws cloudformation validate-template \
        --template-body "file://$MASTER_TEMPLATE" \
        --region $REGION > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Master stack validation passed${NC}"
    else
        echo -e "${RED}✗ Master stack validation failed${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}⚠ Master stack not found at: $MASTER_TEMPLATE${NC}"
fi

echo ""
echo -e "${GREEN}=== Upload Complete ===${NC}"
echo "Templates bucket: s3://$BUCKET_NAME/"
echo "Region: $REGION"
echo ""
echo "Next step: Deploy master stack"
echo "  ./infrastructure/scripts/deploy-nested.sh --create --environment production --region $REGION"
echo ""
