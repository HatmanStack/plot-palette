#!/bin/bash
##############################################################################
# Plot Palette - Cost Estimation Script
#
# Estimate monthly infrastructure costs for CloudFormation deployment
##############################################################################

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

ENVIRONMENT=${1:-production}

usage() {
    cat << EOF
Usage: $0 [ENVIRONMENT]

Estimate monthly AWS costs for Plot Palette infrastructure.

Arguments:
    ENVIRONMENT    Environment: development, staging, production (default: production)

Examples:
    $0 production
    $0 development

EOF
    exit 0
}

if [[ "$1" == "-h" ]] || [[ "$1" == "--help" ]]; then
    usage
fi

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║          Plot Palette - Cost Estimation                      ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "Environment: $ENVIRONMENT"
echo ""

# Get region
REGION=${AWS_DEFAULT_REGION:-us-east-1}
echo "Region: $REGION"
echo ""

echo -e "${BLUE}=== Fixed Infrastructure Costs (Monthly) ===${NC}"
echo ""

# Fixed costs (regardless of usage)
COGNITO_BASE=0  # Free tier: 50,000 MAUs
DYNAMODB_BASE=0  # On-demand pricing, pay per request
S3_BASE=0  # Pay per GB stored
AMPLIFY_HOSTING=1  # ~$1-2/month for small SPA
API_GATEWAY_BASE=0  # First 1M requests free, then $1/million
VPC_BASE=0  # VPCs, subnets, IGW are free
NAT_GATEWAY=0  # Using public subnets, no NAT gateway

echo "VPC (Subnets, IGW):           \$0.00"
echo "NAT Gateway:                  \$0.00 (using public subnets)"
echo "Cognito User Pool:            \$0.00 (free tier)"
echo "DynamoDB Tables:              \$0.00 (on-demand)"
echo "S3 Buckets:                   \$0.00 (pay per GB)"
echo "Amplify Hosting:              ~\$${AMPLIFY_HOSTING}.00"
echo "API Gateway (HTTP):           \$0.00 (first 1M requests free)"
echo ""

FIXED_TOTAL=$AMPLIFY_HOSTING

echo -e "${GREEN}Fixed monthly cost: \$${FIXED_TOTAL}.00${NC}"
echo ""

echo -e "${BLUE}=== Variable Costs (Usage-Based) ===${NC}"
echo ""

# Variable costs depend on usage
case $ENVIRONMENT in
    development)
        # Development: Light usage
        S3_STORAGE_GB=10
        DYNAMODB_WRITES=100000  # 100K writes/month
        DYNAMODB_READS=500000   # 500K reads/month
        LAMBDA_INVOCATIONS=50000  # 50K invocations/month
        BEDROCK_TOKENS_M=1  # 1M tokens/month
        FARGATE_SPOT_HOURS=10  # 10 hours/month
        ;;
    staging)
        # Staging: Moderate usage
        S3_STORAGE_GB=50
        DYNAMODB_WRITES=500000
        DYNAMODB_READS=2000000
        LAMBDA_INVOCATIONS=200000
        BEDROCK_TOKENS_M=5
        FARGATE_SPOT_HOURS=50
        ;;
    production)
        # Production: Higher usage
        S3_STORAGE_GB=100
        DYNAMODB_WRITES=1000000  # 1M writes/month
        DYNAMODB_READS=5000000   # 5M reads/month
        LAMBDA_INVOCATIONS=500000  # 500K invocations/month
        BEDROCK_TOKENS_M=10  # 10M tokens/month
        FARGATE_SPOT_HOURS=100  # 100 hours/month
        ;;
    *)
        echo -e "${YELLOW}Unknown environment, using production estimates${NC}"
        S3_STORAGE_GB=100
        DYNAMODB_WRITES=1000000
        DYNAMODB_READS=5000000
        LAMBDA_INVOCATIONS=500000
        BEDROCK_TOKENS_M=10
        FARGATE_SPOT_HOURS=100
        ;;
esac

# S3 costs
S3_STORAGE_COST=$(awk "BEGIN {printf \"%.2f\", $S3_STORAGE_GB * 0.023}")
S3_REQUESTS=$(awk "BEGIN {printf \"%.0f\", $DYNAMODB_WRITES / 10}")  # Rough estimate
S3_REQUEST_COST=$(awk "BEGIN {printf \"%.2f\", $S3_REQUESTS / 1000 * 0.005}")
S3_TOTAL=$(awk "BEGIN {printf \"%.2f\", $S3_STORAGE_COST + $S3_REQUEST_COST}")

echo "S3 Storage (${S3_STORAGE_GB}GB):        \$${S3_STORAGE_COST}"
echo "S3 Requests:                  \$${S3_REQUEST_COST}"

# DynamoDB costs
DDB_WRITE_COST=$(awk "BEGIN {printf \"%.2f\", ($DYNAMODB_WRITES / 1000000) * 1.25}")
DDB_READ_COST=$(awk "BEGIN {printf \"%.2f\", ($DYNAMODB_READS / 1000000) * 0.25}")
DDB_TOTAL=$(awk "BEGIN {printf \"%.2f\", $DDB_WRITE_COST + $DDB_READ_COST}")

echo "DynamoDB Writes:              \$${DDB_WRITE_COST}"
echo "DynamoDB Reads:               \$${DDB_READ_COST}"

# Lambda costs (first 1M requests free)
if [ $LAMBDA_INVOCATIONS -gt 1000000 ]; then
    BILLABLE_INVOCATIONS=$((LAMBDA_INVOCATIONS - 1000000))
    LAMBDA_COST=$(awk "BEGIN {printf \"%.2f\", ($BILLABLE_INVOCATIONS / 1000000) * 0.20}")
else
    LAMBDA_COST=0.00
fi
echo "Lambda:                       \$${LAMBDA_COST} ($(($LAMBDA_INVOCATIONS / 1000))K invocations)"

# Bedrock costs (averaged across models)
# Assume mix: 60% cheap (Llama 8B), 40% expensive (Claude)
# Llama 8B: ~$0.30/M input, $0.60/M output
# Claude Sonnet: ~$3.00/M input, $15.00/M output
# Average: ~$2/M tokens (rough estimate)
BEDROCK_COST=$(awk "BEGIN {printf \"%.2f\", $BEDROCK_TOKENS_M * 2.0}")
echo "Bedrock (${BEDROCK_TOKENS_M}M tokens):    \$${BEDROCK_COST} (model mix estimate)"

# ECS Fargate Spot costs
# vCPU: $0.01334/hour, Memory: $0.00146/GB-hour (Spot pricing, ~70% discount)
# Assuming 1 vCPU, 2GB task
FARGATE_VCPU_COST=$(awk "BEGIN {printf \"%.2f\", $FARGATE_SPOT_HOURS * 0.01334}")
FARGATE_MEM_COST=$(awk "BEGIN {printf \"%.2f\", $FARGATE_SPOT_HOURS * 2 * 0.00146}")
FARGATE_TOTAL=$(awk "BEGIN {printf \"%.2f\", $FARGATE_VCPU_COST + $FARGATE_MEM_COST}")
echo "Fargate Spot (${FARGATE_SPOT_HOURS}hrs):      \$${FARGATE_TOTAL}"

# CloudWatch Logs (rough estimate)
CLOUDWATCH_COST=2.00
echo "CloudWatch Logs:              \$${CLOUDWATCH_COST}"

# Data Transfer (rough estimate)
DATA_TRANSFER_COST=1.00
echo "Data Transfer:                \$${DATA_TRANSFER_COST}"

echo ""

# Calculate total variable cost
VARIABLE_TOTAL=$(awk "BEGIN {printf \"%.2f\", $S3_TOTAL + $DDB_TOTAL + $LAMBDA_COST + $BEDROCK_COST + $FARGATE_TOTAL + $CLOUDWATCH_COST + $DATA_TRANSFER_COST}")

echo -e "${GREEN}Variable monthly cost: \$${VARIABLE_TOTAL}${NC}"
echo ""

# Total cost
TOTAL_COST=$(awk "BEGIN {printf \"%.2f\", $FIXED_TOTAL + $VARIABLE_TOTAL}")

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                   Total Estimated Cost                        ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}Estimated monthly cost: \$${TOTAL_COST}${NC}"
echo ""

# Cost breakdown by category
echo -e "${BLUE}=== Cost Breakdown ===${NC}"
echo ""
echo "Compute (Fargate):            $(awk "BEGIN {printf \"%.0f%%\", ($FARGATE_TOTAL / $TOTAL_COST) * 100}")"
echo "AI/ML (Bedrock):              $(awk "BEGIN {printf \"%.0f%%\", ($BEDROCK_COST / $TOTAL_COST) * 100}")"
echo "Database (DynamoDB):          $(awk "BEGIN {printf \"%.0f%%\", ($DDB_TOTAL / $TOTAL_COST) * 100}")"
echo "Storage (S3):                 $(awk "BEGIN {printf \"%.0f%%\", ($S3_TOTAL / $TOTAL_COST) * 100}")"
echo "Other (Amplify, logs, etc):   $(awk "BEGIN {printf \"%.0f%%\", (($AMPLIFY_HOSTING + $CLOUDWATCH_COST + $DATA_TRANSFER_COST + $LAMBDA_COST) / $TOTAL_COST) * 100}")"
echo ""

# Recommendations
echo -e "${BLUE}=== Cost Optimization Tips ===${NC}"
echo ""
echo "1. Use Fargate Spot (70% savings vs on-demand) - ✓ Enabled"
echo "2. Smart model routing (cheaper models for simple tasks) - Implement in templates"
echo "3. Hard budget limits prevent runaway costs - Set via InitialBudgetLimit parameter"
echo "4. S3 Lifecycle to Glacier after 3 days (90% storage savings) - ✓ Configured"
echo "5. DynamoDB on-demand pricing (no wasted provisioned capacity) - ✓ Enabled"
echo ""

# Warning for high Bedrock usage
if [ $BEDROCK_TOKENS_M -gt 20 ]; then
    echo -e "${YELLOW}⚠ WARNING: High Bedrock token usage detected${NC}"
    echo "  Consider using cheaper models (Llama 8B) for simple tasks"
    echo "  Current estimate assumes model mix, actual costs may vary"
    echo ""
fi

echo "Note: This is an estimate based on typical usage patterns."
echo "Actual costs will vary based on your specific usage."
echo ""
echo "To track real-time costs:"
echo "  - Enable AWS Cost Explorer"
echo "  - Set up AWS Budgets (see infrastructure/cloudformation/budget-stack.yaml)"
echo "  - Monitor DynamoDB Cost Tracking table in deployed stack"
echo ""
