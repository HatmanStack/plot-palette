#!/bin/bash
##############################################################################
# Plot Palette - Parameter Validation Script
#
# Validates CloudFormation parameters before deployment
##############################################################################

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

ENVIRONMENT=${1:-production}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARAM_FILE="${SCRIPT_DIR}/../parameters/${ENVIRONMENT}.json"

echo -e "${BLUE}=== Parameter Validation ===${NC}"
echo "Environment: $ENVIRONMENT"
echo "Parameter file: $PARAM_FILE"
echo ""

# Check if parameter file exists
if [ ! -f "$PARAM_FILE" ]; then
    echo -e "${RED}ERROR: Parameter file not found: $PARAM_FILE${NC}"
    exit 1
fi

# Check JSON syntax
echo "Checking JSON syntax..."
if ! jq empty "$PARAM_FILE" 2>/dev/null; then
    echo -e "${RED}ERROR: Invalid JSON syntax in $PARAM_FILE${NC}"
    exit 1
fi
echo -e "${GREEN}✓ JSON syntax valid${NC}"

# Extract parameters (from array format)
ADMIN_EMAIL=$(jq -r '.[] | select(.ParameterKey=="AdminEmail") | .ParameterValue' "$PARAM_FILE")
BUDGET_LIMIT=$(jq -r '.[] | select(.ParameterKey=="InitialBudgetLimit") | .ParameterValue' "$PARAM_FILE")
LOG_RETENTION=$(jq -r '.[] | select(.ParameterKey=="LogRetentionDays") | .ParameterValue' "$PARAM_FILE")
ENV_NAME=$(jq -r '.[] | select(.ParameterKey=="EnvironmentName") | .ParameterValue' "$PARAM_FILE")

# Validate email format
echo "Validating AdminEmail..."
if ! echo "$ADMIN_EMAIL" | grep -E '^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$' > /dev/null; then
    echo -e "${RED}ERROR: Invalid email format: $ADMIN_EMAIL${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Email format valid: $ADMIN_EMAIL${NC}"

# Validate budget limit
echo "Validating InitialBudgetLimit..."
if [ "$BUDGET_LIMIT" -lt 1 ] || [ "$BUDGET_LIMIT" -gt 10000 ]; then
    echo -e "${RED}ERROR: InitialBudgetLimit must be between 1 and 10000, got: $BUDGET_LIMIT${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Budget limit valid: \$$BUDGET_LIMIT${NC}"

# Validate log retention
echo "Validating LogRetentionDays..."
VALID_RETENTION="1 3 5 7 14 30 60 90 120 150 180 365"
if ! echo "$VALID_RETENTION" | grep -w "$LOG_RETENTION" > /dev/null; then
    echo -e "${RED}ERROR: Invalid LogRetentionDays: $LOG_RETENTION${NC}"
    echo "Valid values: $VALID_RETENTION"
    exit 1
fi
echo -e "${GREEN}✓ Log retention valid: $LOG_RETENTION days${NC}"

# Validate environment name
echo "Validating EnvironmentName..."
if [[ ! "$ENV_NAME" =~ ^(development|staging|production)$ ]]; then
    echo -e "${RED}ERROR: Invalid environment name: $ENV_NAME${NC}"
    echo "Valid values: development, staging, production"
    exit 1
fi
echo -e "${GREEN}✓ Environment name valid: $ENV_NAME${NC}"

echo ""
echo -e "${BLUE}Checking AWS environment...${NC}"

# Check AWS credentials
if ! aws sts get-caller-identity > /dev/null 2>&1; then
    echo -e "${RED}ERROR: AWS CLI not configured or credentials invalid${NC}"
    exit 1
fi

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo -e "${GREEN}✓ AWS credentials valid (Account: $ACCOUNT_ID)${NC}"

# Get region
REGION=$(aws configure get region || echo "us-east-1")
echo "Region: $REGION"

# Check Bedrock access (if available)
echo ""
echo -e "${BLUE}Checking Bedrock model access...${NC}"
if aws bedrock list-foundation-models --region $REGION > /dev/null 2>&1; then
    MODELS=$(aws bedrock list-foundation-models --region $REGION --query 'modelSummaries[].modelId' --output text)

    # Check for required models
    REQUIRED_MODELS="anthropic.claude meta.llama3"
    MISSING_MODELS=""

    for model_prefix in $REQUIRED_MODELS; do
        if ! echo "$MODELS" | grep -q "$model_prefix"; then
            MISSING_MODELS="$MISSING_MODELS $model_prefix"
        fi
    done

    if [ -n "$MISSING_MODELS" ]; then
        echo -e "${YELLOW}⚠ WARNING: Some Bedrock models not available in $REGION:${NC}"
        for model in $MISSING_MODELS; do
            echo "  - $model*"
        done
        echo ""
        echo "Enable model access in AWS Bedrock console before deployment:"
        echo "  https://console.aws.amazon.com/bedrock/home?region=${REGION}#/modelaccess"
    else
        echo -e "${GREEN}✓ Required Bedrock models available${NC}"
    fi
else
    echo -e "${YELLOW}⚠ WARNING: Cannot check Bedrock access${NC}"
    echo "Bedrock service may not be available in $REGION"
    echo ""
    echo "Recommended regions for Bedrock:"
    echo "  - us-east-1 (N. Virginia)"
    echo "  - us-west-2 (Oregon)"
    echo "  - eu-west-1 (Ireland)"
fi

echo ""
echo -e "${GREEN}=== Validation Complete ===${NC}"
echo ""
echo "Summary:"
echo "  Environment: $ENV_NAME"
echo "  Admin Email: $ADMIN_EMAIL"
echo "  Budget Limit: \$$BUDGET_LIMIT"
echo "  Log Retention: $LOG_RETENTION days"
echo "  AWS Account: $ACCOUNT_ID"
echo "  Region: $REGION"
echo ""
echo "Next step: Upload templates and deploy"
echo "  ./infrastructure/scripts/upload-templates.sh $REGION"
echo "  ./infrastructure/scripts/deploy-nested.sh --create --environment $ENVIRONMENT --region $REGION"
echo ""
