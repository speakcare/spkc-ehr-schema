#!/bin/bash
source ./dns_and_cert.sh
set -euo pipefail

# Environment variables to be set by the user
#CUSTOMER_NAME="holyname"
#STAGE_NAME="prod"
#SPEAKCARE_ENV="dev"
AWS_PROFILE="speakcare.${SPEAKCARE_ENV}"

if [ -z "$SPEAKCARE_ENV" ]; then
  echo "SPEAKCARE_ENV is not set"
  exit 1
fi
if [ -z "$CUSTOMER_NAME" ]; then
  echo "CUSTOMER_NAME is not set"
  exit 1
fi
if [ -z "$STAGE_NAME" ]; then
  echo "STAGE_NAME is not set"
  exit 1
fi

echo "AWS_PROFILE: $AWS_PROFILE"
echo "Deploying customer ${CUSTOMER_NAME} in environment ${SPEAKCARE_ENV} and stage ${STAGE_NAME}"

# Login to AWS SSO
# aws sso login --profile $AWS_PROFILE

AWS_ACCOUNT_ID=$(aws sts get-caller-identity --profile $AWS_PROFILE --query Account --output text)
AWS_REGION="$(aws configure get region --profile $AWS_PROFILE)"     

# Prepare all the variables
# S3 variables
S3_BUCKET="speakcare-${CUSTOMER_NAME}"
S3_BUCKET_ARN="arn:aws:s3:::${S3_BUCKET}"
S3_RECORDING_DIR="recording"

# DynamoDB variables
DYNAMO_TABLE_ENROLLMENTS="${CUSTOMER_NAME}-recordings-enrollments"
DYNAMO_TABLE_ENROLLMENTS_ARN="arn:aws:dynamodb:${AWS_REGION}:${AWS_ACCOUNT_ID}:table/${DYNAMO_TABLE_ENROLLMENTS}"
DYNAMO_TABLE_SESSIONS="${CUSTOMER_NAME}-recordings-sessions"
DYNAMO_TABLE_SESSIONS_ARN="arn:aws:dynamodb:${AWS_REGION}:${AWS_ACCOUNT_ID}:table/${DYNAMO_TABLE_SESSIONS}"

# Lambda function names
LAMBDA_FUNCTION_NAME_BASE="speakcare-${CUSTOMER_NAME}"
LAMBDA_FUNCTION_NAME_RECORDING="${LAMBDA_FUNCTION_NAME_BASE}-recording-handler"
LAMBDA_FUNCTION_NAME_RECORDING_UPDATE="${LAMBDA_FUNCTION_NAME_BASE}-recording-update-handler"

# Lambda ARNs
LAMBDA_ARN_BASE="arn:aws:lambda:${AWS_REGION}:${AWS_ACCOUNT_ID}:function"
LAMBDA_ARN_RECORDING="${LAMBDA_ARN_BASE}:${LAMBDA_FUNCTION_NAME_RECORDING}"
LAMBDA_ARN_RECORDING_UPDATE="${LAMBDA_ARN_BASE}:${LAMBDA_FUNCTION_NAME_RECORDING_UPDATE}"

# Lambda API URIs
API_LAMBDA_URI_BASE="arn:aws:apigateway:${AWS_REGION}:lambda:path/2015-03-31/functions"
API_LAMBDA_URI_RECORDING="${API_LAMBDA_URI_BASE}/${LAMBDA_ARN_RECORDING}/invocations"
API_LAMBDA_URI_RECORDING_UPDATE="${API_LAMBDA_URI_BASE}/${LAMBDA_ARN_RECORDING_UPDATE}/invocations"


# IAM roles
ROLE_NAME_LAMBDA_RECORDING="speakcare-${CUSTOMER_NAME}-recording-lambda-role"
ROLE_ARN_LAMBDA_RECORDING="arn:aws:iam::${AWS_ACCOUNT_ID}:role/${ROLE_NAME_LAMBDA_RECORDING}"


# Policy 
SERVICE_ROLE_LAMBDA_POLICY_ARN="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
POLICY_DIR="customer-policies"
POLICY_NAME_S3_DYNAMO="speakcare-${CUSTOMER_NAME}-s3-dynamo-policy"
POLICY_ARN_S3_DYNAMO="arn:aws:iam::${AWS_ACCOUNT_ID}:policy/${POLICY_NAME_S3_DYNAMO}"
POLICY_FILE_S3_DYNAMO="${POLICY_DIR}/${CUSTOMER_NAME}-lambda-s3-dynamo-policy.json"

# domain variables
SPEAKCARE_DOMAIN="speakcare.ai"
SPEAKCARE_HOSTED_ZONE="${SPEAKCARE_ENV}.${SPEAKCARE_DOMAIN}"
SPEAKCARE_API_SUBDOMAIN="api.${SPEAKCARE_HOSTED_ZONE}"
CUSTOMER_API_DOMAIN="${CUSTOMER_NAME}.${SPEAKCARE_API_SUBDOMAIN}"

# API Gateway, REST API, and key
# ─── VARIABLES ────────────────────────────────────────────────────────────────                           # e.g. us-east-1
REST_API_NAME="speakcare-${CUSTOMER_NAME}-api"



# Create S3 buckets
s3_create_bucket() {
  bucket=$1
  aws s3 mb "s3://${bucket}" --profile $AWS_PROFILE
}
#aws s3 mb "s3://${S3_BUCKET}" --profile $AWS_PROFILE
#s3_create_bucket $S3_BUCKET

# Enable versioning on S3 buckets
s3_enable_versioning() {
  bucket=$1
  aws s3api put-bucket-versioning --bucket "${bucket}" --versioning-configuration Status=Enabled --profile $AWS_PROFILE
}
#aws s3api put-bucket-versioning --bucket "${S3_BUCKET}" --versioning-configuration Status=Enabled --profile $AWS_PROFILE
#s3_enable_versioning $S3_BUCKET

# Create DynamoDB tables
dynamodb_create_table() {
  table=$1
  aws dynamodb create-table \
    --table-name "${table}" \
    --attribute-definitions AttributeName=recordingId,AttributeType=S \
    --key-schema AttributeName=recordingId,KeyType=HASH \
    --region ${AWS_REGION} \
    --billing-mode PAY_PER_REQUEST \
    --profile $AWS_PROFILE \
    --no-cli-pager
}
#dynamodb_create_table $DYNAMO_TABLE_ENROLLMENTS
#dynamodb_create_table $DYNAMO_TABLE_SESSIONS

# Enable TTL on DynamoDB tables
dynamodb_enable_ttl() {
  table=$1
  aws dynamodb update-time-to-live \
    --table-name "${table}" \
    --time-to-live-specification Enabled=true,AttributeName=expiresAt \
    --profile $AWS_PROFILE \
    --no-cli-pager
}
#dynamodb_enable_ttl $DYNAMO_TABLE_ENROLLMENTS
#dynamodb_enable_ttl $DYNAMO_TABLE_SESSIONS




# Create IAM role for Lambda
iam_create_role() {
  role=$1
  aws iam create-role \
    --role-name "${role}" \
    --assume-role-policy-document file://trust-policy.json \
    --profile $AWS_PROFILE \
    --no-cli-pager
}
#iam_create_role $ROLE_NAME_LAMBDA_RECORDING


# Attach the AWS‑managed Lambda Logging Policy
iam_attach_role_policy() {
  role=$1
  policyArn=$2
  aws iam attach-role-policy \
    --role-name "${role}" \
    --policy-arn "${policyArn}" \
    --profile $AWS_PROFILE \
    --no-cli-pager
}
#iam_attach_role_policy $ROLE_NAME_LAMBDA_RECORDING


# Generate the Lambda S3 and DynamoDB Policy json
# Attach the Lambda S3 and DynamoDB Policy

lambda_generate_policy() {
  policy_file=$1
  mkdir -p $POLICY_DIR
cat <<EOF > $policy_file
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:PutObject"],
      "Resource": [
        "${S3_BUCKET_ARN}/${S3_RECORDING_DIR}/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": ["dynamodb:PutItem","dynamodb:UpdateItem"],
      "Resource": [
        "${DYNAMO_TABLE_ENROLLMENTS_ARN}",
        "${DYNAMO_TABLE_SESSIONS_ARN}"
      ]
    }
  ]
}
EOF
}
#lambda_generate_policy $POLICY_FILE_S3_DYNAMO

iam_put_role_policy() {
  role=$1
  policy_name=$2
  policy_document=$3
  aws iam put-role-policy \
    --role-name "${role}" \
    --policy-name "${policy_name}" \
    --policy-document file://${policy_document} \
    --profile $AWS_PROFILE \
    --no-cli-pager
}
#iam_put_role_policy $ROLE_NAME_LAMBDA_RECORDING $POLICY_NAME_S3_DYNAMO $POLICY_FILE_S3_DYNAMO

# Lambda handlers

# zip the lambda functions
# ─── ZIP THE LAMBDA FUNCTIONS ────────────────────────────────────────────────
lambda_create_zip_files() {
  cd lambda
  zip -r ../recording_handler.zip recording_handler.py
  zip -r ../recording_update_handler.zip recording_update_handler.py
  cd ..
}

lambda_delete_zip_files() {
  rm -f recording_handler.zip
  rm -f recording_update_handler.zip
}


UPLOAD_EXPIRES=$((1*3600))      # 1 hour
PRESIGN_URL_EXPIRES=$((5*60))

# deploy the lambda functions
# Create the enroll lambda function
lambda_create_recording_handler() {
  aws lambda create-function \
    --function-name $LAMBDA_FUNCTION_NAME_RECORDING \
    --runtime python3.11 \
    --role $ROLE_ARN_LAMBDA_RECORDING \
    --handler recording_handler.lambda_handler \
    --zip-file fileb://recording_handler.zip \
    --environment Variables="{CUSTOMER_NAME=${CUSTOMER_NAME},S3_RECORDING_DIR=${S3_RECORDING_DIR},UPLOAD_EXPIRES=${UPLOAD_EXPIRES},PRESIGN_URL_EXPIRES=${PRESIGN_URL_EXPIRES}}" \
    --timeout 30 \
    --memory-size 128 \
    --profile $AWS_PROFILE \
    --no-cli-pager
}

# Update the enroll lambda function code  
lambda_update_recording_handler() {
  aws lambda update-function-code \
    --function-name $LAMBDA_FUNCTION_NAME_RECORDING \
    --zip-file fileb://recording_handler.zip \
    --profile $AWS_PROFILE \
    --no-cli-pager
}

# Update the enroll lambda function configuration
lambda_update_recording_handler_configuration() {
  aws lambda update-function-configuration \
    --function-name $LAMBDA_FUNCTION_NAME_RECORDING \
    --environment Variables="{CUSTOMER_NAME=${CUSTOMER_NAME},S3_RECORDING_DIR=${S3_RECORDING_DIR},UPLOAD_EXPIRES=${UPLOAD_EXPIRES},PRESIGN_URL_EXPIRES=${PRESIGN_URL_EXPIRES}}" \
    --profile $AWS_PROFILE \
    --no-cli-pager
}


# Recording update lambda function
lambda_create_recording_update_handler() {
  aws lambda create-function \
    --function-name $LAMBDA_FUNCTION_NAME_RECORDING_UPDATE \
    --runtime python3.11 \
    --role $ROLE_ARN_LAMBDA_RECORDING \
    --handler recording_update_handler.lambda_handler \
    --zip-file fileb://recording_update_handler.zip \
    --environment Variables="{CUSTOMER_NAME=${CUSTOMER_NAME},S3_RECORDING_DIR=${S3_RECORDING_DIR}}" \
    --timeout 30 \
    --memory-size 128 \
    --profile $AWS_PROFILE \
    --no-cli-pager  
}

# Update the recording update lambda function code
lambda_update_recording_update_handler() {
  aws lambda update-function-code \
    --function-name $LAMBDA_FUNCTION_NAME_RECORDING_UPDATE \
    --zip-file fileb://recording_update_handler.zip \
    --profile $AWS_PROFILE \
    --no-cli-pager    
}

# Update the recording update lambda function configuration
lambda_update_recording_update_handler_configuration() {
  aws lambda update-function-configuration \
    --function-name $LAMBDA_FUNCTION_NAME_RECORDING_UPDATE \
    --environment Variables="{CUSTOMER_NAME=${CUSTOMER_NAME},S3_RECORDING_DIR=${S3_RECORDING_DIR}}" \
    --profile $AWS_PROFILE \
    --no-cli-pager  
}

lambda_create_handlers() {
  lambda_create_zip_files
  lambda_create_recording_handler
  lambda_create_recording_update_handler
  lambda_delete_zip_files
}

lambda_update_handlers() {
  lambda_create_zip_files
  lambda_update_recording_handler
  lambda_update_recording_handler_configuration
  lambda_update_recording_update_handler
  lambda_update_recording_update_handler_configuration
  lambda_delete_zip_files
}

lambda_update_handlers_configuration() {
  lambda_update_recording_handler_configuration
  lambda_update_recording_update_handler_configuration
}


# ─── 1) CREATE REST API ───────────────────────────────────────────────────────

# REST_API_ID=$(aws apigateway create-rest-api \
#   --name "${REST_API_NAME}" \
#   --endpoint-configuration types=REGIONAL \
#   --query 'id' --output text \
#   --profile $AWS_PROFILE)


api_gateway_create_rest_api() {
  restApiName=$1
  restApiNameApiId=$(aws apigateway create-rest-api \
    --name "${restApiName}" \
    --endpoint-configuration types=REGIONAL \
    --query 'id' --output text \
    --profile $AWS_PROFILE)
  echo "${restApiNameApiId}"
}
# REST_API_ID=$(api_gateway_create_rest_api $REST_API_NAME)
# echo "Created REST API: ${REST_API_ID}"

# ─── 2) GET ROOT RESOURCE ID ─────────────────────────────────────────────────
# RESOURCE_ROOT_ID=$(aws apigateway get-resources \
#   --rest-api-id "${REST_API_ID}" \
#   --query 'items[?path==`/`].id' \
#   --output text \
#   --profile $AWS_PROFILE)

api_gateway_get_root_resource_id() {
  restApiId=$1
  resourceRootId=$(aws apigateway get-resources \
    --rest-api-id "${restApiId}" \
    --query 'items[?path==`/`].id' \
    --output text \
    --profile $AWS_PROFILE)
  echo "${resourceRootId}"
}
# RESOURCE_ROOT_ID=$(api_gateway_get_root_resource_id $REST_API_ID) 


# ─── 3) CREATE /enroll AND /session RESOURCES ─────────────────────────────────
# RECORDING_RESOURCE_ID=$(aws apigateway create-resource \
#   --rest-api-id  "${REST_API_ID}" \
#   --parent-id    "${RESOURCE_ROOT_ID}" \
#   --path-part    recording \
#   --query 'id' --output text \
#   --profile $AWS_PROFILE)

api_gateway_create_resource() {
  restApiId=$1
  parentId=$2
  pathPart=$3
  resourceId=$(aws apigateway create-resource \
    --rest-api-id  "${restApiId}" \
    --parent-id    "${parentId}" \
    --path-part    "${pathPart}" \
    --query 'id' --output text \
    --profile $AWS_PROFILE)
  echo "${resourceId}"
}
# RECORDING_RESOURCE_ID=$(api_gateway_create_resource $REST_API_ID $RESOURCE_ROOT_ID recording)
# RECORDING_ENROLLMENT_RESOURCE_ID=$(api_gateway_create_resource $REST_API_ID $RECORDING_RESOURCE_ID enrollment)
# RECORDING_ENROLLMENT_ID_RESOURCE_ID=$(api_gateway_create_resource $REST_API_ID $RECORDING_ENROLLMENT_RESOURCE_ID "{recordingId}")
# RECORDING_SESSION_RESOURCE_ID=$(api_gateway_create_resource $REST_API_ID $RECORDING_RESOURCE_ID session)
# RECORDING_SESSION_ID_RESOURCE_ID=$(api_gateway_create_resource $REST_API_ID $RECORDING_SESSION_RESOURCE_ID "{recordingId}")


# RECORDING_UPDATE_RESOURCE_ID=$(aws apigateway create-resource \
#   --rest-api-id  "${REST_API_ID}" \
#   --parent-id    "${RECORDING_RESOURCE_ID}" \
#   --path-part    "{recordingId}" \
#   --query 'id' --output text \
#   --profile $AWS_PROFILE)


# ─── 4) PUT METHODS (POST + API KEY REQUIRED) ─────────────────────────────────
api_gateway_put_method() {
  restApiId=$1
  resourceId=$2
  httpMethod=$3
  echo "PUT METHOD: ${restApiId} ${resourceId} ${httpMethod}"
  aws apigateway put-method \
    --rest-api-id "${restApiId}" \
    --resource-id "${resourceId}" \
    --http-method "${httpMethod}" \
    --authorization-type NONE \
    --api-key-required \
    --profile $AWS_PROFILE \
    --no-cli-pager  
}

api_gateway_put_method_with_path_parameters() {
  restApiId=$1
  resourceId=$2
  httpMethod=$3
  requestParameters=$4
  echo "PUT METHOD: ${restApiId} ${resourceId} ${httpMethod} ${requestParameters}"
  aws apigateway put-method \
    --rest-api-id "${restApiId}" \
    --resource-id "${resourceId}" \
    --http-method "${httpMethod}" \
    --authorization-type NONE \
    --api-key-required \
    --request-parameters "${requestParameters}" \
    --profile $AWS_PROFILE \
    --no-cli-pager  
}

# api_gateway_put_method "${RECORDING_RESOURCE_ID}" "POST" ""
# api_gateway_put_method "${RECORDING_UPDATE_RESOURCE_ID}" "PATCH" "method.request.path.recordingId=true"
# api_gateway_put_method "${REST_API_ID}" "${RECORDING_ENROLLMENT_RESOURCE_ID}" "POST" ""
# api_gateway_put_method "${REST_API_ID}" "${RECORDING_ENROLLMENT_ID_RESOURCE_ID}" "PATCH" "method.request.path.recordingId=true"
# api_gateway_put_method "${REST_API_ID}" "${RECORDING_SESSION_RESOURCE_ID}" "POST" ""
# api_gateway_put_method "${REST_API_ID}" "${RECORDING_SESSION_ID_RESOURCE_ID}" "PATCH" "method.request.path.recordingId=true"

# aws apigateway put-method \
#   --rest-api-id "${REST_API_ID}" \
#   --resource-id "${RECORDING_RESOURCE_ID}" \
#   --http-method POST \
#   --authorization-type NONE \
#   --api-key-required \
#   --profile $AWS_PROFILE \
#   --no-cli-pager

# aws apigateway put-method \
#   --rest-api-id "${REST_API_ID}" \
#   --resource-id "${RECORDING_UPDATE_RESOURCE_ID}" \
#   --http-method PATCH \
#   --authorization-type NONE \
#   --api-key-required \
#   --request-parameters method.request.path.recordingId=true \
#   --profile $AWS_PROFILE \
#   --no-cli-pager

api_gateway_delete_method() {
  restApiId=$1
  resourceId=$2
  httpMethod=$3
  aws apigateway delete-method \
    --rest-api-id "${restApiId}" \
    --resource-id "${resourceId}" \
    --http-method "${httpMethod}" \
    --profile $AWS_PROFILE \
    --no-cli-pager
}

# api_gateway_delete_method "${REST_API_ID}" "${RECORDING_RESOURCE_ID}" "POST"
# api_gateway_delete_method "${REST_API_ID}" "${RECORDING_UPDATE_RESOURCE_ID}" "PATCH"




# ─── 5) INTEGRATE METHODS WITH LAMBDA ─────────────────────────────────────────

# aws apigateway put-integration \
#   --rest-api-id "${REST_API_ID}" \
#   --resource-id "${RECORDING_RESOURCE_ID}" \
#   --http-method POST \
#   --type AWS_PROXY \
#   --integration-http-method POST \
#   --uri "${API_URI_RECORDING}" \
#   --profile $AWS_PROFILE \
#   --no-cli-pager


api_gateway_put_integration() {
  restApiId=$1
  resourceId=$2
  httpMethod=$3
  apiUri=$4
  aws apigateway put-integration \
    --rest-api-id "${restApiId}" \
    --resource-id "${resourceId}" \
    --http-method "${httpMethod}" \
    --type AWS_PROXY \
    --integration-http-method POST \
    --uri "${apiUri}" \
    --profile $AWS_PROFILE \
    --no-cli-pager
} 

# api_gateway_put_integration "${RECORDING_RESOURCE_ID}" "POST" "${API_URI_RECORDING}"
# api_gateway_put_integration "${RECORDING_UPDATE_RESOURCE_ID}" "PATCH" "${API_URI_RECORDING_UPDATE}"

# api_gateway_put_integration "${REST_API_ID}" "${RECORDING_ENROLLMENT_RESOURCE_ID}" "POST" "${API_URI_RECORDING}"
# api_gateway_put_integration "${REST_API_ID}" "${RECORDING_ENROLLMENT_ID_RESOURCE_ID}" "PATCH" "${API_URI_RECORDING_UPDATE}"

# api_gateway_put_integration "${REST_API_ID}" "${RECORDING_SESSION_RESOURCE_ID}" "POST" "${API_URI_RECORDING}"
# api_gateway_put_integration "${REST_API_ID}" "${RECORDING_SESSION_ID_RESOURCE_ID}" "PATCH" "${API_URI_RECORDING_UPDATE}"



# aws apigateway put-integration \
#   --rest-api-id "${REST_API_ID}" \
#   --resource-id "${RECORDING_UPDATE_RESOURCE_ID}" \
#   --http-method PATCH \
#   --type AWS_PROXY \
#   --integration-http-method POST \
#   --uri "${API_URI_RECORDING_UPDATE}" \
#   --profile $AWS_PROFILE \
#   --no-cli-pager


# ─── 6) ADD PERMISSIONS FOR API GW TO INVOKE LAMBDAS ──────────────────────────
# RECORDING_SOURCE_ARN="arn:aws:execute-api:${AWS_REGION}:${AWS_ACCOUNT_ID}:${REST_API_ID}/*/POST/recording"
# RECORDING_UPDATE_SOURCE_ARN="arn:aws:execute-api:${AWS_REGION}:${AWS_ACCOUNT_ID}:${REST_API_ID}/*/PATCH/recording/*"
# RECORDING_ENROLLMENT_SOURCE_ARN="arn:aws:execute-api:${AWS_REGION}:${AWS_ACCOUNT_ID}:${REST_API_ID}/*/POST/recording/enrollment"
# RECORDING_ENROLLMENT_ID_SOURCE_ARN="arn:aws:execute-api:${AWS_REGION}:${AWS_ACCOUNT_ID}:${REST_API_ID}/*/PATCH/recording/enrollment/*"
# RECORDING_SESSION_SOURCE_ARN="arn:aws:execute-api:${AWS_REGION}:${AWS_ACCOUNT_ID}:${REST_API_ID}/*/POST/recording/session"
# RECORDING_SESSION_ID_SOURCE_ARN="arn:aws:execute-api:${AWS_REGION}:${AWS_ACCOUNT_ID}:${REST_API_ID}/*/PATCH/recording/session/*"


# aws lambda add-permission \
#   --function-name "${LAMBDA_FUNCTION_NAME_RECORDING}" \
#   --statement-id "apigw-invoke-recording-${CUSTOMER_NAME}" \
#   --action lambda:InvokeFunction \
#   --principal apigateway.amazonaws.com \
#   --source-arn "${RECORDING_SOURCE_ARN}" \
#   --profile $AWS_PROFILE \
#   --no-cli-pager

# aws lambda add-permission \
#   --function-name "${LAMBDA_FUNCTION_NAME_RECORDING_UPDATE}" \
#   --statement-id "apigw-invoke-recording-update-${CUSTOMER_NAME}" \
#   --action lambda:InvokeFunction \
#   --principal apigateway.amazonaws.com \
#   --source-arn "${RECORDING_UPDATE_SOURCE_ARN}" \
#   --profile $AWS_PROFILE \
#   --no-cli-pager

lambda_add_permission() {
  functionName=$1
  statementId=$2
  sourceArn=$3
  aws lambda add-permission \
    --function-name "${functionName}" \
    --statement-id "${statementId}" \
    --action lambda:InvokeFunction \
    --principal apigateway.amazonaws.com \
    --source-arn "${sourceArn}" \
    --profile $AWS_PROFILE \
    --no-cli-pager
}

# lambda_add_permission "${LAMBDA_FUNCTION_NAME_RECORDING}" "apigw-invoke-recording-enrollment-${CUSTOMER_NAME}" "${RECORDING_ENROLLMENT_SOURCE_ARN}"
# lambda_add_permission "${LAMBDA_FUNCTION_NAME_RECORDING_UPDATE}" "apigw-invoke-recording-update-enrollment-${CUSTOMER_NAME}" "${RECORDING_ENROLLMENT_ID_SOURCE_ARN}"
# lambda_add_permission "${LAMBDA_FUNCTION_NAME_RECORDING}" "apigw-invoke-recording-session-${CUSTOMER_NAME}" "${RECORDING_SESSION_SOURCE_ARN}"
# lambda_add_permission "${LAMBDA_FUNCTION_NAME_RECORDING_UPDATE}" "apigw-invoke-recording-update-session-${CUSTOMER_NAME}" "${RECORDING_SESSION_ID_SOURCE_ARN}"


# ─── 7) DEPLOY API TO prod STAGE ───────────────────────────────────────────────
# aws apigateway create-deployment \
#   --rest-api-id "${REST_API_ID}" \
#   --stage-name "${STAGE_NAME}" \
#   --profile $AWS_PROFILE \
#   --no-cli-pager

api_gateway_create_deployment() {
  restApiId=$1
  stageName=$2
  aws apigateway create-deployment \
    --rest-api-id "${restApiId}" \
    --stage-name "${stageName}" \
    --profile $AWS_PROFILE \
    --no-cli-pager
}

# api_gateway_create_deployment "${REST_API_ID}" "${STAGE_NAME}"
# echo "Deployed API to stage: ${STAGE_NAME}"

# ─── 8) CREATE USAGE PLAN & ASSOCIATE API STAGE ────────────────────────────────
# USAGE_PLAN_ID=$(aws apigateway create-usage-plan \
#   --name "${CUSTOMER_NAME}-usage-plan" \
#   --description "Usage plan for customer ${CUSTOMER_NAME}" \
#   --api-stages apiId="${REST_API_ID}",stage="${STAGE_NAME}" \
#   --query 'id' --output text \
#   --profile $AWS_PROFILE)

api_gateway_create_usage_plan() {
  customerName=$1
  apiId=$2
  stageName=$3
  usagePlanId=$(aws apigateway create-usage-plan \
    --name "${customerName}-usage-plan" \
    --description "Usage plan for customer ${customerName}" \
    --api-stages apiId="${apiId}",stage="${stageName}" \
    --query 'id' --output text \
    --profile $AWS_PROFILE \
    --no-cli-pager)
  echo "${usagePlanId}"
}

# USAGE_PLAN_ID= $(api_gateway_create_usage_plan "${CUSTOMER_NAME}" "${REST_API_ID}" "${STAGE_NAME}")
# echo "Created Usage Plan: ${USAGE_PLAN_ID}"

# ─── 9) CREATE API KEY & ASSOCIATE WITH USAGE PLAN ─────────────────────────────
# API_KEY_ID=$(aws apigateway create-api-key \
#   --name "${CUSTOMER_NAME}-api-key-${STAGE_NAME}-$(date -u +"%Y-%m-%dT%H-%M-%SZ")" \
#   --enabled \
#   --query "id" \
#   --output text \
#   --profile "$AWS_PROFILE")

api_gateway_create_api_key() {
  name=$1
  apiKeyId=$(aws apigateway create-api-key \
    --name "${name}" \
    --enabled \
    --query "id" \
    --output text \
    --profile "$AWS_PROFILE")
  echo "${apiKeyId}"
}

# API_KEY_ID=$(api_gateway_create_api_key "${CUSTOMER_NAME}-api-key-${STAGE_NAME}-$(date -u +"%Y-%m-%dT%H-%M-%SZ")") 


# 2) Immediately fetch the actual key value
# CLIENT_API_KEY=$(aws apigateway get-api-key \
#   --api-key "$API_KEY_ID" \
#   --include-value \
#   --query "value" \
#   --output text \
#   --profile "$AWS_PROFILE")

api_gateway_get_api_key() {
  apiKeyId=$1
  apiKeyValue=$(aws apigateway get-api-key \
    --api-key "$apiKeyId" \
    --include-value \
    --query "value" \
    --output text \
    --profile "$AWS_PROFILE")
  echo "${apiKeyValue}"
}

# CLIENT_API_KEY=$(api_gateway_get_api_key "$API_KEY_ID")
# echo "Key ID:    $API_KEY_ID"
# echo "Key Value: $CLIENT_API_KEY"

# Store the key in AWS Secrets Manager
# aws secretsmanager create-secret \
#   --name speakcare/${CUSTOMER_NAME}/api-key \
#   --description "API key for customer ${CUSTOMER_NAME} audio ingestion" \
#   --secret-string "{\"apiKeyId\":\"$API_KEY_ID\",\"apiKeyValue\":\"$CLIENT_API_KEY\"}" \
#   --profile $AWS_PROFILE \
#   --no-cli-pager

secrets_manager_create_secret() {
  customerName=$1
  apiKeyId=$2
  apiKeyValue=$3
  aws secretsmanager create-secret \
    --name "speakcare/${customerName}/api-key" \
    --description "API key for customer ${customerName} audio ingestion" \
    --secret-string "{\"apiKeyId\":\"$apiKeyId\",\"apiKeyValue\":\"$apiKeyValue\"}" \
    --profile $AWS_PROFILE \
    --no-cli-pager
} 

# secretsmanager_create_secret $CUSTOMER_NAME $API_KEY_ID $CLIENT_API_KEY



# aws apigateway create-usage-plan-key \
#   --usage-plan-id "${USAGE_PLAN_ID}" \
#   --key-id "${API_KEY_ID}" \
#   --key-type API_KEY \
#   --profile $AWS_PROFILE \
#   --no-cli-pager

api_gateway_create_usage_plan_key() {
  usagePlanId=$1
  keyId=$2
  keyType=$3
  aws apigateway create-usage-plan-key \
    --usage-plan-id "${usagePlanId}" \
    --key-id "${keyId}" \
    --key-type "${keyType}" \
    --profile $AWS_PROFILE \
    --no-cli-pager
}

# api_gateway_create_usage_plan_key "${USAGE_PLAN_ID}" "${API_KEY_ID}" "API_KEY"

# echo "API Key created (${API_KEY_ID}) and attached to Usage Plan."
# echo
# echo "   Customer ${CUSTOMER_NAME} API ready"
# echo "   URL: https://${REST_API_ID}.execute-api.${AWS_REGION}.amazonaws.com/${STAGE_NAME}"
# echo "   API Key: ${CLIENT_API_KEY}"

# Create a custom domain for the customer
# CERT_ARN=$(acm_get_wildcard_cert_arn $AWS_REGION $SPEAKCARE_API_DOMAIN)

api_gateway_create_domain_name() {
  domain=$1
  certArn=$2
  aws apigateway create-domain-name \
    --domain-name "$domain" \
    --regional-certificate-arn "$certArn" \
    --endpoint-configuration types=REGIONAL \
    --region $AWS_REGION \
    --profile $AWS_PROFILE \
    --no-cli-pager
}

# api_gateway_create_domain_name $CUSTOMER_API_DOMAIN $CERT_ARN

# Fetch the target alias and zone ID for Route 53:
api_gateway_get_domain_info() {
  domain=$1
  read regionalDomainName regionalHostedZoneId < <(aws apigateway get-domain-name \
    --domain-name "$domain" \
    --region $AWS_REGION \
    --query '[regionalDomainName, regionalHostedZoneId]' \
    --profile $AWS_PROFILE \
    --output text)
  echo "$regionalDomainName $regionalHostedZoneId"
}


# Create a base path mapping for the customer
api_gateway_create_base_path_mapping() {
  domain=$1
  restApiId=$2
  stage=$3
  aws apigateway create-base-path-mapping \
    --domain-name "$domain" \
    --rest-api-id "$restApiId" \
    --stage "$stage" \
    --region $AWS_REGION \
    --profile $AWS_PROFILE \
    --no-cli-pager
}

# api_gateway_create_base_path_mapping $CUSTOMER_API_DOMAIN $REST_API_ID $STAGE_NAME


# Add a Route 53 alias record for the custom domain
route53_change_resource_record_sets() {
  domain=$1
  zoneId=$(route53_get_zone_id $SPEAKCARE_DOMAIN $SPEAKCARE_HOSTED_ZONE)
  read regionalDomainName regionalHostedZoneId < <(api_gateway_get_domain_info $domain)
  aws route53 change-resource-record-sets \
    --hosted-zone-id "$zoneId" \
    --change-batch "{
      \"Comment\": \"Customer-specific API custom domain\",
      \"Changes\": [{
        \"Action\": \"UPSERT\",
        \"ResourceRecordSet\": {
          \"Name\": \"$domain.\",
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
  -
}

# route53_change_resource_record_sets $ZONE_ID $CUSTOMER_API_DOMAIN

speakcare_deploy_customer() {
  # ─── CREATE S3 BUCKET ───────────────────────────────────────────────────────
  s3_create_bucket $S3_BUCKET
  s3_enable_versioning $S3_BUCKET

  # ─── CREATE DYNAMODB TABLES ─────────────────────────────────────────────────
  dynamodb_create_table $DYNAMO_TABLE_ENROLLMENTS
  dynamodb_create_table $DYNAMO_TABLE_SESSIONS
  dynamodb_enable_ttl $DYNAMO_TABLE_ENROLLMENTS
  dynamodb_enable_ttl $DYNAMO_TABLE_SESSIONS

  # ─── CREATE IAM ROLE ───────────────────────────────────────────────────────
  iam_create_role $ROLE_NAME_LAMBDA_RECORDING
  iam_attach_role_policy $ROLE_NAME_LAMBDA_RECORDING $SERVICE_ROLE_LAMBDA_POLICY_ARN
  lambda_generate_policy $POLICY_FILE_S3_DYNAMO
  iam_put_role_policy $ROLE_NAME_LAMBDA_RECORDING $POLICY_NAME_S3_DYNAMO $POLICY_FILE_S3_DYNAMO

  # ─── CREATE LAMBDA HANDLERS ─────────────────────────────────────────────────
  lambda_create_handlers

  # ─── CREATE REST API ───────────────────────────────────────────────────────
  REST_API_ID=$(api_gateway_create_rest_api $REST_API_NAME)
  echo "Created REST API: ${REST_API_ID}"
  # ─── GET ROOT RESOURCE ID ─────────────────────────────────────────────────
  RESOURCE_ROOT_ID=$(api_gateway_get_root_resource_id $REST_API_ID)
  # ─── CREATE recording, recording/enrollment and recording/session RESOURCES ─────────────────────────────────
  RECORDING_RESOURCE_ID=$(api_gateway_create_resource $REST_API_ID $RESOURCE_ROOT_ID recording)

  RECORDING_ENROLLMENT_RESOURCE_ID=$(api_gateway_create_resource $REST_API_ID $RECORDING_RESOURCE_ID enrollment)
  RECORDING_ENROLLMENT_ID_RESOURCE_ID=$(api_gateway_create_resource $REST_API_ID $RECORDING_ENROLLMENT_RESOURCE_ID "{recordingId}")

  RECORDING_SESSION_RESOURCE_ID=$(api_gateway_create_resource $REST_API_ID $RECORDING_RESOURCE_ID session)
  RECORDING_SESSION_ID_RESOURCE_ID=$(api_gateway_create_resource $REST_API_ID $RECORDING_SESSION_RESOURCE_ID "{recordingId}")

  # ─── Create HTTP POST and PATCH methods for recording/enrollment and recording/session
  api_gateway_put_method "${REST_API_ID}" "${RECORDING_ENROLLMENT_RESOURCE_ID}" "POST"
  api_gateway_put_method_with_path_parameters "${REST_API_ID}" "${RECORDING_ENROLLMENT_ID_RESOURCE_ID}" "PATCH" "method.request.path.recordingId=true"

  api_gateway_put_method "${REST_API_ID}" "${RECORDING_SESSION_RESOURCE_ID}" "POST"
  api_gateway_put_method_with_path_parameters "${REST_API_ID}" "${RECORDING_SESSION_ID_RESOURCE_ID}" "PATCH" "method.request.path.recordingId=true"

  # ─── INTEGRATE METHODS WITH LAMBDA ─────────────────────────────────────────
  api_gateway_put_integration "${REST_API_ID}" "${RECORDING_ENROLLMENT_RESOURCE_ID}" "POST" "${API_LAMBDA_URI_RECORDING}"
  api_gateway_put_integration "${REST_API_ID}" "${RECORDING_ENROLLMENT_ID_RESOURCE_ID}" "PATCH" "${API_LAMBDA_URI_RECORDING_UPDATE}"

  api_gateway_put_integration "${REST_API_ID}" "${RECORDING_SESSION_RESOURCE_ID}" "POST" "${API_LAMBDA_URI_RECORDING}"
  api_gateway_put_integration "${REST_API_ID}" "${RECORDING_SESSION_ID_RESOURCE_ID}" "PATCH" "${API_LAMBDA_URI_RECORDING_UPDATE}"


  # ─── ADD PERMISSIONS FOR API GW TO INVOKE LAMBDAS ──────────────────────────
  REOCORDING_ARN_BASE="arn:aws:execute-api:${AWS_REGION}:${AWS_ACCOUNT_ID}:${REST_API_ID}"
  RECORDING_ENROLLMENT_SOURCE_ARN="${REOCORDING_ARN_BASE}/*/POST/recording/enrollment"
  RECORDING_ENROLLMENT_ID_SOURCE_ARN="${REOCORDING_ARN_BASE}/*/PATCH/recording/enrollment/*"
  RECORDING_SESSION_SOURCE_ARN="${REOCORDING_ARN_BASE}/*/POST/recording/session"
  RECORDING_SESSION_ID_SOURCE_ARN="${REOCORDING_ARN_BASE}/*/PATCH/recording/session/*"

  lambda_add_permission "${LAMBDA_FUNCTION_NAME_RECORDING}" "apigw-invoke-recording-enrollment-${CUSTOMER_NAME}" "${RECORDING_ENROLLMENT_SOURCE_ARN}"
  lambda_add_permission "${LAMBDA_FUNCTION_NAME_RECORDING_UPDATE}" "apigw-invoke-recording-update-enrollment-${CUSTOMER_NAME}" "${RECORDING_ENROLLMENT_ID_SOURCE_ARN}"
  lambda_add_permission "${LAMBDA_FUNCTION_NAME_RECORDING}" "apigw-invoke-recording-session-${CUSTOMER_NAME}" "${RECORDING_SESSION_SOURCE_ARN}"
  lambda_add_permission "${LAMBDA_FUNCTION_NAME_RECORDING_UPDATE}" "apigw-invoke-recording-update-session-${CUSTOMER_NAME}" "${RECORDING_SESSION_ID_SOURCE_ARN}"

  # ─── DEPLOY API TO STAGE ───────────────────────────────────────────────
  api_gateway_create_deployment "${REST_API_ID}" "${STAGE_NAME}"
  echo "Deployed API to stage: ${STAGE_NAME}"

  # ─── CREATE USAGE PLAN & ASSOCIATE API STAGE ─────────────────────────────
  USAGE_PLAN_ID=$(api_gateway_create_usage_plan "${CUSTOMER_NAME}" "${REST_API_ID}" "${STAGE_NAME}")
  echo "Created Usage Plan: ${USAGE_PLAN_ID}"

  # ─── 9) CREATE API KEY & ASSOCIATE WITH USAGE PLAN ─────────────────────────────
  API_KEY_NAME="${CUSTOMER_NAME}-api-key-${STAGE_NAME}-$(date -u +"%Y-%m-%dT%H-%M-%SZ")"
  API_KEY_ID=$(api_gateway_create_api_key "$API_KEY_NAME")
  # Immediately fetch the actual key value 
  CLIENT_API_KEY=$(api_gateway_get_api_key "$API_KEY_ID")
  echo "Key ID:    $API_KEY_ID"
  echo "Key Value: $CLIENT_API_KEY"
  # Store the key in AWS Secrets Manager
  secrets_manager_create_secret $CUSTOMER_NAME $API_KEY_ID $CLIENT_API_KEY
  api_gateway_create_usage_plan_key "${USAGE_PLAN_ID}" "${API_KEY_ID}" "API_KEY"

  echo "API Key created (${API_KEY_ID}) and attached to Usage Plan."
  echo
  echo "   Customer ${CUSTOMER_NAME} API ready"
  echo "   URL: https://${REST_API_ID}.execute-api.${AWS_REGION}.amazonaws.com/${STAGE_NAME}"
  echo "   API Key: ${CLIENT_API_KEY}"

  # ─── CREATE CUSTOM DOMAIN ───────────────────────────────────────────────
  CERT_ARN=$(acm_get_wildcard_cert_arn $AWS_REGION $SPEAKCARE_API_SUBDOMAIN)
  api_gateway_create_domain_name $CUSTOMER_API_DOMAIN $CERT_ARN

  # Create a base path mapping for the customer
  api_gateway_create_base_path_mapping $CUSTOMER_API_DOMAIN $REST_API_ID $STAGE_NAME

  # Add a Route 53 alias record for the custom domain
  #ZONE_ID=$(get_route53_zone_id $SPEAKCARE_DOMAIN)
  route53_change_resource_record_sets $CUSTOMER_API_DOMAIN

}
