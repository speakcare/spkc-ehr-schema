#!/bin/bash
set -euo pipefail

AWS_PROFILE="speakcare.dev"
# Login to AWS SSO
aws sso login --profile $AWS_PROFILE


AWS_ACCOUNT_ID=$(aws sts get-caller-identity --profile $AWS_PROFILE --query Account --output text)
CUSTOMER_NAME="holyname"

# Prepare all the variables
# S3 variables
S3_BUCKET="speakcare-${CUSTOMER_NAME}"
S3_BUCKET_ARN="arn:aws:s3:::${S3_BUCKET}"
S3_RECORDING_DIR="recording"

# DynamoDB variables
DYNAMO_TABLE_ENROLLMENTS="${CUSTOMER_NAME}-enrollments"
DYNAMO_TABLE_ENROLLMENTS_ARN="arn:aws:dynamodb:us-east-1:${AWS_ACCOUNT_ID}:table/${DYNAMO_TABLE_ENROLLMENTS}"
DYNAMO_TABLE_SESSIONS="${CUSTOMER_NAME}-sessions"
DYNAMO_TABLE_SESSIONS_ARN="arn:aws:dynamodb:us-east-1:${AWS_ACCOUNT_ID}:table/${DYNAMO_TABLE_SESSIONS}"

# Lambda function names
LAMBDA_FUNCTION_NAME_RECORDING="speakcare-${CUSTOMER_NAME}-recording-handler"
LAMBDA_FUNCTION_NAME_RECORDING_UPDATE="speakcare-${CUSTOMER_NAME}-recording-update-handler"

# Lambda ARNs
LAMBDA_ARN_RECORDING="arn:aws:lambda:${AWS_REGION}:${AWS_ACCOUNT_ID}:function:${LAMBDA_FUNCTION_NAME_RECORDING}"
LAMBDA_ARN_RECORDING_UPDATE="arn:aws:lambda:${AWS_REGION}:${AWS_ACCOUNT_ID}:function:${LAMBDA_FUNCTION_NAME_RECORDING_UPDATE}"


# IAM roles
ROLE_NAME_LAMBDA_RECORDING="speakcare-${CUSTOMER_NAME}-recording-lambda-role"
ROLE_ARN_LAMBDA_RECORDING="arn:aws:iam::${AWS_ACCOUNT_ID}:role/${ROLE_NAME_LAMBDA_RECORDING}"


# Policy 
POLICY_DIR="customer-policies"
POLICY_NAME_S3_DYNAMO="speakcare-${CUSTOMER_NAME}-s3-dynamo-policy"
POLICY_ARN_S3_DYNAMO="arn:aws:iam::${AWS_ACCOUNT_ID}:policy/${POLICY_NAME_S3_DYNAMO}"
POLICY_FILE_S3_DYNAMO="${POLICY_DIR}/${CUSTOMER_NAME}-lambda-s3-dynamo-policy.json"

# Create S3 buckets
aws s3 mb "s3://${S3_BUCKET}" --profile $AWS_PROFILE

# Enable versioning on S3 buckets
aws s3api put-bucket-versioning --bucket "${S3_BUCKET}" --versioning-configuration Status=Enabled --profile $AWS_PROFILE


# Create DynamoDB tables

aws dynamodb create-table \
  --table-name "${DYNAMO_TABLE_ENROLLMENTS}" \
  --attribute-definitions AttributeName=recordingId,AttributeType=S \
  --key-schema AttributeName=recordingId,KeyType=HASH \
  --region us-east-1 \
  --billing-mode PAY_PER_REQUEST \
  --profile $AWS_PROFILE \
  --no-cli-pager


aws dynamodb update-time-to-live \
  --table-name "${DYNAMO_TABLE_ENROLLMENTS}" \
  --time-to-live-specification Enabled=true,AttributeName=expiresAt \
  --profile $AWS_PROFILE \
  --no-cli-pager

aws dynamodb create-table \
  --table-name "${DYNAMO_TABLE_SESSIONS}" \
  --attribute-definitions AttributeName=recordingId,AttributeType=S \
  --key-schema AttributeName=recordingId,KeyType=HASH \
  --region us-east-1 \
  --billing-mode PAY_PER_REQUEST \
  --profile $AWS_PROFILE \
  --no-cli-pager

aws dynamodb update-time-to-live \
  --table-name "${DYNAMO_TABLE_SESSIONS}" \
  --time-to-live-specification Enabled=true,AttributeName=expiresAt \
  --profile $AWS_PROFILE \
  --no-cli-pager


# Create IAM role for Lambda
aws iam create-role \
  --role-name $ROLE_NAME_LAMBDA_RECORDING \
  --assume-role-policy-document file://trust-policy.json \
  --profile $AWS_PROFILE \
   --no-cli-pager


# Attach the AWS‑managed Lambda Logging Policy
aws iam attach-role-policy \
  --role-name $ROLE_NAME_LAMBDA_RECORDING \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole \
  --profile $AWS_PROFILE \
  --no-cli-pager

# Generate the Lambda S3 and DynamoDB Policy json
# Attach the Lambda S3 and DynamoDB Policy

mkdir -p $POLICY_DIR
cat <<EOF > $POLICY_FILE_S3_DYNAMO
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


aws iam put-role-policy \
  --role-name $ROLE_NAME_LAMBDA_RECORDING \
  --policy-name $POLICY_NAME_S3_DYNAMO \
  --policy-document file://$POLICY_FILE_S3_DYNAMO \
  --profile $AWS_PROFILE \
  --no-cli-pager

# Lambda handlers
# zip the lambda functions  
cd lambda
zip -r ../recording_handler.zip recording_handler.py
zip -r ../recording_update_handler.zip recording_update_handler.py
cd ..

# deploy the lambda functions
# Create the enroll lambda function
aws lambda create-function \
  --function-name $LAMBDA_FUNCTION_NAME_RECORDING \
  --runtime python3.11 \
  --role $ROLE_ARN_LAMBDA_RECORDING \
  --handler recording_handler.lambda_handler \
  --zip-file fileb://recording_handler.zip \
  --environment Variables="{CUSTOMER_NAME=${CUSTOMER_NAME},S3_RECORDING_DIR=${S3_RECORDING_DIR}}" \
  --timeout 30 \
  --memory-size 128 \
  --profile $AWS_PROFILE \
  --no-cli-pager

# Update the enroll lambda function code
aws lambda update-function-code \
  --function-name $LAMBDA_FUNCTION_NAME_RECORDING \
  --zip-file fileb://recording_handler.zip \
  --profile $AWS_PROFILE \
  --no-cli-pager

# Update the enroll lambda function configuration
aws lambda update-function-configuration \
  --function-name $LAMBDA_FUNCTION_NAME_RECORDING \
  --environment Variables="{CUSTOMER_NAME=${CUSTOMER_NAME},S3_RECORDING_DIR=${S3_RECORDING_DIR}}" \
  --profile $AWS_PROFILE \
  --no-cli-pager


# Recording update lambda function
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

# Update the recording update lambda function code
aws lambda update-function-code \
  --function-name $LAMBDA_FUNCTION_NAME_RECORDING_UPDATE \
  --zip-file fileb://recording_update_handler.zip \
  --profile $AWS_PROFILE \
  --no-cli-pager    

# Update the recording update lambda function configuration
aws lambda update-function-configuration \
  --function-name $LAMBDA_FUNCTION_NAME_RECORDING_UPDATE \
  --environment Variables="{CUSTOMER_NAME=${CUSTOMER_NAME},S3_RECORDING_DIR=${S3_RECORDING_DIR}}" \
  --profile $AWS_PROFILE \
  --no-cli-pager  

 
# API Gateway, REST API, and key
# ─── VARIABLES ────────────────────────────────────────────────────────────────
AWS_REGION="$(aws configure get region --profile $AWS_PROFILE)"                              # e.g. us-east-1
REST_API_NAME="speakcare-${CUSTOMER_NAME}-api"
STAGE_NAME="prod"


# ─── 1) CREATE REST API ───────────────────────────────────────────────────────
REST_API_ID=$(aws apigateway create-rest-api \
  --name "${REST_API_NAME}" \
  --endpoint-configuration types=REGIONAL \
  --query 'id' --output text \
  --profile $AWS_PROFILE)

echo "Created REST API: ${REST_API_ID}"

# ─── 2) GET ROOT RESOURCE ID ─────────────────────────────────────────────────
RESOURCE_ROOT_ID=$(aws apigateway get-resources \
  --rest-api-id "${REST_API_ID}" \
  --query 'items[?path==`/`].id' \
  --output text \
  --profile $AWS_PROFILE)

# ─── 3) CREATE /enroll AND /session RESOURCES ─────────────────────────────────
RECORDING_RESOURCE_ID=$(aws apigateway create-resource \
  --rest-api-id  "${REST_API_ID}" \
  --parent-id    "${RESOURCE_ROOT_ID}" \
  --path-part    recording \
  --query 'id' --output text \
  --profile $AWS_PROFILE)

RECORDING_UPDATE_RESOURCE_ID=$(aws apigateway create-resource \
  --rest-api-id  "${REST_API_ID}" \
  --parent-id    "${RECORDING_RESOURCE_ID}" \
  --path-part    "{recordingId}" \
  --query 'id' --output text \
  --profile $AWS_PROFILE)


# ─── 4) PUT METHODS (POST + API KEY REQUIRED) ─────────────────────────────────
aws apigateway put-method \
  --rest-api-id "${REST_API_ID}" \
  --resource-id "${RECORDING_RESOURCE_ID}" \
  --http-method POST \
  --authorization-type NONE \
  --api-key-required \
  --profile $AWS_PROFILE \
  --no-cli-pager

aws apigateway put-method \
  --rest-api-id "${REST_API_ID}" \
  --resource-id "${RECORDING_UPDATE_RESOURCE_ID}" \
  --http-method PATCH \
  --authorization-type NONE \
  --api-key-required \
  --request-parameters method.request.path.recordingId=true \
  --profile $AWS_PROFILE \
  --no-cli-pager


RECORDING_SOURCE_ARN="arn:aws:execute-api:${AWS_REGION}:${AWS_ACCOUNT_ID}:${REST_API_ID}/*/POST/recording"
RECORDING_UPDATE_SOURCE_ARN="arn:aws:execute-api:${AWS_REGION}:${AWS_ACCOUNT_ID}:${REST_API_ID}/*/PATCH/recording/*"


# ─── 5) INTEGRATE METHODS WITH LAMBDA ─────────────────────────────────────────
API_URI_RECORDING="arn:aws:apigateway:${AWS_REGION}:lambda:path/2015-03-31/functions/${LAMBDA_ARN_RECORDING}/invocations"
API_URI_RECORDING_UPDATE="arn:aws:apigateway:${AWS_REGION}:lambda:path/2015-03-31/functions/${LAMBDA_ARN_RECORDING_UPDATE}/invocations"


aws apigateway put-integration \
  --rest-api-id "${REST_API_ID}" \
  --resource-id "${RECORDING_RESOURCE_ID}" \
  --http-method POST \
  --type AWS_PROXY \
  --integration-http-method POST \
  --uri "${API_URI_RECORDING}" \
  --profile $AWS_PROFILE \
  --no-cli-pager

aws apigateway put-integration \
  --rest-api-id "${REST_API_ID}" \
  --resource-id "${RECORDING_UPDATE_RESOURCE_ID}" \
  --http-method PATCH \
  --type AWS_PROXY \
  --integration-http-method POST \
  --uri "${API_URI_RECORDING_UPDATE}" \
  --profile $AWS_PROFILE \
  --no-cli-pager


# ─── 6) ADD PERMISSIONS FOR API GW TO INVOKE LAMBDAS ──────────────────────────
aws lambda add-permission \
  --function-name "${LAMBDA_FUNCTION_NAME_RECORDING}" \
  --statement-id "apigw-invoke-recording-${CUSTOMER_NAME}" \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn "${RECORDING_SOURCE_ARN}" \
  --profile $AWS_PROFILE \
  --no-cli-pager

aws lambda add-permission \
  --function-name "${LAMBDA_FUNCTION_NAME_RECORDING_UPDATE}" \
  --statement-id "apigw-invoke-recording-update-${CUSTOMER_NAME}" \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn "${RECORDING_UPDATE_SOURCE_ARN}" \
  --profile $AWS_PROFILE \
  --no-cli-pager

# ─── 7) DEPLOY API TO prod STAGE ───────────────────────────────────────────────
aws apigateway create-deployment \
  --rest-api-id "${REST_API_ID}" \
  --stage-name "${STAGE_NAME}" \
  --profile $AWS_PROFILE \
  --no-cli-pager

echo "Deployed API to stage: ${STAGE_NAME}"

# ─── 8) CREATE USAGE PLAN & ASSOCIATE API STAGE ────────────────────────────────
USAGE_PLAN_ID=$(aws apigateway create-usage-plan \
  --name "${CUSTOMER_NAME}-usage-plan" \
  --description "Usage plan for customer ${CUSTOMER_NAME}" \
  --api-stages apiId="${REST_API_ID}",stage="${STAGE_NAME}" \
  --query 'id' --output text \
  --profile $AWS_PROFILE)

echo "Created Usage Plan: ${USAGE_PLAN_ID}"

# ─── 9) CREATE API KEY & ASSOCIATE WITH USAGE PLAN ─────────────────────────────
API_KEY_ID=$(aws apigateway create-api-key \
  --name "${CUSTOMER_NAME}-api-key-${STAGE_NAME}-$(date -u +"%Y-%m-%dT%H-%M-%SZ")" \
  --enabled \
  --query "id" \
  --output text \
  --profile "$AWS_PROFILE")

# 2) Immediately fetch the actual key value
CLIENT_API_KEY=$(aws apigateway get-api-key \
  --api-key "$API_KEY_ID" \
  --include-value \
  --query "value" \
  --output text \
  --profile "$AWS_PROFILE")

echo "Key ID:    $API_KEY_ID"
echo "Key Value: $CLIENT_API_KEY"

# Store the key in AWS Secrets Manager
aws secretsmanager create-secret \
  --name speakcare/${CUSTOMER_NAME}/api-key \
  --description "API key for customer ${CUSTOMER_NAME} audio ingestion" \
  --secret-string "{\"apiKeyId\":\"$API_KEY_ID\",\"apiKeyValue\":\"$CLIENT_API_KEY\"}" \
  --profile $AWS_PROFILE \
  --no-cli-pager


aws apigateway create-usage-plan-key \
  --usage-plan-id "${USAGE_PLAN_ID}" \
  --key-id "${API_KEY_ID}" \
  --key-type API_KEY \
  --profile $AWS_PROFILE \
  --no-cli-pager

echo "API Key created (${API_KEY_ID}) and attached to Usage Plan."
echo
echo "   Customer ${CUSTOMER_NAME} API ready"
echo "   URL: https://${REST_API_ID}.execute-api.${AWS_REGION}.amazonaws.com/${STAGE_NAME}"
echo "   API Key: ${CLIENT_API_KEY}"


# Test the enrollment API

# compute md5 of the file
md5=$(md5sum ../recordings/admission.mp3 | awk '{ print $1 }')

response=$(curl -s -X POST "https://${REST_API_ID}.execute-api.${AWS_REGION}.amazonaws.com/${STAGE_NAME}/recording" \
  -H "x-api-key: ${CLIENT_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "customerId":     "holyname",
    "username":       "testuser",
    "type":           "enroll",
    "speakerType":    "patient",
    "deviceType":     "SM-R910",
    "deviceUniqueId": "12345678",
    "fileName":       "admission.mp3",
    "startTime":      "2021-01-01T00:00:00Z",
    "endTime":        "2021-01-01T00:00:00Z",
    "md5":            "'"${md5}"'"
  }')

recordingId=$(echo "$response" | jq -r '.recordingId')
uploadUrl=$(echo "$response" | jq -r '.uploadUrl')

# Upload the file to S3
curl -i -X PUT \
     --upload-file ../recordings/admission.mp3 \
     "${uploadUrl}"

# Test the session API
curl -i -X PATCH "https://${REST_API_ID}.execute-api.${AWS_REGION}.amazonaws.com/${STAGE_NAME}/recording/${recordingId}" \
  -H "x-api-key: ${CLIENT_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
     "type":           "enroll",
     "status":         "uploaded"
  }'

# try to update non-existent recording in the session table
curl -i -X PATCH "https://${REST_API_ID}.execute-api.${AWS_REGION}.amazonaws.com/${STAGE_NAME}/recording/${recordingId}" \
  -H "x-api-key: ${CLIENT_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
     "type":           "session",
     "status":         "uploaded"
  }'




# Test the session API

response=$(curl -s -X POST "https://${REST_API_ID}.execute-api.${AWS_REGION}.amazonaws.com/${STAGE_NAME}/recording" \
  -H "x-api-key: ${CLIENT_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "customerId":     "holyname",
    "username":       "testuser",
    "type":           "session",
    "deviceType":     "SM-R910",
    "deviceUniqueId": "12345678",
    "fileName":       "admission.mp3",
    "startTime":      "2021-01-01T00:00:00Z",
    "endTime":        "2021-01-01T00:00:00Z",
    "md5":            "'"${md5}"'"
  }')

recordingId=$(echo "$response" | jq -r '.recordingId')
uploadUrl=$(echo "$response" | jq -r '.uploadUrl')

# Upload the file to S3
curl -i -X PUT \
     --upload-file ../recordings/admission.mp3 \
     "${uploadUrl}"

# Test the session API
curl -i -X PATCH "https://${REST_API_ID}.execute-api.${AWS_REGION}.amazonaws.com/${STAGE_NAME}/recording/${recordingId}" \
  -H "x-api-key: ${CLIENT_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
     "type":           "session",
     "status":         "uploaded"
  }'

# try to update non-existent recording in the enrollments table
curl -i -X PATCH "https://${REST_API_ID}.execute-api.${AWS_REGION}.amazonaws.com/${STAGE_NAME}/recording/${recordingId}" \
  -H "x-api-key: ${CLIENT_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
     "type":           "enroll",
     "status":         "uploaded"
  }'

  
