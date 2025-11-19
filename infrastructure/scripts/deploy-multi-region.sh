#!/bin/bash
##############################################################################
# Plot Palette - Multi-Region Deployment Script
#
# Deploy CloudFormation stacks across multiple AWS regions
##############################################################################

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
REGIONS=""
ENVIRONMENT="production"
STACK_NAME_PREFIX="plot-palette"
PARALLEL=false
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Deploy Plot Palette CloudFormation stacks to multiple AWS regions.

Options:
    --regions REGIONS       Comma-separated list of regions (e.g., us-east-1,us-west-2)
    --environment ENV       Environment: development, staging, production (default: production)
    --stack-prefix NAME     Stack name prefix (default: plot-palette)
    --parallel              Deploy to regions in parallel (experimental)
    -h, --help              Show this help message

Examples:
    # Deploy to multiple regions sequentially
    $0 --regions us-east-1,us-west-2,eu-west-1 --environment production

    # Deploy in parallel
    $0 --regions us-east-1,us-west-2 --parallel

EOF
    exit 0
}

# Parse command-line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --regions)
            REGIONS="$2"
            shift 2
            ;;
        --environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --stack-prefix)
            STACK_NAME_PREFIX="$2"
            shift 2
            ;;
        --parallel)
            PARALLEL=true
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

# Validate regions
if [ -z "$REGIONS" ]; then
    echo -e "${RED}ERROR: Must specify --regions${NC}"
    usage
fi

# Convert comma-separated regions to array
IFS=',' read -ra REGION_ARRAY <<< "$REGIONS"

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║          Plot Palette - Multi-Region Deployment              ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "Environment: $ENVIRONMENT"
echo "Stack prefix: $STACK_NAME_PREFIX"
echo "Regions: ${REGION_ARRAY[*]}"
echo "Mode: $([ "$PARALLEL" = true ] && echo "Parallel" || echo "Sequential")"
echo ""

# Check regions configuration
REGIONS_CONFIG="${SCRIPT_DIR}/../parameters/regions.json"
if [ ! -f "$REGIONS_CONFIG" ]; then
    echo -e "${YELLOW}⚠ WARNING: regions.json not found${NC}"
    echo "Using default configuration"
else
    echo -e "${BLUE}Region availability check:${NC}"

    for REGION in "${REGION_ARRAY[@]}"; do
        REGION_INFO=$(jq -r ".\"$REGION\"" "$REGIONS_CONFIG" 2>/dev/null)

        if [ "$REGION_INFO" != "null" ]; then
            DISPLAY_NAME=$(echo "$REGION_INFO" | jq -r '.displayName')
            RECOMMENDED=$(echo "$REGION_INFO" | jq -r '.recommended')
            NOTES=$(echo "$REGION_INFO" | jq -r '.notes')

            echo "  ✓ $REGION ($DISPLAY_NAME)"
            echo "    Notes: $NOTES"

            if [ "$RECOMMENDED" != "true" ]; then
                echo -e "    ${YELLOW}⚠ Not recommended for production${NC}"
            fi
        else
            echo -e "  ${YELLOW}⚠ $REGION - No configuration found${NC}"
        fi
    done
    echo ""
fi

# Confirm deployment
read -p "Proceed with multi-region deployment? (yes/no) " -r
echo
if [[ ! $REPLY =~ ^yes$ ]]; then
    echo "Deployment cancelled"
    exit 0
fi

# Deploy function
deploy_to_region() {
    local REGION=$1
    local STACK_NAME="${STACK_NAME_PREFIX}-${REGION}"

    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}Deploying to: $REGION${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
    echo ""

    # Run deployment script for this region
    if ${SCRIPT_DIR}/deploy-nested.sh \
        --create \
        --stack-name "$STACK_NAME" \
        --environment "$ENVIRONMENT" \
        --region "$REGION"; then

        echo ""
        echo -e "${GREEN}✓ Deployment to $REGION completed successfully${NC}"
        return 0
    else
        echo ""
        echo -e "${RED}✗ Deployment to $REGION failed${NC}"
        return 1
    fi
}

# Track results
declare -A DEPLOYMENT_RESULTS
SUCCESSFUL=0
FAILED=0

if [ "$PARALLEL" = true ]; then
    echo -e "${YELLOW}⚠ Parallel deployment is experimental${NC}"
    echo "Deploying to all regions simultaneously..."
    echo ""

    # Deploy in parallel using background jobs
    for REGION in "${REGION_ARRAY[@]}"; do
        deploy_to_region "$REGION" &
    done

    # Wait for all deployments
    for job in $(jobs -p); do
        if wait $job; then
            SUCCESSFUL=$((SUCCESSFUL + 1))
        else
            FAILED=$((FAILED + 1))
        fi
    done

else
    # Sequential deployment
    for REGION in "${REGION_ARRAY[@]}"; do
        if deploy_to_region "$REGION"; then
            DEPLOYMENT_RESULTS[$REGION]="SUCCESS"
            SUCCESSFUL=$((SUCCESSFUL + 1))
        else
            DEPLOYMENT_RESULTS[$REGION]="FAILED"
            FAILED=$((FAILED + 1))

            echo ""
            echo -e "${YELLOW}Continue with remaining regions? (y/n)${NC}"
            read -p "> " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                echo "Multi-region deployment aborted"
                break
            fi
        fi
    done
fi

# Summary
echo ""
echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                   Deployment Summary                          ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

for REGION in "${REGION_ARRAY[@]}"; do
    RESULT="${DEPLOYMENT_RESULTS[$REGION]}"

    if [ "$RESULT" = "SUCCESS" ]; then
        echo -e "  ${GREEN}✓ $REGION - SUCCESS${NC}"

        # Get stack outputs
        STACK_NAME="${STACK_NAME_PREFIX}-${REGION}"
        FRONTEND_URL=$(aws cloudformation describe-stacks \
            --stack-name "$STACK_NAME" \
            --region "$REGION" \
            --query 'Stacks[0].Outputs[?OutputKey==`FrontendUrl`].OutputValue' \
            --output text 2>/dev/null || echo "N/A")

        if [ "$FRONTEND_URL" != "N/A" ]; then
            echo "    Frontend: $FRONTEND_URL"
        fi
    else
        echo -e "  ${RED}✗ $REGION - FAILED${NC}"
    fi
done

echo ""
echo "Total regions: ${#REGION_ARRAY[@]}"
echo "Successful: $SUCCESSFUL"
echo "Failed: $FAILED"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All deployments completed successfully!${NC}"
    exit 0
else
    echo -e "${YELLOW}⚠ Some deployments failed${NC}"
    exit 1
fi
