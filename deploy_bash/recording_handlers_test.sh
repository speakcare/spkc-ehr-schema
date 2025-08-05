#!/bin/bash


# Set environment variables
AWS_PROFILE="speakcare.dev"
AWS_REGION="us-east-1"

CUSTOMER="<customer_name>"
CUSTOMER_API_DOMAIN="<customer>.api.dev.speakcare.ai"
CLIENT_API_KEY="<api-key>"


# Test the enrollment API

# compute md5 of the file
md5=$(md5sum ../recordings/admission.mp3 | awk '{ print $1 }')

response=$(curl -s -X POST "https://${REST_API_ID}.execute-api.${AWS_REGION}.amazonaws.com/${STAGE_NAME}/recording" \
  -H "x-api-key: ${CLIENT_API_KEY}" \
  -H "Content-Type: application/json" \
  -d @- <<EOF
{
  "customerId":     "${CUSTOMER}",
  "username":       "testuser",
  "speakerType":    "patient",
  "deviceType":     "SM-R910",
  "deviceUniqueId": "12345678",
  "fileName":       "admission.mp3",
  "startTime":      "2025-04-23T00:00:00Z",
  "endTime":        "2025-04-23T00:10:00Z"
}
EOF
)

response=$(curl -s -X POST "https://${CUSTOMER_API_DOMAIN}/recording/enrollment" \
  -H "x-api-key: ${CLIENT_API_KEY}" \
  -H "Content-Type: application/json" \
  -d @- <<EOF
{
  "customerId":     "${CUSTOMER}",
  "username":       "testuser",
  "speakerType":    "patient",
  "deviceType":     "SM-R910",
  "deviceUniqueId": "12345678",
  "fileName":       "admission.mp3",
  "startTime":      "2025-04-23T00:00:00Z",
  "endTime":        "2025-04-23T00:10:00Z"
}
EOF
)

recordingId=$(echo "$response" | jq -r '.recordingId')
uploadUrl=$(echo "$response" | jq -r '.uploadUrl')

# Upload the file to S3
curl -i -X PUT \
     --upload-file ../recordings/admission.mp3 \
     "${uploadUrl}"

# update the enrollment status to uploaded
curl -i -X PATCH "https://${CUSTOMER_API_DOMAIN}/recording/enrollment/${recordingId}" \
  -H "x-api-key: ${CLIENT_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
     "status":         "uploaded",
     "md5sum":         "'"${md5}"'"
  }'

# try to update non-existent recording in the session table
curl -i -X PATCH "https://${CUSTOMER_API_DOMAIN}/recording/session/${recordingId}" \
  -H "x-api-key: ${CLIENT_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
     "status":         "uploaded",
     "md5sum":         "'"${md5}"'"
  }'




# Test the session API

response=$(curl -s -X POST "https://${CUSTOMER_API_DOMAIN}/recording/session" \
  -H "x-api-key: ${CLIENT_API_KEY}" \
  -H "Content-Type: application/json" \
  -d @- <<EOF
{
  "customerId":     "${CUSTOMER}",
  "username":       "testuser",
  "deviceType":     "SM-R910",
  "deviceUniqueId": "12345678",
  "fileName":       "admission.mp3",
  "startTime":      "2025-04-23T00:00:00Z",
  "endTime":        "2025-04-23T00:10:00Z"
}
EOF
)

recordingId=$(echo "$response" | jq -r '.recordingId')
uploadUrl=$(echo "$response" | jq -r '.uploadUrl')

# Upload the file to S3
curl -i -X PUT \
     --upload-file ../recordings/admission.mp3 \
     "${uploadUrl}"

# Test the session API
curl -i -X PATCH "https://${CUSTOMER_API_DOMAIN}/recording/session/${recordingId}" \
  -H "x-api-key: ${CLIENT_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
     "status":         "uploaded",
     "md5sum":         "'"${md5}"'"
  }'

# try to update non-existent recording in the enrollments table
curl -i -X PATCH "https://${CUSTOMER_API_DOMAIN}/recording/enrollment/${recordingId}" \
  -H "x-api-key: ${CLIENT_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
     "status":         "uploaded",
     "md5sum":         "'"${md5}"'"
  }'

  
