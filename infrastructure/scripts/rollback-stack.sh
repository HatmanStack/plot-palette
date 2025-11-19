#!/bin/bash
##############################################################################
# Plot Palette - Stack Rollback Script
#
# Rollback failed CloudFormation stack updates
##############################################################################

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

STACK_NAME=${1:-plot-palette}
REGION=${2:-us-east-1}

echo -e "${BLUE}=== Stack Rollback Process ===${NC}"
echo "Stack: $STACK_NAME"
echo "Region: $REGION"
echo ""

# Check stack status
if ! aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $REGION > /dev/null 2>&1; then
    echo -e "${RED}ERROR: Stack $STACK_NAME not found${NC}"
    exit 1
fi

STATUS=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $REGION \
    --query 'Stacks[0].StackStatus' \
    --output text)

echo "Current status: $STATUS"
echo ""

# Check if rollback is possible
if [[ "$STATUS" != *"FAILED"* ]] && [[ "$STATUS" != "UPDATE_ROLLBACK_"* ]]; then
    echo -e "${YELLOW}Stack is not in a failed state${NC}"
    echo "Current status: $STATUS"
    echo ""
    echo "Rollback is only possible after:"
    echo "  - UPDATE_FAILED"
    echo "  - CREATE_FAILED"
    echo "  - UPDATE_ROLLBACK_FAILED"
    echo ""

    if [[ "$STATUS" == "UPDATE_COMPLETE" ]] || [[ "$STATUS" == "CREATE_COMPLETE" ]]; then
        echo -e "${GREEN}Stack is in a healthy state. No rollback needed.${NC}"
    fi

    exit 1
fi

# Show recent events
echo -e "${BLUE}Recent stack events (last 10):${NC}"
aws cloudformation describe-stack-events \
    --stack-name $STACK_NAME \
    --region $REGION \
    --max-items 10 \
    --query 'StackEvents[].{Time:Timestamp,Status:ResourceStatus,Resource:LogicalResourceId,Reason:ResourceStatusReason}' \
    --output table

echo ""

# Confirm rollback
echo -e "${YELLOW}⚠️  WARNING: This will rollback the stack to its previous state${NC}"
echo ""
read -p "Are you sure you want to rollback the stack? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Rollback cancelled"
    exit 0
fi

# Perform rollback
echo ""
echo -e "${BLUE}Initiating rollback...${NC}"

if [[ "$STATUS" == "UPDATE_ROLLBACK_FAILED" ]]; then
    # Continue rollback for failed rollback
    echo "Continuing failed rollback..."

    aws cloudformation continue-update-rollback \
        --stack-name $STACK_NAME \
        --region $REGION

    echo "Waiting for rollback to complete..."
    aws cloudformation wait stack-rollback-complete \
        --stack-name $STACK_NAME \
        --region $REGION 2>&1 | while read line; do
            if echo "$line" | grep -q "error\|failed"; then
                echo -e "${RED}$line${NC}"
            else
                echo "$line"
            fi
        done

elif [[ "$STATUS" == "UPDATE_FAILED" ]]; then
    # CloudFormation automatically rolls back on UPDATE_FAILED
    echo "Stack will automatically rollback to previous state..."
    echo "Waiting for rollback to complete..."

    aws cloudformation wait stack-update-complete \
        --stack-name $STACK_NAME \
        --region $REGION 2>&1 | while read line; do
            if echo "$line" | grep -q "error\|failed"; then
                echo -e "${RED}$line${NC}"
            else
                echo "$line"
            fi
        done || {
        # If wait fails, it might be because it's in ROLLBACK_COMPLETE
        FINAL_STATUS=$(aws cloudformation describe-stacks \
            --stack-name $STACK_NAME \
            --region $REGION \
            --query 'Stacks[0].StackStatus' \
            --output text)

        if [[ "$FINAL_STATUS" == "UPDATE_ROLLBACK_COMPLETE" ]]; then
            echo -e "${GREEN}✓ Rollback completed${NC}"
        else
            echo -e "${RED}ERROR: Rollback ended in unexpected state: $FINAL_STATUS${NC}"
            exit 1
        fi
    }

elif [[ "$STATUS" == "CREATE_FAILED" ]]; then
    echo -e "${YELLOW}Stack creation failed. Deleting stack...${NC}"

    aws cloudformation delete-stack \
        --stack-name $STACK_NAME \
        --region $REGION

    echo "Waiting for stack deletion..."
    aws cloudformation wait stack-delete-complete \
        --stack-name $STACK_NAME \
        --region $REGION

    echo -e "${GREEN}✓ Failed stack deleted${NC}"
    exit 0

else
    echo -e "${RED}ERROR: Unexpected status: $STATUS${NC}"
    echo "Manual intervention may be required"
    echo ""
    echo "Check CloudFormation console:"
    echo "  https://console.aws.amazon.com/cloudformation/home?region=${REGION}#/stacks/stackinfo?stackId=${STACK_NAME}"
    exit 1
fi

if [ $? -ne 0 ]; then
    echo ""
    echo -e "${RED}ERROR: Rollback failed or timed out${NC}"
    echo ""
    echo "Check CloudFormation console for details:"
    echo "  https://console.aws.amazon.com/cloudformation/home?region=${REGION}#/stacks/stackinfo?stackId=${STACK_NAME}"
    echo ""
    echo "You may need to:"
    echo "  1. Continue rollback from console"
    echo "  2. Skip resources that can't be rolled back"
    echo "  3. Manually delete the stack"
    exit 1
fi

echo ""
echo -e "${GREEN}=== Stack Rolled Back Successfully ===${NC}"
echo ""
echo "Current outputs:"
aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $REGION \
    --query 'Stacks[0].Outputs' \
    --output table 2>/dev/null || echo "(No outputs available)"

echo ""
echo -e "${GREEN}✓ Rollback complete${NC}"
