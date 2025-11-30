#!/bin/bash
#
# Plot Palette - Lambda Packaging Script
#
# Packages all Lambda functions with dependencies into ZIP files for deployment.
#

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Starting Lambda packaging...${NC}"

# Configuration
LAMBDA_DIR="../lambdas"
BUILD_DIR="build/lambda"
SHARED_DIR="backend/shared"

# Clean build directory
echo "Cleaning build directory..."
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# Array of Lambda functions to package
declare -A LAMBDA_FUNCTIONS=(
    ["jobs"]="create_job list_jobs get_job delete_job"
    ["templates"]="create_template list_templates get_template update_template delete_template"
    ["seed_data"]="generate_upload_url validate_seed_data"
    ["dashboard"]="get_stats"
)

# Function to package a Lambda
package_lambda() {
    local category=$1
    local lambda_name=$2

    echo -e "${GREEN}Packaging ${category}/${lambda_name}...${NC}"

    # Create function directory
    local func_dir="$BUILD_DIR/${category}_${lambda_name}"
    mkdir -p "$func_dir"

    # Copy Lambda function file
    if [ -f "$LAMBDA_DIR/$category/${lambda_name}.py" ]; then
        cp "$LAMBDA_DIR/$category/${lambda_name}.py" "$func_dir/"
    else
        echo "Error: Lambda file not found: $LAMBDA_DIR/$category/${lambda_name}.py"
        return 1
    fi

    # Copy shared library
    echo "  → Copying shared library..."
    cp -r "$SHARED_DIR" "$func_dir/"

    # Install dependencies if requirements.txt exists
    if [ -f "$LAMBDA_DIR/$category/requirements.txt" ]; then
        echo "  → Installing dependencies..."
        pip install -r "$LAMBDA_DIR/$category/requirements.txt" -t "$func_dir/" --quiet --upgrade
    fi

    # Create ZIP
    echo "  → Creating ZIP file..."
    cd "$func_dir"
    zip -r9 "../${category}_${lambda_name}.zip" . -q
    cd - > /dev/null

    # Get ZIP size
    local size=$(du -h "$BUILD_DIR/${category}_${lambda_name}.zip" | cut -f1)
    echo -e "  ${GREEN}✓ Created ${category}_${lambda_name}.zip (${size})${NC}"

    # Clean up temporary directory
    rm -rf "$func_dir"
}

# Package all Lambda functions
for category in "${!LAMBDA_FUNCTIONS[@]}"; do
    for lambda in ${LAMBDA_FUNCTIONS[$category]}; do
        package_lambda "$category" "$lambda"
    done
done

# Summary
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Lambda packaging complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Package summary:"
ls -lh "$BUILD_DIR"/*.zip | awk '{print "  " $9 " → " $5}'
echo ""
echo -e "${YELLOW}Total packages: $(ls -1 $BUILD_DIR/*.zip | wc -l)${NC}"
echo ""
