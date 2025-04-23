#!/bin/bash

AWS_PROFILE="speakcare.dev"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --profile $AWS_PROFILE --query Account --output text)
AWS_REGION="$(aws configure get region --profile $AWS_PROFILE)"

SPEAKCARE_DOMAIN="speakcare.ai"
SPEAKCARE_ENV="dev"
SPEAKCARE_API_DOMAIN="api.${SPEAKCARE_ENV}.${SPEAKCARE_DOMAIN}"

# STEP 1: Request a wildcard ACM certificate (once per environment)

# Request a wildcard certificate for the API domain
acm_request_wildcard_cert() {
  region=$1
  domain=$2
  aws acm request-certificate \
    --domain-name "*.${domain}" \
    --validation-method DNS \
    --region $region \
    --idempotency-token wildcardapicert \
    --output json \
    --profile $AWS_PROFILE \
    --no-cli-pager
}

# Get the certificate ARN:

get_wildcard_cert_arn() {
  region=$1
  domain=$2
  certArn=$(aws acm list-certificates \
    --region $region \
    --query "CertificateSummaryList[?DomainName==\`*.$domain\`].CertificateArn" \
    --output text \
    --profile $AWS_PROFILE \
    --no-cli-pager)
  echo "$certArn"
}

# CERT_ARN=$(get_wildcard_cert_arn $AWS_REGION $SPEAKCARE_API_DOMAIN)

# Get route53 zone id
get_route53_zone_id() {
  domain=$1
  zoneId=$(aws route53 list-hosted-zones-by-name \
    --dns-name "$domain" \
    --query 'HostedZones[0].Id' \
    --output text \
    --profile $AWS_PROFILE)
  echo "$zoneId"
}

# STEP 2: Create validation CNAME in Route 53
create_validation_cname_record() {
  cert_arn=$1
  region=$2
  # Fetch DNS validation info:
  dnsValidation=$(aws acm describe-certificate \
    --certificate-arn "$cert_arn" \
    --region $region \
    --query 'Certificate.DomainValidationOptions[0].ResourceRecord' \
    --profile $AWS_PROFILE)

  echo "DNS Validation: ${dnsValidation}"
  dnsName=$(echo "$dnsValidation" | jq -r '.Name')
  dnsValue=$(echo "$dnsValidation" | jq -r '.Value')

  # Get the Route 53 zone ID:
  zoneId=$(get_route53_zone_id $SPEAKCARE_DOMAIN)

  echo "Route 53 Zone ID: ${zoneId}"

  # Create the CNAME record:
  cnameRecord=$(aws route53 change-resource-record-sets \
    --hosted-zone-id "$zoneId" \
    --change-batch '{
      "Comment": "ACM domain validation for wildcard",
      "Changes": [{
      "Action": "UPSERT",
      "ResourceRecordSet": {
        "Name": "'"${dnsName}"'",
        "Type": "CNAME",
        "TTL": 300,
        "ResourceRecords": [{
          "Value": "'"${dnsValue}"'"
        }]
        }
      }]
    }' \
    --profile $AWS_PROFILE)

  echo "CNAME Record: ${cnameRecord}"
}


wait_for_acm_validation() {
  local cert_arn="$1"
  local region="$AWS_REGION"
  local status="PENDING_VALIDATION"
  
  echo "Waiting for ACM certificate to be validated..."
  start_time=$(date -u +%s)
  until [ "$status" == "ISSUED" ]; do
    status=$(aws acm describe-certificate \
      --certificate-arn "$cert_arn" \
      --region "$region" \
      --query 'Certificate.Status' \
      --output text \
      --profile $AWS_PROFILE) 
    now_timestamp=$(date -u +%s)
    waiting_time=$((now_timestamp - start_time))
    echo "Current status: $status"

    if [[ "$status" == "ISSUED" ]]; then
      echo "Validation completed successfully"
      break
    elif [[ "$status" == "FAILED" ]]; then
      echo "Validation failed for certificate: $cert_arn"
      exit 1
    fi
    echo "Waiting for validation to complete... $(date -u -r $waiting_time +%H:%M:%S)"
    sleep 10
  done

  echo "ACM certificate is validated and issued!"
}


