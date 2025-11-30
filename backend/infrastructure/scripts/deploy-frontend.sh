#!/bin/bash

# Plot Palette Frontend Deployment Script
# This script deploys the React frontend to AWS Amplify

set -e

STACK_NAME="${1:-plot-palette-frontend}"
REGION="${2:-us-east-1}"

echo "=================================================="
echo " Plot Palette Frontend Deployment"
echo "=================================================="
echo " Stack Name: $STACK_NAME"
echo " Region: $REGION"
echo "=================================================="

# Check if required parameters are set
if [ -z "$API_ENDPOINT" ]; then
    echo "Error: API_ENDPOINT environment variable is required"
    echo "Example: export API_ENDPOINT=https://abc123.execute-api.us-east-1.amazonaws.com"
    exit 1
fi

if [ -z "$USER_POOL_ID" ]; then
    echo "Error: USER_POOL_ID environment variable is required"
    echo "Example: export USER_POOL_ID=us-east-1_XXXXXXXXX"
    exit 1
fi

if [ -z "$USER_POOL_CLIENT_ID" ]; then
    echo "Error: USER_POOL_CLIENT_ID environment variable is required"
    echo "Example: export USER_POOL_CLIENT_ID=XXXXXXXXXXXXXXXXXX"
    exit 1
fi

echo ""
echo "Creating CloudFormation stack..."
aws cloudformation create-stack \
    --stack-name "$STACK_NAME" \
    --template-body file://infrastructure/cloudformation/frontend-stack.yaml \
    --parameters \
        ParameterKey=ApiEndpoint,ParameterValue="$API_ENDPOINT" \
        ParameterKey=UserPoolId,ParameterValue="$USER_POOL_ID" \
        ParameterKey=UserPoolClientId,ParameterValue="$USER_POOL_CLIENT_ID" \
        ParameterKey=AwsRegion,ParameterValue="$REGION" \
    --capabilities CAPABILITY_IAM \
    --region "$REGION"

echo ""
echo "Waiting for stack creation to complete..."
aws cloudformation wait stack-create-complete \
    --stack-name "$STACK_NAME" \
    --region "$REGION"

echo ""
echo "=================================================="
echo " Deployment Complete!"
echo "=================================================="
echo ""
echo "Getting Amplify App details..."
APP_ID=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$REGION" \
    --query "Stacks[0].Outputs[?OutputKey=='AmplifyAppId'].OutputValue" \
    --output text)

APP_URL=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$REGION" \
    --query "Stacks[0].Outputs[?OutputKey=='AmplifyDefaultDomain'].OutputValue" \
    --output text)

echo ""
echo "Amplify App ID: $APP_ID"
echo "App URL: $APP_URL"
echo ""
echo "To trigger a build, run:"
echo "  aws amplify start-job --app-id $APP_ID --branch-name main --job-type RELEASE --region $REGION"
echo ""
echo "=================================================="
