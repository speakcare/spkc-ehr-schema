#!/bin/bash
# Setup script for AWS CodeArtifact authentication with Poetry
# 
# This script configures Poetry to use AWS CodeArtifact as a package source
# for installing speakcare-common and other packages from the private repository.
#
# What it does:
# 1. Gets an AWS CodeArtifact authorization token
# 2. Retrieves the CodeArtifact repository endpoint URL
# 3. Configures Poetry with the CodeArtifact source (with /simple/ suffix for installing)
# 4. Sets up authentication credentials for Poetry
# 5. Displays success message and token expiration info (12 hours)
#
# Prerequisites:
# - AWS CLI configured with appropriate permissions
# - Poetry installed
# - Access to the 'speakcare' CodeArtifact domain
#
# Usage: ./setup-codeartifact.sh

set -e

DOMAIN="speakcare"
REPOSITORY="python-packages"
REGION="us-east-1"

while [[ $# -gt 0 ]]; do
    case $1 in
        --help|-h)
            echo "Usage: ./setup-codeartifact.sh --profile <profile>"
            echo ""
            echo "Optional:"
            echo "  --profile <profile> AWS profile (default: speakcare.dev)"
            echo ""
            echo "Examples:"
            echo "  ./setup-codeartifact.sh --profile speakcare.dev"
            exit 0
            ;;
        --profile)
            PROFILE="$2"
            shift 2
            ;;
        *)
            echo "Error: Unknown option $1"
            exit 1
            ;;
    esac
done

PROFILE=${PROFILE:-speakcare.dev}

export AWS_PROFILE="$PROFILE"
echo "AWS_PROFILE: $AWS_PROFILE"
REGION=$(aws configure get region --profile "$AWS_PROFILE")
if [[ -z "$REGION" ]]; then
    echo "Error: AWS region not configured. Please run 'aws configure' to set your region."
    exit 1
fi
echo "REGION: $REGION"

echo "Configuring Poetry for AWS CodeArtifact..."

CODEARTIFACT_AUTH_TOKEN=$(aws codeartifact get-authorization-token \
  --domain "${DOMAIN}" \
  --query authorizationToken \
  --output text \
  --region "${REGION}" \
  --profile "${AWS_PROFILE}")

CODEARTIFACT_REPO_URL=$(aws codeartifact get-repository-endpoint \
  --domain "${DOMAIN}" \
  --repository "${REPOSITORY}" \
  --format pypi \
  --query repositoryEndpoint \
  --output text \
  --region "${REGION}" \
  --profile "${AWS_PROFILE}")

# For installing: WITH /simple/
poetry source add --priority=supplemental codeartifact "${CODEARTIFACT_REPO_URL}simple/" 2>/dev/null || true
poetry config http-basic.codeartifact aws "${CODEARTIFACT_AUTH_TOKEN}"

echo "✓ CodeArtifact configured successfully"
echo "Token expires in 12 hours"
echo ""
echo "Run 'poetry install' to install dependencies"