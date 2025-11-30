#!/bin/bash
##############################################################################
# Plot Palette - Stack Update Script
#
# Safely update CloudFormation stack using change sets
##############################################################################

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

STACK_NAME=${1:-plot-palette}
ENVIRONMENT=${2:-production}
REGION=${3:-us-east-1}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CFN_DIR="${SCRIPT_DIR}/../cloudformation"
PARAM_FILE="${SCRIPT_DIR}/../parameters/${ENVIRONMENT}.json"

echo -e "${BLUE}=== Stack Update Process ===${NC}"
echo "Stack: $STACK_NAME"
echo "Environment: $ENVIRONMENT"
echo "Region: $REGION"
echo ""

# Validate parameters
echo -e "${BLUE}Validating parameters...${NC}"
${SCRIPT_DIR}/validate-parameters.sh $ENVIRONMENT

# Upload latest templates
echo ""
echo -e "${BLUE}Uploading latest templates...${NC}"
${SCRIPT_DIR}/upload-templates.sh $REGION

# Get templates bucket
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
TEMPLATES_BUCKET="plot-palette-cfn-${AWS_ACCOUNT_ID}-${REGION}"

# Create change set
CHANGE_SET_NAME="update-$(date +%Y%m%d-%H%M%S)"
echo ""
echo -e "${BLUE}Creating change set: $CHANGE_SET_NAME${NC}"

aws cloudformation create-change-set \
    --stack-name $STACK_NAME \
    --change-set-name $CHANGE_SET_NAME \
    --template-body file://${CFN_DIR}/master-stack.yaml \
    --parameters file://${PARAM_FILE} ParameterKey=TemplatesBucketName,ParameterValue=${TEMPLATES_BUCKET} \
    --tags Key=Environment,Value=${ENVIRONMENT} Key=Project,Value=plot-palette Key=ManagedBy,Value=cloudformation \
    --capabilities CAPABILITY_IAM CAPABILITY_AUTO_EXPAND CAPABILITY_NAMED_IAM \
    --region $REGION

echo "Waiting for change set creation..."
aws cloudformation wait change-set-create-complete \
    --change-set-name $CHANGE_SET_NAME \
    --stack-name $STACK_NAME \
    --region $REGION 2>&1 | while read line; do
        if echo "$line" | grep -q "error\|failed"; then
            echo -e "${RED}$line${NC}"
        else
            echo "$line"
        fi
    done

if [ ${PIPESTATUS[0]} -ne 0 ]; then
    echo -e "${RED}ERROR: Change set creation failed${NC}"
    echo ""
    echo "Checking for errors..."
    aws cloudformation describe-change-set \
        --change-set-name $CHANGE_SET_NAME \
        --stack-name $STACK_NAME \
        --region $REGION \
        --query 'StatusReason' \
        --output text

    # Delete failed change set
    aws cloudformation delete-change-set \
        --change-set-name $CHANGE_SET_NAME \
        --stack-name $STACK_NAME \
        --region $REGION 2>/dev/null || true

    exit 1
fi

# Display changes
echo ""
echo -e "${BLUE}=== Proposed Changes ===${NC}"
aws cloudformation describe-change-set \
    --change-set-name $CHANGE_SET_NAME \
    --stack-name $STACK_NAME \
    --region $REGION \
    --query 'Changes[].{Action:ResourceChange.Action,Resource:ResourceChange.LogicalResourceId,Type:ResourceChange.ResourceType,Replacement:ResourceChange.Replacement}' \
    --output table

# Check for data-impacting changes
CRITICAL_CHANGES=$(aws cloudformation describe-change-set \
    --change-set-name $CHANGE_SET_NAME \
    --stack-name $STACK_NAME \
    --region $REGION \
    --query 'Changes[?ResourceChange.ResourceType==`AWS::DynamoDB::Table` && ResourceChange.Replacement==`True`].ResourceChange.LogicalResourceId' \
    --output text)

if [ -n "$CRITICAL_CHANGES" ]; then
    echo ""
    echo -e "${RED}⚠️  WARNING: The following DynamoDB tables will be replaced:${NC}"
    echo "$CRITICAL_CHANGES"
    echo ""
    echo -e "${RED}This will result in DATA LOSS unless backed up!${NC}"
    echo ""
    read -p "Do you want to backup DynamoDB tables first? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo ""
        ${SCRIPT_DIR}/backup-dynamodb.sh $STACK_NAME $REGION
        echo ""
    fi
fi

# Check for no changes
CHANGE_COUNT=$(aws cloudformation describe-change-set \
    --change-set-name $CHANGE_SET_NAME \
    --stack-name $STACK_NAME \
    --region $REGION \
    --query 'length(Changes)' \
    --output text)

if [ "$CHANGE_COUNT" = "0" ]; then
    echo ""
    echo -e "${YELLOW}No changes detected. Change set is empty.${NC}"
    echo "Deleting change set..."
    aws cloudformation delete-change-set \
        --change-set-name $CHANGE_SET_NAME \
        --stack-name $STACK_NAME \
        --region $REGION
    echo -e "${GREEN}✓ Stack is already up to date${NC}"
    exit 0
fi

# Confirm execution
echo ""
read -p "Execute this change set? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborting. Change set not executed."
    echo ""
    echo "To delete the change set:"
    echo "  aws cloudformation delete-change-set --change-set-name $CHANGE_SET_NAME --stack-name $STACK_NAME --region $REGION"
    echo ""
    echo "To execute later:"
    echo "  aws cloudformation execute-change-set --change-set-name $CHANGE_SET_NAME --stack-name $STACK_NAME --region $REGION"
    exit 1
fi

# Execute change set
echo ""
echo -e "${BLUE}Executing change set...${NC}"
aws cloudformation execute-change-set \
    --change-set-name $CHANGE_SET_NAME \
    --stack-name $STACK_NAME \
    --region $REGION

echo "Waiting for stack update to complete..."
echo "(This may take several minutes...)"
echo ""

aws cloudformation wait stack-update-complete \
    --stack-name $STACK_NAME \
    --region $REGION 2>&1 | while read line; do
        if echo "$line" | grep -q "error\|failed"; then
            echo -e "${RED}$line${NC}"
        else
            echo "$line"
        fi
    done

if [ ${PIPESTATUS[0]} -ne 0 ]; then
    echo ""
    echo -e "${RED}ERROR: Stack update failed!${NC}"
    echo ""
    echo "Check CloudFormation console for details:"
    echo "  https://console.aws.amazon.com/cloudformation/home?region=${REGION}#/stacks/stackinfo?stackId=${STACK_NAME}"
    echo ""
    echo "To rollback:"
    echo "  ${SCRIPT_DIR}/rollback-stack.sh $STACK_NAME $REGION"
    exit 1
fi

echo ""
echo -e "${GREEN}=== Stack Update Completed Successfully ===${NC}"
echo ""
echo "Updated outputs:"
aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $REGION \
    --query 'Stacks[0].Outputs' \
    --output table

echo ""
echo -e "${GREEN}✓ Update complete${NC}"
