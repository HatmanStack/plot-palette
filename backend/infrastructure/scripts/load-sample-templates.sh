#!/bin/bash
# Load sample templates into DynamoDB via API Gateway
set -e

API_ENDPOINT=$1
TOKEN=$2

if [ -z "$API_ENDPOINT" ] || [ -z "$TOKEN" ]; then
    echo "Usage: ./load-sample-templates.sh <API_ENDPOINT> <TOKEN>"
    echo ""
    echo "Example:"
    echo "  ./load-sample-templates.sh https://api.example.com eyJhbG..."
    echo ""
    echo "Get TOKEN by logging in through the web UI or using Cognito authentication"
    exit 1
fi

echo "========================================="
echo "Loading Sample Templates"
echo "========================================="
echo "API Endpoint: $API_ENDPOINT"
echo ""

# Check if required tools are available
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 is required but not found"
    exit 1
fi

# Check if required Python packages are available
python3 -c "import yaml, requests" 2>/dev/null || {
    echo "Error: Required Python packages not found"
    echo "Installing required packages..."
    python3 -m pip install pyyaml requests --quiet || {
        echo "Failed to install packages. Please install manually:"
        echo "  pip install pyyaml requests"
        exit 1
    }
}

success_count=0
fail_count=0

# Loop through all YAML files in sample_templates
for template_file in backend/sample_templates/*.yaml; do
    if [ ! -f "$template_file" ]; then
        continue
    fi

    template_name=$(basename "$template_file" .yaml)
    echo "Loading: $template_name..."

    # Convert YAML to JSON and post to API
    result=$(python3 << EOF
import yaml
import json
import requests
import sys

try:
    with open('$template_file', 'r') as f:
        template_data = yaml.safe_load(f)

    template = template_data['template']

    # Prepare API request
    payload = {
        'name': template['name'],
        'description': template.get('description', ''),
        'category': template.get('category', 'general'),
        'is_public': template.get('is_public', True),
        'template_definition': {
            'steps': template['steps']
        }
    }

    # Make API request
    response = requests.post(
        '$API_ENDPOINT/templates',
        headers={
            'Authorization': 'Bearer $TOKEN',
            'Content-Type': 'application/json'
        },
        json=payload,
        timeout=30
    )

    if response.status_code in [200, 201]:
        result = response.json()
        print(f"SUCCESS|{template['name']}|{result.get('template_id', 'unknown')}")
    else:
        print(f"FAILED|{template['name']}|{response.status_code}|{response.text}")
        sys.exit(1)

except Exception as e:
    print(f"ERROR|{template['name']}|{str(e)}")
    sys.exit(1)
EOF
    )

    # Parse result
    status=$(echo "$result" | cut -d'|' -f1)
    template_display=$(echo "$result" | cut -d'|' -f2)

    if [ "$status" == "SUCCESS" ]; then
        template_id=$(echo "$result" | cut -d'|' -f3)
        echo "  ✓ Loaded: $template_display (ID: $template_id)"
        ((success_count++))
    else
        error_msg=$(echo "$result" | cut -d'|' -f3-)
        echo "  ✗ Failed: $template_display"
        echo "     Error: $error_msg"
        ((fail_count++))
    fi
    echo ""
done

echo "========================================="
echo "Summary"
echo "========================================="
echo "Successfully loaded: $success_count templates"
echo "Failed: $fail_count templates"
echo ""

if [ $fail_count -gt 0 ]; then
    echo "⚠ Some templates failed to load. Check errors above."
    exit 1
else
    echo "✓ All sample templates loaded successfully!"
    exit 0
fi
