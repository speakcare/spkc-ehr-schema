# recording_update_handler.py

import os
import json
import boto3

dynamo   = boto3.resource('dynamodb')
customer = os.environ['CUSTOMER_NAME']

def lambda_handler(event, context):
    print(f"Received event: {event}")
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
    
    recordingId = event.get('pathParameters',{}).get('recordingId')
    if not recordingId:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Missing recordingId in path'})
        }

    # 2) Parse body
    try:
        body = json.loads(event.get('body','{}'))
    except json.JSONDecodeError:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Invalid JSON body'})
        }

    # 2) Validate required fields
    status = body.get('status')
    if status not in ('uploaded','processed','error'):
        return {
            'statusCode': 400,
            'body': json.dumps({
               'error':'`status` must be one of "uploaded", "processed", or "error"'
            })
        }

    # recordingType = body.get('type')  # "enroll" or "session"
    # if recordingType not in ('enroll','session'):
    #     return {
    #         'statusCode': 400,
    #         'body': json.dumps({'error':'`type` must be "enroll" or "session"'})
    #     }

    # 3) Derive table name
    # enrollment table is "<customer>-enrollments"
    # session table is "<customer>-sessions"
    tableName = f"{customer}-{'enrollments' if recordingType=='enrollment' else 'sessions'}"
    table = dynamo.Table(tableName)

    # 4) Perform the update: set status, remove expiresAt so TTL no longer applies
    try:
        if status == 'uploaded':
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

    # 5) Return the updated resource
    return {
        'statusCode': 200,
        'body': json.dumps({
            'recordingId': recordingId,
            'status':      status
        })
    }
