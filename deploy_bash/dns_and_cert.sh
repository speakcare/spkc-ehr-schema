#!/bin/bash

AWS_PROFILE="speakcare.${SPEAKCARE_ENV}"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --profile $AWS_PROFILE --query Account --output text)
AWS_REGION="$(aws configure get region --profile $AWS_PROFILE)"

SPEAKCARE_DOMAIN="speakcare.ai"
SPEAKCARE_API_SUBDOMAIN="api.${SPEAKCARE_ENV}.${SPEAKCARE_DOMAIN}"

# STEP 1: Request a wildcard ACM certificate (once per environment)

# Request a wildcard certificate for the API domain
acm_request_wildcard_cert() {
  region=$1
  recordName=$2
  aws acm request-certificate \
    --domain-name "*.${recordName}" \
    --validation-method DNS \
    --region $region \
    --idempotency-token wildcardapicert \
    --output json \
    --profile $AWS_PROFILE \
    --no-cli-pager
}

# Get the certificate ARN:

acm_get_wildcard_cert_arn() {
  region=$1
  recordName=$2
  certArn=$(aws acm list-certificates \
    --region $region \
    --query "CertificateSummaryList[?DomainName==\`*.$recordName\`].CertificateArn" \
    --output text \
    --profile $AWS_PROFILE \
    --no-cli-pager)
  echo "$certArn"
}

# CERT_ARN=$(acm_get_wildcard_cert_arn $AWS_REGION $SPEAKCARE_API_DOMAIN)



# STEP 2: Create validation CNAME in Route 53
acm_create_validation_cname_record() {
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
  zoneId=$(route53_get_zone_id $SPEAKCARE_DOMAIN)

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


acm_wait_for_cert_validation() {
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

# Get route53 zone id
route53_get_first_zone_id() {
  recordName=$1
  zoneId=$(aws route53 list-hosted-zones-by-name \
    --dns-name "$recordName" \
    --query 'HostedZones[0].Id' \
    --output text \
    --profile $AWS_PROFILE)
  echo "$zoneId"
}


route53_get_zone_id() {
  recordName=$1
  hosted_zone=$2

  # Get all hosted zones that match the domain
  zones=$(aws route53 list-hosted-zones-by-name \
    --dns-name "$recordName" \
    --query 'HostedZones[*].[Id,Name]' \
    --output text \
    --profile $AWS_PROFILE)

  # If no hosted zone name provided, return the first one (original behavior)
  if [ -z "$hosted_zone" ]; then
    echo "$zones" | head -n 1 | cut -f1
    return
  fi

  # Search for the specific hosted zone
  while IFS=$'\t' read -r id name; do
    if [ "$name" = "$hosted_zone." ]; then  # Note: Route53 names end with a dot
      echo "$id"
      return
    fi
  done <<< "$zones"

  # If no match found, return empty
  echo ""
}


route53_change_resource_record_sets() {
  recordName=$1
  zoneId=$2
  regionalHostedZoneId=$3
  regionalDomainName=$4
  echo "Creating Route 53 record for $recordName zoneId: $zoneId regionalHostedZoneId: $regionalHostedZoneId regionalDomainName: $regionalDomainName"
  aws route53 change-resource-record-sets \
    --hosted-zone-id "$zoneId" \
    --change-batch "{
      \"Comment\": \"Customer-specific API custom domain\",
      \"Changes\": [{
        \"Action\": \"UPSERT\",
        \"ResourceRecordSet\": {
          \"Name\": \"$recordName.\",
          \"Type\": \"A\",
          \"AliasTarget\": {
            \"HostedZoneId\": \"$regionalHostedZoneId\",
            \"DNSName\": \"$regionalDomainName.\",
            \"EvaluateTargetHealth\": false
          }
        }
      }]
    }" \
  --profile $AWS_PROFILE \
  --no-cli-pager
}

