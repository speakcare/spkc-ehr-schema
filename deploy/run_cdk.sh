#!/bin/bash

# Simple script to run CDK commands with proper AWS credentials and context
# Usage: ./run_cdk.sh [cdk-command] --customer-name <name> --environment <env> [--profile <profile>] [--version <version>] [--space <space>] [other-cdk-args...]

# Parse arguments
CUSTOMER_NAME=""
ENVIRONMENT=""
PROFILE="speakcare.dev"
VERSION="v1"
SPACE="tenants"
CDK_COMMAND=""
CDK_ARGS=()

while [[ $# -gt 0 ]]; do
    case $1 in
        --customer-name)
            CUSTOMER_NAME="$2"
            shift 2
            ;;
        --environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --profile)
            PROFILE="$2"
            shift 2
            ;;
        --version)
            VERSION="$2"
            shift 2
            ;;
        --space)
            SPACE="$2"
            shift 2
            ;;
        *)
            if [[ -z "$CDK_COMMAND" ]]; then
                CDK_COMMAND="$1"
            else
                CDK_ARGS+=("$1")
            fi
            shift
            ;;
    esac
done

# Validate required arguments
if [[ -z "$CUSTOMER_NAME" || -z "$ENVIRONMENT" ]]; then
    echo "❌ Error: --customer-name and --environment are required"
    echo "Usage: ./run_cdk.sh [cdk-command] --customer-name <name> --environment <env> [--profile <profile>] [--version <version>] [--space <space>] [other-cdk-args...]"
    echo "Defaults: --version v1, --space tenants"
    exit 1
fi

# Get AWS credentials from the profile
echo "🔐 Getting AWS credentials for profile: $PROFILE"
export $(AWS_PROFILE=$PROFILE aws configure export-credentials --format env)

# Get AWS account and region
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION=$(aws configure get region --profile $PROFILE)
if [[ -z "$REGION" ]]; then
    REGION="us-east-1"
fi

echo "🏢 AWS Account: $ACCOUNT_ID"
echo "🌍 AWS Region: $REGION"

# Build CDK context arguments
CONTEXT_ARGS=(
    "--context" "customer_name=$CUSTOMER_NAME"
    "--context" "environment=$ENVIRONMENT"
    "--context" "account=$ACCOUNT_ID"
    "--context" "region=$REGION"
    "--context" "aws_profile=$PROFILE"
    "--context" "version=$VERSION"
    "--context" "space=$SPACE"
    "--context" "@aws-cdk/core:bootstrapQualifier=speakcare"
)

# Run CDK command (assuming virtual environment is already activated)
echo "🚀 Running: cdk $CDK_COMMAND ${CDK_ARGS[@]} ${CONTEXT_ARGS[@]}"
cdk "$CDK_COMMAND" "${CDK_ARGS[@]}" "${CONTEXT_ARGS[@]}"
