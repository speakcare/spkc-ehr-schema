# recording_update_handler.py

import os
import json
import logging
import boto3
import re

dynamo   = boto3.resource('dynamodb')
customer = os.environ['CUSTOMER_NAME']

logger = logging.getLogger()
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    logger.info("Received event: %s", event)
    
    # Route to appropriate handler based on path
    path = event.get("path", "")
    
    # Check if this is the new structured API path
    if "/api/" in path and "/recording/" in path:
        return handle_new_recording_update_api(event, context)
    else:
        return handle_legacy_recording_update_api(event, context)

def handle_legacy_recording_update_api(event, context):
    """Handle legacy /recording/session/{recordingId} and /recording/enrollment/{recordingId} paths"""
    # Parse path parameters
    path = event.get("path", "")

    # Check if the path matches the expected patterns
    enrollment_pattern = r'^/recording/enrollment/[^/]+$'
    session_pattern = r'^/recording/session/[^/]+$'

    if re.match(enrollment_pattern, path):
        recordingType = "enrollment"
    elif re.match(session_pattern, path):
        recordingType = "session"
    else:
        raise ValueError(f"Invalid path format: {path}")
    
    recordingId = event.get('pathParameters',{}).get('recordingId')
    if not recordingId:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Missing recordingId in path'})
        }

    # Parse body
    try:
        body = json.loads(event.get('body','{}'))
    except json.JSONDecodeError:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Invalid JSON body'})
        }

    # Call the internal function
    return update_recording_internal(recordingType, recordingId, body)

def handle_new_recording_update_api(event, context):
    """Handle new structured API /api/{version}/{space}/{tenant}/recording/{recordingId}"""
    # Parse path parameters to extract tenant and recordingId
    path_params = event.get('pathParameters', {})
    tenant = path_params.get('tenant')
    recordingId = path_params.get('recordingId')
    
    if not tenant:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Missing tenant in path'})
        }
    
    if not recordingId:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Missing recordingId in path'})
        }
    
    # Validate tenant matches customer
    if tenant != customer:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Invalid tenant'})
        }
    
    # Parse body
    try:
        body = json.loads(event.get('body','{}'))
    except json.JSONDecodeError:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Invalid JSON body'})
        }

    # New API only handles sessions (no enrollments)
    recordingType = "session"
    
    # Call the internal function
    return update_recording_internal(recordingType, recordingId, body)

def update_recording_internal(recordingType, recordingId, body):
    """Internal function that handles the core recording update logic"""
    # Validate required fields
    status = body.get('status')
    if status not in ('UPLOADED','PROCESSED','ERROR'):
        return {
            'statusCode': 400,
            'body': json.dumps({
               'error':'`status` must be one of "UPLOADED", "PROCESSED", or "ERROR"'
            })
        }

    # Derive table name
    tableName = f"{customer}-recordings-{'enrollments' if recordingType=='enrollment' else 'sessions'}"
    table = dynamo.Table(tableName)

    # Perform the update: set status, remove expiresAt so TTL no longer applies
    try:
        if status == 'UPLOADED':
            # When status is uploaded, include the md5sum field
            table.update_item(
                Key={'recordingId': recordingId},
                UpdateExpression="SET #s = :st, md5sum = :md REMOVE expiresAt",
                ExpressionAttributeNames={'#s': 'status'},
                ExpressionAttributeValues={
                    ':st': status,
                    ':md': body.get('md5sum', '')
                },
                ConditionExpression="attribute_exists(recordingId)"
            )
        else:
            # For other statuses, just update the status
            table.update_item(
                Key={'recordingId': recordingId},
                UpdateExpression="SET #s = :st REMOVE expiresAt",
                ExpressionAttributeNames={'#s': 'status'},
                ExpressionAttributeValues={':st': status},
                ConditionExpression="attribute_exists(recordingId)"
            )
    except dynamo.meta.client.exceptions.ConditionalCheckFailedException:
        return {
            'statusCode': 404,
            'body': json.dumps({'error': 'Recording not found'})
        }

    # Return the updated resource
    return {
        'statusCode': 200,
        'body': json.dumps({
            'recordingId': recordingId,
            'status':      status
        })
    }
