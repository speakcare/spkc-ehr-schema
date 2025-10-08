# recording_handler.py

import json
import logging
import uuid
import time
import boto3
import os

s3     = boto3.client('s3')
dynamo = boto3.resource('dynamodb')
customer = os.environ['CUSTOMER_NAME']
bucket = os.environ['S3_BUCKET']
recordingDir = os.environ['S3_RECORDING_DIR']
uploadExpires = int(os.environ['UPLOAD_EXPIRES'])
presignUrlExpires = int(os.environ['PRESIGN_URL_EXPIRES'])

logger = logging.getLogger()
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    logger.info("Received event: %s", event)
    
    # Route to appropriate handler based on path
    path = event.get("path", "")
    
    # Check if this is the new structured API path
    if "/api/" in path and "/recording" in path:
        return handle_new_recording_api(event, context)
    else:
        return handle_legacy_recording_api(event, context)

def handle_legacy_recording_api(event, context):
    """Handle legacy /recording/session and /recording/enrollment paths"""
    # 1) Parse path parameters
    path = event.get("path", "")
    if path.endswith("/enrollment"):
        recordingType = "enrollment"
    elif path.endswith("/session"):
        recordingType = "session"
    else:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": f"Invalid path: {path}"})
        }
    # 2) Parse body
    body = json.loads(event['body'])
    customerId = body.get('customerId')
    if not customerId:
        return {
            'statusCode': 400,
            'body': json.dumps({'error':'customerId is required'})
        }
    if customerId != customer:
        return {
            'statusCode': 400,
            'body': json.dumps({'error':'Invalid customerId'})
        }
    
    fileName = body['fileName']      
    username  = body['username']

    # Call the internal function with legacy parameters
    return create_recording_internal(
        recordingType=recordingType,
        customerId=customerId,
        fileName=fileName,
        username=username,
        body=body
    )

def handle_new_recording_api(event, context):
    """Handle new structured API /api/{version}/{space}/{tenant}/recording"""
    # Parse path parameters to extract tenant
    path_params = event.get('pathParameters', {})
    tenant = path_params.get('tenant')
    
    if not tenant:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Missing tenant in path'})
        }
    
    # Validate tenant matches customer
    if tenant != customer:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Invalid tenant'})
        }
    
    # Parse body
    try:
        body = json.loads(event.get('body', '{}'))
    except json.JSONDecodeError:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Invalid JSON body'})
        }
    
    # Extract required fields
    fileName = body.get('fileName')
    userId = body.get('userId')
    
    if not fileName:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'fileName is required'})
        }
    
    if not userId:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'userId is required'})
        }
    
    # Use userId as username for internal function
    username = userId
    
    # Call the internal function with new API parameters
    return create_recording_internal(
        recordingType="session",  # New API only handles sessions
        customerId=tenant,        # tenant becomes customerId
        fileName=fileName,
        username=username,
        body=body
    )

def create_recording_internal(recordingType, customerId, fileName, username, body):
    """Internal function that handles the core recording creation logic"""
    # Derive bucket, table, S3 key
    if recordingType == 'enrollment':
        prefix     = f"{recordingDir}/enrollments/{username}"
        tableName = f"{customer}-recordings-enrollments"
    else:
        prefix     = f"{recordingDir}/sessions/{username}"
        tableName = f"{customer}-recordings-sessions"

    key = f"{prefix}/{fileName}"

    # Timestamps for TTL
    now       = int(time.time())
    expiresAt = now + uploadExpires   # expire in 5 minutes

    # Write a pending_upload record
    recordingId = str(uuid.uuid4())
    table  = dynamo.Table(tableName)
    item = {
      'recordingId':      recordingId,
      'customerId':       customerId,
      'type':             recordingType,
      'username':         username,
      'deviceType':       body.get('deviceType','unknown'),
      'deviceUniqueId':   body.get('deviceUniqueId','unknown'),
      'startTime':        body.get('startTime', ""),
      'endTime':          body.get('endTime', ""),
      'fileName':         fileName,
      's3Uri':            f"s3://{bucket}/{key}",
      'status':           body.get('status', 'PENDING_UPLOAD'),
      'createdAt':        now,
      'expiresAt':        expiresAt
    }
    if recordingType == 'enrollment':
      item['speakerType'] = body.get('speakerType','clinician')

    table.put_item(Item=item)

    # Generate presigned URL
    upload_url = s3.generate_presigned_url(
      ClientMethod='put_object',
      Params={'Bucket': bucket, 'Key': key},
      ExpiresIn=presignUrlExpires   # 5 minutes
    )

    # Respond with the reservation
    return {
      'statusCode': 201,
      'body': json.dumps({
        'recordingId': recordingId,
        'status':      'pending_upload',
        'uploadUrl':   upload_url,
        'expiresAt':   expiresAt
      })
    }
