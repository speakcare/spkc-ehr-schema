
#!/bin/bash
set -e

DOMAIN="speakcare"
REPOSITORY="python-packages"
PROFILE=${AWS_PROFILE:-"speakcare.dev"}

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


export AWS_PROFILE="$PROFILE"
echo "AWS_PROFILE: $AWS_PROFILE"
REGION=$(aws configure get region --profile $AWS_PROFILE)
if [[ -z "$REGION" ]]; then
    echo "Error: AWS region not configured. Please run 'aws configure' to set your region."
    exit 1
fi
echo "REGION: $REGION"

echo "Building package..."
poetry build

echo "Getting CodeArtifact credentials..."
CODEARTIFACT_AUTH_TOKEN=$(aws codeartifact get-authorization-token \
  --domain ${DOMAIN} \
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

echo "Configuring Poetry for publishing..."
# For publishing: no /simple/ suffix
poetry config repositories.codeartifact "${CODEARTIFACT_REPO_URL}"
poetry config http-basic.codeartifact aws "${CODEARTIFACT_AUTH_TOKEN}"

echo "Publishing to CodeArtifact..."
poetry publish -r codeartifact

VERSION=$(poetry version -s)
echo "✓ Successfully published spkc-ehr-schema ${VERSION}"
