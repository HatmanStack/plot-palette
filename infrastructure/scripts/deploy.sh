#!/bin/bash

##############################################################################
# Plot Palette - CloudFormation Stack Deployment Script
#
# This script deploys all Phase 1 infrastructure stacks in the correct order
# with proper dependency handling and output passing between stacks.
##############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
REGION="${AWS_DEFAULT_REGION:-us-east-1}"
PROFILE="${AWS_PROFILE:-default}"
ENVIRONMENT="production"
DELETE_MODE=false
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
CFN_DIR="${PROJECT_ROOT}/infrastructure/cloudformation"
OUTPUTS_FILE="${SCRIPT_DIR}/outputs.json"
LOG_FILE="${SCRIPT_DIR}/deployment.log"

##############################################################################
# Helper Functions
##############################################################################

log() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${BLUE}[${timestamp}]${NC} $1" | tee -a "${LOG_FILE}"
}

log_success() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${GREEN}[${timestamp}] ✓${NC} $1" | tee -a "${LOG_FILE}"
}

log_error() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${RED}[${timestamp}] ✗${NC} $1" | tee -a "${LOG_FILE}"
}

log_warning() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${YELLOW}[${timestamp}] ⚠${NC} $1" | tee -a "${LOG_FILE}"
}

usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Deploy Plot Palette CloudFormation infrastructure stacks.

Options:
    --region REGION         AWS region (default: ${REGION})
    --profile PROFILE       AWS CLI profile (default: ${PROFILE})
    --environment ENV       Environment name: development, staging, production (default: ${ENVIRONMENT})
    --delete                Delete all stacks instead of creating them
    -h, --help              Show this help message

Examples:
    # Deploy to production in us-east-1
    $0 --region us-east-1 --environment production

    # Deploy to development with specific profile
    $0 --profile dev-account --environment development

    # Delete all stacks
    $0 --delete --environment test

EOF
    exit 0
}

check_prerequisites() {
    log "Checking prerequisites..."

    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI not found. Please install it: https://aws.amazon.com/cli/"
        exit 1
    fi

    # Check jq
    if ! command -v jq &> /dev/null; then
        log_error "jq not found. Please install it: https://stedolan.github.io/jq/"
        exit 1
    fi

    # Check AWS credentials
    if ! aws sts get-caller-identity --profile "${PROFILE}" --region "${REGION}" &> /dev/null; then
        log_error "AWS credentials not configured or invalid for profile: ${PROFILE}"
        exit 1
    fi

    # Check CloudFormation templates exist
    local templates=("network-stack.yaml" "storage-stack.yaml" "database-stack.yaml" "iam-stack.yaml")
    for template in "${templates[@]}"; do
        if [[ ! -f "${CFN_DIR}/${template}" ]]; then
            log_error "Template not found: ${CFN_DIR}/${template}"
            exit 1
        fi
    done

    log_success "Prerequisites check passed"
}

stack_exists() {
    local stack_name=$1
    aws cloudformation describe-stacks \
        --stack-name "${stack_name}" \
        --profile "${PROFILE}" \
        --region "${REGION}" \
        &> /dev/null
    return $?
}

get_stack_output() {
    local stack_name=$1
    local output_key=$2

    aws cloudformation describe-stacks \
        --stack-name "${stack_name}" \
        --profile "${PROFILE}" \
        --region "${REGION}" \
        --query "Stacks[0].Outputs[?OutputKey=='${output_key}'].OutputValue" \
        --output text
}

deploy_stack() {
    local stack_name=$1
    local template_file=$2
    shift 2
    local parameters=("$@")

    log "Deploying stack: ${stack_name}..."

    # Build parameter overrides
    local param_overrides=""
    for param in "${parameters[@]}"; do
        param_overrides="${param_overrides} ${param}"
    done

    # Deploy stack
    aws cloudformation deploy \
        --stack-name "${stack_name}" \
        --template-file "${template_file}" \
        --parameter-overrides EnvironmentName="${ENVIRONMENT}" ${param_overrides} \
        --capabilities CAPABILITY_NAMED_IAM \
        --profile "${PROFILE}" \
        --region "${REGION}" \
        --no-fail-on-empty-changeset \
        2>&1 | tee -a "${LOG_FILE}"

    if [[ ${PIPESTATUS[0]} -eq 0 ]]; then
        log_success "Stack ${stack_name} deployed successfully"

        # Save outputs to JSON
        aws cloudformation describe-stacks \
            --stack-name "${stack_name}" \
            --profile "${PROFILE}" \
            --region "${REGION}" \
            --query 'Stacks[0].Outputs' \
            > "${OUTPUTS_FILE}.tmp.${stack_name}"

        return 0
    else
        log_error "Failed to deploy stack: ${stack_name}"
        return 1
    fi
}

delete_stack() {
    local stack_name=$1

    if stack_exists "${stack_name}"; then
        log "Deleting stack: ${stack_name}..."

        aws cloudformation delete-stack \
            --stack-name "${stack_name}" \
            --profile "${PROFILE}" \
            --region "${REGION}"

        aws cloudformation wait stack-delete-complete \
            --stack-name "${stack_name}" \
            --profile "${PROFILE}" \
            --region "${REGION}" \
            2>&1 | tee -a "${LOG_FILE}"

        if [[ ${PIPESTATUS[0]} -eq 0 ]]; then
            log_success "Stack ${stack_name} deleted successfully"
        else
            log_error "Failed to delete stack: ${stack_name}"
            return 1
        fi
    else
        log_warning "Stack ${stack_name} does not exist, skipping deletion"
    fi
}

deploy_all_stacks() {
    log "Starting deployment to ${REGION} (environment: ${ENVIRONMENT})..."

    # Initialize outputs file
    echo "{}" > "${OUTPUTS_FILE}"

    # Deploy Network Stack
    local network_stack="plot-palette-network-${ENVIRONMENT}"
    deploy_stack "${network_stack}" "${CFN_DIR}/network-stack.yaml" || exit 1

    # Deploy Storage Stack
    local storage_stack="plot-palette-storage-${ENVIRONMENT}"
    deploy_stack "${storage_stack}" "${CFN_DIR}/storage-stack.yaml" || exit 1

    # Get storage stack outputs for IAM stack
    local bucket_name=$(get_stack_output "${storage_stack}" "BucketName")
    log "Retrieved S3 bucket name: ${bucket_name}"

    # Deploy Database Stack
    local database_stack="plot-palette-database-${ENVIRONMENT}"
    deploy_stack "${database_stack}" "${CFN_DIR}/database-stack.yaml" || exit 1

    # Get database stack outputs for IAM stack
    local jobs_table_arn=$(get_stack_output "${database_stack}" "JobsTableArn")
    local queue_table_arn=$(get_stack_output "${database_stack}" "QueueTableArn")
    local templates_table_arn=$(get_stack_output "${database_stack}" "TemplatesTableArn")
    local costtracking_table_arn=$(get_stack_output "${database_stack}" "CostTrackingTableArn")

    log "Retrieved DynamoDB table ARNs"

    # Deploy IAM Stack
    local iam_stack="plot-palette-iam-${ENVIRONMENT}"
    deploy_stack "${iam_stack}" "${CFN_DIR}/iam-stack.yaml" \
        "S3BucketName=${bucket_name}" \
        "JobsTableArn=${jobs_table_arn}" \
        "QueueTableArn=${queue_table_arn}" \
        "TemplatesTableArn=${templates_table_arn}" \
        "CostTrackingTableArn=${costtracking_table_arn}" \
        || exit 1

    # Consolidate all outputs
    log "Consolidating stack outputs..."
    {
        echo "{"
        echo "  \"Region\": \"${REGION}\","
        echo "  \"Environment\": \"${ENVIRONMENT}\","
        echo "  \"Timestamp\": \"$(date -Iseconds)\","
        echo "  \"Stacks\": {"

        local first=true
        for stack in "${network_stack}" "${storage_stack}" "${database_stack}" "${iam_stack}"; do
            if [[ "${first}" == false ]]; then
                echo ","
            fi
            first=false

            echo -n "    \"${stack}\": "
            cat "${OUTPUTS_FILE}.tmp.${stack}"
        done

        echo ""
        echo "  }"
        echo "}"
    } > "${OUTPUTS_FILE}"

    # Clean up temporary files
    rm -f "${OUTPUTS_FILE}.tmp."*

    log_success "All stacks deployed successfully!"
    log "Outputs saved to: ${OUTPUTS_FILE}"
}

delete_all_stacks() {
    log "Starting deletion of all stacks (environment: ${ENVIRONMENT})..."

    # Delete in reverse order
    local iam_stack="plot-palette-iam-${ENVIRONMENT}"
    local database_stack="plot-palette-database-${ENVIRONMENT}"
    local storage_stack="plot-palette-storage-${ENVIRONMENT}"
    local network_stack="plot-palette-network-${ENVIRONMENT}"

    delete_stack "${iam_stack}"
    delete_stack "${database_stack}"
    delete_stack "${storage_stack}"
    delete_stack "${network_stack}"

    log_success "All stacks deleted successfully!"
}

##############################################################################
# Main Script
##############################################################################

# Parse command-line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --region)
            REGION="$2"
            shift 2
            ;;
        --profile)
            PROFILE="$2"
            shift 2
            ;;
        --environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --delete)
            DELETE_MODE=true
            shift
            ;;
        -h|--help)
            usage
            ;;
        *)
            log_error "Unknown option: $1"
            usage
            ;;
    esac
done

# Validate environment
if [[ ! "${ENVIRONMENT}" =~ ^(development|staging|production)$ ]]; then
    log_error "Invalid environment: ${ENVIRONMENT}. Must be development, staging, or production."
    exit 1
fi

# Initialize log file
echo "=== Plot Palette Deployment - $(date -Iseconds) ===" > "${LOG_FILE}"

# Run prerequisites check
check_prerequisites

# Execute deployment or deletion
if [[ "${DELETE_MODE}" == true ]]; then
    delete_all_stacks
else
    deploy_all_stacks
fi

log_success "Script completed successfully!"
exit 0
