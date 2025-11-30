#!/bin/bash
##############################################################################
# Plot Palette - Nested Stack Deployment Script
#
# End-to-end deployment automation for master CloudFormation stack
##############################################################################

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
STACK_NAME="plot-palette"
ENVIRONMENT="production"
REGION="${AWS_DEFAULT_REGION:-us-east-1}"
MODE=""
SKIP_VALIDATION=false
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CFN_DIR="${SCRIPT_DIR}/../cloudformation"
PARAM_FILE="${SCRIPT_DIR}/../parameters/${ENVIRONMENT}.json"

usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Deploy Plot Palette CloudFormation master stack with nested stacks.

Options:
    --create                Create new stack
    --update                Update existing stack
    --delete                Delete stack
    --stack-name NAME       Stack name (default: plot-palette)
    --environment ENV       Environment: development, staging, production (default: production)
    --region REGION         AWS region (default: ${REGION})
    --skip-validation       Skip parameter validation
    -h, --help              Show this help message

Examples:
    # Create new production stack
    $0 --create --environment production --region us-east-1

    # Update existing stack
    $0 --update --stack-name plot-palette

    # Delete stack
    $0 --delete --stack-name plot-palette-dev

EOF
    exit 0
}

# Parse command-line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --create)
            MODE="create"
            shift
            ;;
        --update)
            MODE="update"
            shift
            ;;
        --delete)
            MODE="delete"
            shift
            ;;
        --stack-name)
            STACK_NAME="$2"
            shift 2
            ;;
        --environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --region)
            REGION="$2"
            shift 2
            ;;
        --skip-validation)
            SKIP_VALIDATION=true
            shift
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo -e "${RED}ERROR: Unknown option: $1${NC}"
            usage
            ;;
    esac
done

# Validate mode
if [ -z "$MODE" ]; then
    echo -e "${RED}ERROR: Must specify --create, --update, or --delete${NC}"
    usage
fi

# Update parameter file path
PARAM_FILE="${SCRIPT_DIR}/../parameters/${ENVIRONMENT}.json"

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║          Plot Palette - Nested Stack Deployment              ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "Mode: $MODE"
echo "Stack: $STACK_NAME"
echo "Environment: $ENVIRONMENT"
echo "Region: $REGION"
echo ""

# Handle delete mode
if [ "$MODE" = "delete" ]; then
    echo -e "${YELLOW}⚠️  WARNING: This will delete the entire stack and all resources${NC}"
    echo ""
    read -p "Are you sure you want to delete stack $STACK_NAME? (yes/no) " -r
    echo
    if [[ ! $REPLY =~ ^yes$ ]]; then
        echo "Deletion cancelled"
        exit 0
    fi

    echo -e "${BLUE}Deleting stack...${NC}"
    aws cloudformation delete-stack \
        --stack-name $STACK_NAME \
        --region $REGION

    echo "Waiting for stack deletion..."
    aws cloudformation wait stack-delete-complete \
        --stack-name $STACK_NAME \
        --region $REGION

    echo ""
    echo -e "${GREEN}✓ Stack deleted successfully${NC}"
    exit 0
fi

# Validate parameters (unless skipped)
if [ "$SKIP_VALIDATION" = false ]; then
    echo -e "${BLUE}Step 1/4: Validating parameters${NC}"
    ${SCRIPT_DIR}/validate-parameters.sh $ENVIRONMENT
    echo ""
fi

# Upload templates
echo -e "${BLUE}Step 2/4: Uploading templates${NC}"
${SCRIPT_DIR}/upload-templates.sh $REGION
echo ""

# Get templates bucket
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
TEMPLATES_BUCKET="plot-palette-cfn-${AWS_ACCOUNT_ID}-${REGION}"

# Check if stack exists
STACK_EXISTS=false
if aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $REGION > /dev/null 2>&1; then
    STACK_EXISTS=true
fi

# Handle create vs update
if [ "$MODE" = "create" ]; then
    if [ "$STACK_EXISTS" = true ]; then
        echo -e "${RED}ERROR: Stack $STACK_NAME already exists${NC}"
        echo "Use --update to update existing stack, or --delete to remove it first"
        exit 1
    fi

    echo -e "${BLUE}Step 3/4: Creating stack${NC}"
    echo "This may take 10-20 minutes..."
    echo ""

    aws cloudformation create-stack \
        --stack-name $STACK_NAME \
        --template-body file://${CFN_DIR}/master-stack.yaml \
        --parameters file://${PARAM_FILE} ParameterKey=TemplatesBucketName,ParameterValue=${TEMPLATES_BUCKET} \
        --tags Key=Environment,Value=${ENVIRONMENT} Key=Project,Value=plot-palette Key=ManagedBy,Value=cloudformation \
        --capabilities CAPABILITY_IAM CAPABILITY_AUTO_EXPAND CAPABILITY_NAMED_IAM \
        --region $REGION

    echo "Waiting for stack creation..."
    aws cloudformation wait stack-create-complete \
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
        echo -e "${RED}ERROR: Stack creation failed${NC}"
        echo ""
        echo "Check CloudFormation console for details:"
        echo "  https://console.aws.amazon.com/cloudformation/home?region=${REGION}#/stacks/stackinfo?stackId=${STACK_NAME}"
        echo ""
        echo "To rollback:"
        echo "  ${SCRIPT_DIR}/rollback-stack.sh $STACK_NAME $REGION"
        exit 1
    fi

elif [ "$MODE" = "update" ]; then
    if [ "$STACK_EXISTS" = false ]; then
        echo -e "${RED}ERROR: Stack $STACK_NAME does not exist${NC}"
        echo "Use --create to create a new stack"
        exit 1
    fi

    echo -e "${BLUE}Step 3/4: Updating stack${NC}"
    echo "Using change sets for safe update..."
    echo ""

    # Use update-stack.sh script
    ${SCRIPT_DIR}/update-stack.sh $STACK_NAME $ENVIRONMENT $REGION

    # Exit after update (update script handles everything)
    exit 0
fi

# Display outputs
echo ""
echo -e "${BLUE}Step 4/4: Retrieving stack outputs${NC}"
echo ""

OUTPUTS=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $REGION \
    --query 'Stacks[0].Outputs' \
    --output json)

echo -e "${GREEN}=== Deployment Complete ===${NC}"
echo ""
echo "$OUTPUTS" | jq -r '.[] | "\(.OutputKey): \(.OutputValue)"'
echo ""

# Extract key outputs
API_ENDPOINT=$(echo "$OUTPUTS" | jq -r '.[] | select(.OutputKey=="ApiEndpoint") | .OutputValue')
FRONTEND_URL=$(echo "$OUTPUTS" | jq -r '.[] | select(.OutputKey=="FrontendUrl") | .OutputValue')
USER_POOL_ID=$(echo "$OUTPUTS" | jq -r '.[] | select(.OutputKey=="UserPoolId") | .OutputValue')
USER_POOL_CLIENT_ID=$(echo "$OUTPUTS" | jq -r '.[] | select(.OutputKey=="UserPoolClientId") | .OutputValue')

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                       Quick Start                             ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "Frontend URL: $FRONTEND_URL"
echo "API Endpoint: $API_ENDPOINT"
echo ""
echo "Authentication:"
echo "  User Pool ID: $USER_POOL_ID"
echo "  Client ID: $USER_POOL_CLIENT_ID"
echo ""
echo "Next steps:"
echo "  1. Access the web application:"
echo "     open $FRONTEND_URL"
echo ""
echo "  2. Or create a test user via CLI:"
echo "     aws cognito-idp sign-up \\"
echo "       --client-id $USER_POOL_CLIENT_ID \\"
echo "       --username test@example.com \\"
echo "       --password TestPassword123! \\"
echo "       --region $REGION"
echo ""
echo "  3. Confirm the user:"
echo "     aws cognito-idp admin-confirm-sign-up \\"
echo "       --user-pool-id $USER_POOL_ID \\"
echo "       --username test@example.com \\"
echo "       --region $REGION"
echo ""
echo -e "${GREEN}✓ Deployment successful!${NC}"
