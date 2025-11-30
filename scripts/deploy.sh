#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"

echo "=============================================="
echo "PLOT PALETTE - SAM DEPLOYMENT"
echo "=============================================="

# ============================================================
# PHASE 1: Load Configuration
# ============================================================
ENV_FILE="$BACKEND_DIR/.env.deploy"

if [[ -f "$ENV_FILE" ]]; then
    echo "[CONFIG] Loading from $ENV_FILE"
    set -a
    source "$ENV_FILE"
    set +a
else
    echo "[CONFIG] No .env.deploy found, will prompt for values"
fi

# ============================================================
# PHASE 2: Interactive Prompts for Missing Values
# ============================================================
prompt_if_missing() {
    local var_name="$1"
    local prompt_text="$2"
    local default_value="${3:-}"

    eval "current_value=\${$var_name:-}"

    if [[ -z "$current_value" ]]; then
        if [[ -n "$default_value" ]]; then
            read -rp "$prompt_text [$default_value]: " input
            input="${input:-$default_value}"
        else
            read -rp "$prompt_text: " input
        fi
        eval "$var_name=\"$input\""
    else
        echo "[SET] $var_name=****"
    fi
}

prompt_if_missing_secret() {
    local var_name="$1"
    local prompt_text="$2"

    eval "current_value=\${$var_name:-}"

    if [[ -z "$current_value" ]]; then
        read -rsp "$prompt_text: " input
        echo ""
        eval "$var_name=\"$input\""
    else
        echo "[SET] $var_name=****"
    fi
}

echo ""
echo "=== Configuration ==="

# Required: AWS Region
prompt_if_missing "AWS_REGION" "AWS Region" "us-east-1"
export AWS_DEFAULT_REGION="$AWS_REGION"

# Required: Environment
prompt_if_missing "ENVIRONMENT" "Environment (dev/staging/prod)" "dev"

# Required: Cognito User Pool ID
prompt_if_missing "COGNITO_USER_POOL_ID" "Cognito User Pool ID"

# Required: Cognito Client ID
prompt_if_missing "COGNITO_CLIENT_ID" "Cognito App Client ID"

# Optional: ECS Configuration
echo ""
echo "=== Optional ECS Configuration (press Enter to skip) ==="
prompt_if_missing "ECS_CLUSTER_NAME" "ECS Cluster Name" ""
prompt_if_missing "TASK_DEFINITION_ARN" "Task Definition ARN" ""
prompt_if_missing "SUBNET_IDS" "Subnet IDs (comma-separated)" ""
prompt_if_missing "SECURITY_GROUP_ID" "Security Group ID" ""

# ============================================================
# PHASE 3: Validate Prerequisites
# ============================================================
echo ""
echo "=== Validating Prerequisites ==="

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    echo "[ERROR] AWS CLI not found. Install from https://aws.amazon.com/cli/"
    exit 1
fi
echo "[OK] AWS CLI installed"

# Check SAM CLI
if ! command -v sam &> /dev/null; then
    echo "[ERROR] SAM CLI not found. Install from https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html"
    exit 1
fi
echo "[OK] SAM CLI installed"

# Check Docker (required for sam build --use-container)
if ! command -v docker &> /dev/null; then
    echo "[WARN] Docker not found. Will build without container."
    USE_CONTAINER=""
else
    if docker info &> /dev/null 2>&1; then
        echo "[OK] Docker available"
        USE_CONTAINER="--use-container"
    else
        echo "[WARN] Docker not running. Will build without container."
        USE_CONTAINER=""
    fi
fi

# Check AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    echo "[ERROR] AWS credentials not configured. Run 'aws configure'"
    exit 1
fi

AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "[OK] AWS Account: $AWS_ACCOUNT_ID"
echo "[OK] Region: $AWS_REGION"

# ============================================================
# PHASE 4: Create/Verify Deployment Bucket
# ============================================================
STACK_NAME="plot-palette-${ENVIRONMENT}"
DEPLOY_BUCKET="sam-deploy-plot-palette-${AWS_REGION}"

echo ""
echo "=== Deployment Bucket ==="

if aws s3api head-bucket --bucket "$DEPLOY_BUCKET" 2>/dev/null; then
    echo "[OK] Bucket exists: $DEPLOY_BUCKET"
else
    echo "[CREATE] Creating bucket: $DEPLOY_BUCKET"
    if [[ "$AWS_REGION" == "us-east-1" ]]; then
        aws s3api create-bucket --bucket "$DEPLOY_BUCKET"
    else
        aws s3api create-bucket --bucket "$DEPLOY_BUCKET" \
            --create-bucket-configuration LocationConstraint="$AWS_REGION"
    fi
    echo "[OK] Bucket created"
fi

# ============================================================
# PHASE 5: Copy Shared Library to Lambda Directories
# ============================================================
echo ""
echo "=== Preparing Lambda Code ==="

SHARED_DIR="$BACKEND_DIR/shared"
LAMBDA_DIRS=(
    "$BACKEND_DIR/lambdas/jobs"
    "$BACKEND_DIR/lambdas/templates"
    "$BACKEND_DIR/lambdas/seed_data"
    "$BACKEND_DIR/lambdas/dashboard"
)

for lambda_dir in "${LAMBDA_DIRS[@]}"; do
    if [[ -d "$lambda_dir" ]]; then
        # Copy shared modules
        cp "$SHARED_DIR"/*.py "$lambda_dir/" 2>/dev/null || true
        echo "[COPY] Shared -> $(basename "$lambda_dir")"
    fi
done

# ============================================================
# PHASE 6: SAM Build
# ============================================================
echo ""
echo "=== Building with SAM ==="

cd "$BACKEND_DIR"

BUILD_CMD="sam build --template template.yaml"
if [[ -n "${USE_CONTAINER:-}" ]]; then
    BUILD_CMD="$BUILD_CMD $USE_CONTAINER"
fi

echo "[RUN] $BUILD_CMD"
$BUILD_CMD

echo "[OK] Build complete"

# ============================================================
# PHASE 7: SAM Deploy
# ============================================================
echo ""
echo "=== Deploying with SAM ==="

PARAM_OVERRIDES="Environment=$ENVIRONMENT"
PARAM_OVERRIDES="$PARAM_OVERRIDES CognitoUserPoolId=$COGNITO_USER_POOL_ID"
PARAM_OVERRIDES="$PARAM_OVERRIDES CognitoClientId=$COGNITO_CLIENT_ID"

if [[ -n "${ECS_CLUSTER_NAME:-}" ]]; then
    PARAM_OVERRIDES="$PARAM_OVERRIDES EcsClusterName=$ECS_CLUSTER_NAME"
fi
if [[ -n "${TASK_DEFINITION_ARN:-}" ]]; then
    PARAM_OVERRIDES="$PARAM_OVERRIDES TaskDefinitionArn=$TASK_DEFINITION_ARN"
fi
if [[ -n "${SUBNET_IDS:-}" ]]; then
    PARAM_OVERRIDES="$PARAM_OVERRIDES SubnetIds=$SUBNET_IDS"
fi
if [[ -n "${SECURITY_GROUP_ID:-}" ]]; then
    PARAM_OVERRIDES="$PARAM_OVERRIDES SecurityGroupId=$SECURITY_GROUP_ID"
fi

sam deploy \
    --stack-name "$STACK_NAME" \
    --s3-bucket "$DEPLOY_BUCKET" \
    --s3-prefix "$STACK_NAME" \
    --capabilities CAPABILITY_IAM CAPABILITY_AUTO_EXPAND \
    --parameter-overrides $PARAM_OVERRIDES \
    --no-confirm-changeset \
    --no-fail-on-empty-changeset

echo "[OK] Deployment complete"

# ============================================================
# PHASE 8: Post-Deploy - Retrieve Outputs
# ============================================================
echo ""
echo "=== Stack Outputs ==="

API_URL=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" \
    --output text)

DATA_BUCKET=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query "Stacks[0].Outputs[?OutputKey=='DataBucketName'].OutputValue" \
    --output text)

echo ""
echo "=============================================="
echo "DEPLOYMENT SUCCESSFUL"
echo "=============================================="
echo ""
echo "API URL:     $API_URL"
echo "Data Bucket: $DATA_BUCKET"
echo "Region:      $AWS_REGION"
echo "Stack:       $STACK_NAME"
echo ""
echo "=== Frontend Configuration ==="
echo ""
echo "Add to frontend/.env.local:"
echo ""
echo "  VITE_API_URL=$API_URL"
echo "  VITE_AWS_REGION=$AWS_REGION"
echo "  VITE_USER_POOL_ID=$COGNITO_USER_POOL_ID"
echo "  VITE_CLIENT_ID=$COGNITO_CLIENT_ID"
echo ""
echo "Or for Expo projects:"
echo ""
echo "  EXPO_PUBLIC_API_GATEWAY_URL=$API_URL"
echo "  EXPO_PUBLIC_AWS_REGION=$AWS_REGION"
echo "  EXPO_PUBLIC_USER_POOL_ID=$COGNITO_USER_POOL_ID"
echo "  EXPO_PUBLIC_CLIENT_ID=$COGNITO_CLIENT_ID"
echo ""
