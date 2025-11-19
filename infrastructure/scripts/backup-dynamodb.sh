#!/bin/bash
##############################################################################
# Plot Palette - DynamoDB Backup Script
#
# Creates on-demand backups of DynamoDB tables before updates
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
BACKUP_NAME="backup-$(date +%Y%m%d-%H%M%S)"

echo -e "${BLUE}=== DynamoDB Backup Process ===${NC}"
echo "Stack: $STACK_NAME"
echo "Region: $REGION"
echo "Backup name: $BACKUP_NAME"
echo ""

# Check if stack exists
if ! aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $REGION > /dev/null 2>&1; then
    echo -e "${RED}ERROR: Stack $STACK_NAME not found in region $REGION${NC}"
    exit 1
fi

# Get nested database stack name
DATABASE_STACK=$(aws cloudformation describe-stack-resources \
    --stack-name $STACK_NAME \
    --region $REGION \
    --query 'StackResources[?LogicalResourceId==`DatabaseStack`].PhysicalResourceId' \
    --output text 2>/dev/null)

if [ -z "$DATABASE_STACK" ]; then
    echo -e "${YELLOW}⚠ WARNING: DatabaseStack not found in master stack${NC}"
    echo "Searching for tables in master stack..."

    # Try to find tables directly
    TABLES=$(aws cloudformation describe-stack-resources \
        --stack-name $STACK_NAME \
        --region $REGION \
        --query 'StackResources[?ResourceType==`AWS::DynamoDB::Table`].PhysicalResourceId' \
        --output text)
else
    # Get tables from database stack
    TABLES=$(aws cloudformation describe-stack-resources \
        --stack-name $DATABASE_STACK \
        --region $REGION \
        --query 'StackResources[?ResourceType==`AWS::DynamoDB::Table`].PhysicalResourceId' \
        --output text)
fi

if [ -z "$TABLES" ]; then
    echo -e "${YELLOW}⚠ No DynamoDB tables found in stack${NC}"
    exit 0
fi

echo "Found tables to backup:"
for TABLE in $TABLES; do
    echo "  - $TABLE"
done
echo ""

# Confirm backup
read -p "Proceed with backup? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Backup cancelled"
    exit 0
fi

echo ""
echo -e "${BLUE}Creating backups...${NC}"

# Track backup status
SUCCESSFUL=0
FAILED=0

for TABLE in $TABLES; do
    echo ""
    echo "Backing up: $TABLE"

    # Create on-demand backup
    if aws dynamodb create-backup \
        --table-name $TABLE \
        --backup-name "${BACKUP_NAME}-${TABLE}" \
        --region $REGION > /dev/null 2>&1; then

        echo -e "${GREEN}✓ Backup created: ${BACKUP_NAME}-${TABLE}${NC}"
        SUCCESSFUL=$((SUCCESSFUL + 1))
    else
        echo -e "${RED}✗ Backup failed for: $TABLE${NC}"
        FAILED=$((FAILED + 1))
    fi
done

echo ""
echo -e "${BLUE}=== Backup Summary ===${NC}"
echo "Successful: $SUCCESSFUL"
echo "Failed: $FAILED"
echo ""

if [ $FAILED -gt 0 ]; then
    echo -e "${YELLOW}⚠ Some backups failed${NC}"
    exit 1
fi

echo -e "${GREEN}✓ All DynamoDB tables backed up successfully${NC}"
echo ""
echo "Backup name: $BACKUP_NAME"
echo ""
echo "To list backups:"
for TABLE in $TABLES; do
    echo "  aws dynamodb list-backups --table-name $TABLE --region $REGION"
done
echo ""
echo "To restore a backup:"
echo "  aws dynamodb restore-table-from-backup \\"
echo "    --target-table-name <new-table-name> \\"
echo "    --backup-arn <backup-arn> \\"
echo "    --region $REGION"
echo ""
echo "To get backup ARN:"
echo "  aws dynamodb list-backups --table-name <table-name> --region $REGION"
echo ""
